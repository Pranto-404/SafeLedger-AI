import {useEffect,useRef,useState,type FormEvent} from 'react';
import {ApiError} from './api';
import {useCurrency} from './Currency';
import {DraftCard} from './DraftCard';
import {formatDate,prettyVendor} from './format';
import {localAnswer,type AssistantAction} from './localAssistant';
import {looksLikeTransaction,parseRecordSentence} from './recordParser';
import type {AgentResult,CashEvent,Draft,Forecast,Invoice,Profile,Session,Snapshot} from './types';

type Props={snapshot:Snapshot|null;forecast:Forecast|null;week:Forecast|null;events:CashEvent[];invoices:Invoice[];session:Session;profile:Profile|null;cloudAvailable:boolean;revision:string;request:<T>(path:string,body?:unknown)=>Promise<T>;onSaved:()=>Promise<void>;onProposal:()=>Promise<void>;onNavigate:(action:AssistantAction)=>void;onClose?:()=>void;visible:boolean};
type Message={id:number;role:'user'|'assistant';text:string;kind?:'device'|'smart';actions?:AssistantAction[];draft?:Draft;agent?:AgentResult;offTopic?:string;retry?:string};
const hints=['What is my balance?','I paid Rahman 5000 for freight yesterday','Which loan fits my cash flow?','Which bills are overdue?'];

