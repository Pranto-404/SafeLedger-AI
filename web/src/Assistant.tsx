import {useEffect,useRef,useState,type FormEvent} from 'react';
import {useCurrency} from './Currency';
import type {Session,Snapshot,Forecast,Invoice,AgentResult} from './types';
type Props={snapshot:Snapshot|null;forecast:Forecast|null;invoices:Invoice[];session:Session;request:<T>(path:string,body?:unknown)=>Promise<T>;onProposal:()=>Promise<void>;onClose?:()=>void;visible:boolean};
type Message={id:number;role:'user'|'assistant';text:string;result?:AgentResult;source?:string};
type Provider={provider_name:string;configured:boolean};
export default function Assistant({snapshot,forecast,invoices,session,request,onProposal,onClose,visible}:Props){
 const {money}=useCurrency();
 const [provider,setProvider]=useState<Provider|null>(null);const [statusError,setStatusError]=useState('');
 const [mode,setMode]=useState<'private'|'ai'>('private');const [messages,setMessages]=useState<Message[]>([]);
 const [task,setTask]=useState('');const [target,setTarget]=useState('');const [allow,setAllow]=useState(false);const [consent,setConsent]=useState(false);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const nextId=useRef(0);const mounted=useRef(true);const pending=useRef(false);const log=useRef<HTMLDivElement>(null);const input=useRef<HTMLTextAreaElement>(null);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 useEffect(()=>{if(visible)input.current?.focus();},[visible]);
 useEffect(()=>{if(log.current)log.current.scrollTop=log.current.scrollHeight;},[messages,busy]);
 async function checkProvider(){setStatusError('');try{const x=await request<Provider>('/agent/status');if(mounted.current)setProvider(x);}catch(e){if(mounted.current)setStatusError(e instanceof Error?e.message:'Could not check AI availability.');}}
 // No provider request until the user chooses external AI.
 function chooseAI(){setMode('ai');if(!provider)void checkProvider();}
 function privateReply(question:string):string {
   if(!snapshot)return 'Your records have not loaded. Refresh data, then ask again.';
   const q=question.toLowerCase();
   if(/balance|cash|income|expense|money|টাকা|ব্যালেন্স|টাকা|forecast|outlook|flow/.test(q))return `As of ${snapshot.as_of}, your recorded balance is ${money(snapshot.balance_minor)}. Cleared income: ${money(snapshot.income_minor)}; cleared expenses: ${money(snapshot.expenses_minor)}.${forecast?` Your baseline 30-day closing balance is ${money(forecast.closing_balance_minor)}. ${forecast.first_shortfall_on?'The first reserve shortfall is projected on '+forecast.first_shortfall_on+'.':'No reserve shortfall is projected.'}`:''} These figures come from your saved records, not a bank connection. Use Cash flow to test a different reserve or receipt delay.`;
   if(/invoice|bill|payment|risk|ইনভয়েস/.test(q)){const open=invoices.filter(i=>i.status==='open');return `You have ${open.length} open invoices.${open.length?' Open Invoices to inspect amounts, due dates and source evidence.':''} ${forecast?.risk_flags.length?forecast.risk_flags.length+' invoice risk groups need review.':'No invoice risk groups are flagged in the current forecast.'} To record an invoice payment, prepare its proposal and invite a separate approver through Workspace & teammates. I cannot approve or send money.`;}
   if(/currenc|usd|bdt|jpy|eur|kwd/.test(q))return `This workspace uses ${snapshot.currency}. Choose a currency when creating an account or a workspace under Workspace & teammates. Keep separate currencies in separate workspaces; no exchange rate or conversion is assumed.`;
   if(/add|record|start|help|hello|hi\b|হ্যালো|সাহায্য/.test(q))return 'Open Data to add cash activity or an unpaid supplier invoice. Cleared cash updates your balance; scheduled activity and unpaid invoices affect the forecast. I can show your balance, outlook and invoice risks here. Choose External AI for questions that need model analysis.';
   return 'I can explain your recorded balance, cash outlook, invoice risks and how to use this workspace. This private helper uses fixed rules, not AI. Choose External AI for broader questions; you control when anything is shared.';
 }
 async function ask(e:FormEvent){e.preventDefault();const question=task.trim();if(!question||pending.current)return;
   if(mode==='ai'&&(!provider?.configured||!consent)){setError('Enable a configured provider and confirm sharing before asking external AI.');return;}
   pending.current=true;setBusy(true);setError('');
   try{
     let result:AgentResult|undefined;
     if(mode==='ai'){
       const previous=messages.filter(m=>m.role==='user').slice(-2).map(m=>m.text.slice(0,250)).join('\n');
       const contextual=(previous?'Earlier questions (context only):\n'+previous+'\nCurrent question: ':'')+question;
       result=await request<AgentResult>('/agent/tasks',{task:contextual.slice(-2000),invoice_id:target||null,allow_proposal:allow,external_ai_consent:consent});
     }
     if(!mounted.current)return;
     const text=result?result.explanation.join('\n\n'):privateReply(question);
     const pair:Message[]=[{id:nextId.current++,role:'user',text:question},{id:nextId.current++,role:'assistant',text,result,source:result?'External AI · verified facts':`Private helper · saved snapshot ${snapshot?.as_of??'unavailable'}`}];
     setMessages(current=>[...current,...pair].slice(-40));setTask('');setAllow(false);input.current?.focus();
   }catch(e){if(mounted.current)setError(e instanceof Error?e.message:'The assistant is unavailable. Your question is saved below—retry when ready.');}
   finally{pending.current=false;if(mounted.current)setBusy(false);}
 }
 return <section className="panel chat-panel" aria-label="Workspace assistant"><div className="chat-heading"><div className="assistant-orb" aria-hidden="true">✦</div><div><h2>Assistant</h2><p>{mode==='private'?'Private help, right where you work':'External AI · on demand'}</p></div>{onClose&&<button className="secondary chat-close" onClick={onClose} aria-label="Minimize assistant">×</button>}</div>
 <div className="chat-modes" role="group" aria-label="Assistant mode"><button className={mode==='private'?'active':'secondary'} aria-pressed={mode==='private'} disabled={busy} onClick={()=>setMode('private')}>Private helper</button><button className={mode==='ai'?'active':'secondary'} aria-pressed={mode==='ai'} disabled={busy} onClick={chooseAI}>External AI</button></div>
 <div className="chat-log" ref={log} role="log" aria-label="Conversation" aria-live="polite">{!messages.length&&<div className="chat-welcome"><span aria-hidden="true">✦</span><h3>How can I help?</h3><p>Ask about your balance, cash flow or invoices. Your conversation stays in this session.</p><div className="chat-suggestions">{['What is my available balance?','Explain my cash outlook.','How do I add a record?'].map(q=><button key={q} className="secondary" onClick={()=>{setTask(q);input.current?.focus();}}>{q}</button>)}</div></div>}{messages.map(m=><article className={'chat-message '+m.role} key={m.id}><small>{m.role==='user'?'You':m.source}</small><p>{m.text}</p>{m.result&&<><div className="chat-facts">{m.result.facts.map(f=><details key={f.fact_id}><summary>{f.fact_id.replaceAll('_',' ')} · {money(f.value_minor)}</summary>{f.source_ids.map(id=><code className="source-code" key={id}>{id}</code>)}</details>)}</div>{m.result.proposal&&<button onClick={()=>void onProposal()}>Open payment review</button>}<details><summary>Response limits</summary>{m.result.limitations.map((v,i)=><p key={i}>{v}</p>)}</details></>}</article>)}{busy&&<p role="status" className="chat-thinking">Reviewing your question<span aria-hidden="true">…</span></p>}</div>
 {mode==='ai'&&<details className="chat-permission" open={!consent||!provider?.configured}><summary>External AI settings{provider?' · '+provider.provider_name:''}</summary>{statusError?<p className="error" role="alert">{statusError} <button className="link" onClick={()=>void checkProvider()}>Retry connection</button></p>:!provider?<p role="status">Checking provider configuration…</p>:!provider.configured?<p className="notice">External AI is not configured. The private helper is available.</p>:null}<p className="small muted">Your question, recent questions and relevant financial facts go to {provider?.provider_name||'the configured provider'}. Its free service may use submissions to improve models. Share only non-confidential information.</p><label className="check"><input type="checkbox" checked={consent} disabled={busy} onChange={e=>setConsent(e.target.checked)}/>I choose to share these non-confidential details with this provider.</label><label htmlFor="agent-target">Invoice (optional)</label><select id="agent-target" value={target} disabled={busy} onChange={e=>{setTarget(e.target.value);setAllow(false);}}><option value="">Cash-flow questions</option>{invoices.filter(i=>i.status==='open').map(i=><option key={i.invoice_id} value={i.invoice_id}>{i.invoice_number} · {money(i.amount_minor)}</option>)}</select><label className="check"><input type="checkbox" checked={allow} disabled={!target||session.role==='viewer'||busy} onChange={e=>setAllow(e.target.checked)}/>Allow a proposal for this invoice; another person must approve.</label></details>}
 {error&&<p className="error chat-error" role="alert">{error} Your question is preserved for retry. You can also use the private helper.</p>}
 <form className="chat-compose" onSubmit={e=>void ask(e)}><label htmlFor="agent-task" className="sr-only">Message assistant</label><textarea ref={input} id="agent-task" rows={2} placeholder="Ask about your workspace…" maxLength={1400} value={task} disabled={busy} onChange={e=>setTask(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><button disabled={busy||!task.trim()||!snapshot||(mode==='ai'&&(!consent||!provider?.configured))} aria-label="Send message">{busy?'…':'↑'}</button></form><p className="chat-footnote">{mode==='private'?'Rule-based help · no external AI call':'No bank transfers · no paid fallback'} · Enter to send</p></section>;
}