export default function Assistant({snapshot,forecast,week,events,invoices,session,profile,cloudAvailable,revision,request,onSaved,onProposal,onNavigate,onClose,visible}:Props){
  const {currency,digits,nativeMoney:money}=useCurrency();
  const [messages,setMessages]=useState<Message[]>([]);const [task,setTask]=useState('');const [busy,setBusy]=useState(false);
  const [picking,setPicking]=useState(false);const [target,setTarget]=useState('');
  const lastIntent=useRef('');const nextId=useRef(0);const mounted=useRef(true);const pending=useRef(false);
  const log=useRef<HTMLDivElement>(null);const input=useRef<HTMLTextAreaElement>(null);
  const owner=session.role==='owner';const smart=!!profile?.smart_assist&&cloudAvailable;
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{if(visible)input.current?.focus();},[visible]);
  useEffect(()=>{if(log.current)log.current.scrollTop=log.current.scrollHeight;},[messages,busy]);
  const add=(...m:Omit<Message,'id'>[])=>setMessages(cur=>[...cur,...m.map(x=>({...x,id:nextId.current++}))].slice(-40));
  const openBills=invoices.filter(i=>i.status==='open');

  async function ask(question:string,force=false){
    const q=question.trim();if(!q||pending.current)return;
    pending.current=true;setBusy(true);setTask('');
    add({role:'user',text:q});
    try{
      // 1. A sentence that describes a payment or a bill becomes a draft record to confirm.
      if(owner){
        const draft=parseRecordSentence(q,{currency,digits});
        if(draft){add({role:'assistant',kind:'device',text:draft.kind==='invoice'?'I read this as a bill you still have to pay. Check it, then add it to your records.':draft.direction==='inflow'?'I read this as money you received. Check it, then add it to your records.':'I read this as a payment you made. Check it, then add it to your records.',draft});return;}
      }
      // 2. Answers that need no cloud: balances, forecasts, invoices, how-to, definitions.
      const local=localAnswer(q,{snapshot,forecast,week,events,invoices},lastIntent.current);
      if(local.handled){lastIntent.current=local.intent;add({role:'assistant',kind:'device',text:local.text,actions:local.actions});return;}
      const blocked=['security','approval','limit'].includes(local.intent);
      if(blocked){add({role:'assistant',kind:'device',text:local.text});return;}
      // 3. Everything else goes to smart assist, if it is on.
      const offTopic=local.intent==='out_of_domain';
      if(offTopic&&!force){add({role:'assistant',kind:'device',text:local.text,offTopic:q});return;}
      if(!smart){add({role:'assistant',kind:'device',text:profile&&!profile.smart_assist?'I can only answer that with smart assist. You can turn it on in Settings.':'Smart assist is not available right now. I can still help with your balance, invoices, cash flow, loans and adding records.'});return;}
      if(owner&&looksLikeTransaction(q)){
        const r=await request<{draft:Draft}>('/assist/extract',{text:q});
        if(!mounted.current)return;
        if(r.draft.ok){add({role:'assistant',kind:'smart',text:'I read this from your message. Check it, then add it to your records.',draft:r.draft});return;}
      }
      const history=messages.filter(m=>!m.draft&&!m.agent).slice(-4).map(m=>({role:m.role,text:m.text.slice(0,500)}));
      const r=await request<{answer:string}>('/assist/ask',{question:q,history});
      if(mounted.current)add({role:'assistant',kind:'smart',text:r.answer});
    }catch(e){
      if(!mounted.current)return;
      const text=e instanceof ApiError&&(e.code==='AI_QUOTA_EXHAUSTED'||e.status===503)?'Smart assist is busy right now. Please try again in a minute. Your balance, invoices and cash-flow questions still work.':e instanceof Error?e.message:'Something went wrong. Please try again.';
      add({role:'assistant',kind:'device',text,retry:q});
    }finally{pending.current=false;if(mounted.current){setBusy(false);input.current?.focus();}}
  }
  async function prepare(){
    if(!target||pending.current)return;pending.current=true;setBusy(true);setPicking(false);
    const bill=openBills.find(i=>i.invoice_id===target);
    add({role:'user',text:`Prepare a payment for ${bill?bill.invoice_number+' · '+prettyVendor(bill.vendor_id):'this bill'}`});
    try{
      const r=await request<AgentResult>('/agent/tasks',{task:'Review this invoice and prepare it for approval if it is safe to pay.',invoice_id:target,allow_proposal:true,external_ai_consent:true,fallback_ai_consent:false});
      if(mounted.current)add({role:'assistant',kind:'smart',text:r.explanation.join('\n\n'),agent:r});
    }catch(e){if(mounted.current)add({role:'assistant',kind:'device',text:e instanceof Error?e.message:'I could not prepare that payment.'});}
    finally{pending.current=false;if(mounted.current)setBusy(false);}
  }
  return <section className="panel chat-panel" aria-label="Assistant">
    <div className="chat-heading"><div className="assistant-orb" aria-hidden="true">✦</div><div><h2>Assistant</h2><p>Ask a question, or tell me what you paid or received</p></div>{onClose&&<button className="secondary chat-close" onClick={onClose} aria-label="Minimize assistant">×</button>}</div>
    <div className="chat-log" ref={log} role="log" aria-label="Conversation" aria-live="polite">
      {!messages.length&&<div className="chat-welcome"><span aria-hidden="true">✦</span><h3>How can I help?</h3><p>Speak or type in English, বাংলা or Banglish. I can add records for you, explain your numbers and compare loan offers.</p><div className="chat-suggestions">{hints.filter(h=>owner||!/^I paid/.test(h)).map(h=><button key={h} className="secondary" onClick={()=>void ask(h)}>{h}</button>)}</div></div>}
      {messages.map(m=><article className={'chat-message '+m.role} key={m.id}>
        {m.role==='assistant'&&<small>{m.kind==='smart'?'Smart answer':'Assistant'}</small>}
        {m.text.split('\n\n').map((para,i)=><p key={i}>{para}</p>)}
        {m.draft&&owner&&<DraftCard compact draft={m.draft} revision={revision} request={request} onSaved={onSaved} onDiscard={()=>setMessages(cur=>cur.map(x=>x.id===m.id?{...x,draft:undefined,text:'Discarded. Nothing was added.'}:x))}/>}
        {!!m.actions?.length&&<div className="chat-actions">{m.actions.map(a=><button className="secondary" key={a} onClick={()=>onNavigate(a)}>{({Financing:'Open Loans',Data:'Open Add records',Audit:'Open Activity'} as Record<string,string>)[a]||`Open ${a}`}</button>)}</div>}
        {m.offTopic&&smart&&<div className="chat-actions"><button className="secondary" disabled={busy} onClick={()=>void ask(m.offTopic!,true)}>It is about my business: try anyway</button></div>}
        {m.retry&&<div className="chat-actions"><button className="secondary" disabled={busy} onClick={()=>void ask(m.retry!)}>Try again</button></div>}
        {m.agent?.proposal&&<button onClick={()=>void onProposal()}>Open payment approval</button>}
        {m.agent&&!!m.agent.limitations.length&&<details><summary>Good to know</summary>{m.agent.limitations.map((v,i)=><p key={i}>{v}</p>)}</details>}
        {m.kind==='smart'&&!m.draft&&!m.agent&&<small className="muted">AI-written. Please double-check important decisions.</small>}
      </article>)}
      {busy&&<p role="status" className="chat-thinking">Thinking<span aria-hidden="true">…</span></p>}
    </div>
    {picking&&<div className="chat-pick"><label htmlFor="agent-bill">Which bill?</label><select id="agent-bill" value={target} onChange={e=>setTarget(e.target.value)}><option value="">Choose a bill</option>{openBills.map(i=><option key={i.invoice_id} value={i.invoice_id}>{prettyVendor(i.vendor_id)} · {i.invoice_number} · {money(i.amount_minor)} · due {formatDate(i.due_on)}</option>)}</select><div className="actions"><button disabled={!target||busy} onClick={()=>void prepare()}>Prepare for approval</button><button className="secondary" onClick={()=>setPicking(false)}>Cancel</button></div></div>}
    {owner&&!!openBills.length&&smart&&!picking&&<div className="chat-chips"><button className="secondary small" disabled={busy} onClick={()=>setPicking(true)}>Prepare a payment…</button></div>}
    <form className="chat-compose" onSubmit={(e:FormEvent)=>{e.preventDefault();void ask(task);}}><label htmlFor="agent-task" className="sr-only">Message the assistant</label><textarea ref={input} id="agent-task" rows={2} placeholder="Ask, or say what you paid…" maxLength={800} value={task} disabled={busy} onChange={e=>setTask(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><button disabled={busy||!task.trim()} aria-label="Send message">{busy?'…':'↑'}</button></form>
    <p className="chat-footnote">{smart?'Smart assist is on · simple questions are answered on your device':'Answers on your device · turn on smart assist in Settings for more'}</p>
  </section>;
}
