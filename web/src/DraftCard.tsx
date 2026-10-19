import {useRef,useState} from 'react';
import {currencyDigits,parseMinor} from './api';
import {slug} from './recordParser';
import {prettyVendor,todayIso} from './format';
import type {Draft} from './types';

type Props={draft:Draft;revision:string;request:<T>(path:string,body?:unknown)=>Promise<T>;onSaved:()=>Promise<void>|void;onDiscard:()=>void;compact?:boolean};
const major=(minor:number,currency:string)=>{const d=currencyDigits(currency);return (minor/10**d).toFixed(d);};

/** A suggestion read from a photo or a sentence. Nothing is saved until the owner checks it and presses Save. */
export function DraftCard({draft,revision,request,onSaved,onDiscard,compact}:Props){
  const currency=draft.workspace_currency;
  const [kind,setKind]=useState(draft.kind);
  const [amount,setAmount]=useState(major(draft.amount_minor,currency));
  const [date,setDate]=useState(draft.effective_on);const [due,setDue]=useState(draft.due_on||draft.effective_on);
  const [vendor,setVendor]=useState(draft.vendor_name||(draft.vendor_id&&draft.vendor_id!=='unknown-vendor'?prettyVendor(draft.vendor_id):''));
  const [number,setNumber]=useState(draft.invoice_number||'');const [memo,setMemo]=useState(draft.memo);
  const [direction,setDirection]=useState(draft.direction||'outflow');const [status,setStatus]=useState(draft.status||'cleared');
  const [allow,setAllow]=useState(false);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [done,setDone]=useState(false);
  const attempt=useRef<{signature:string;id:string}|null>(null);
  const today=todayIso();
  async function save(){
    setError('');
    try{
      const minor=parseMinor(amount,currency);if(minor<=0)throw new Error('Amount must be greater than zero.');
      let fields:Record<string,unknown>;
      if(kind==='invoice'){
        const id=slug(vendor);if(!id)throw new Error('Enter the supplier name.');
        if(!number.trim())throw new Error('Enter the invoice number.');
        if(date>today)throw new Error('The bill date cannot be in the future.');
        if(due<date)throw new Error('The due date cannot be before the bill date.');
        fields={kind:'invoice',amount_minor:minor,effective_on:date,vendor_id:id,invoice_number:number.trim(),due_on:due,memo:memo.slice(0,2000),trust_vendor:allow};
      }else{
        const effective=date>today&&status==='cleared'?'scheduled':status;
        fields={kind:'cash',amount_minor:minor,effective_on:date,direction,status:effective,memo:memo.slice(0,2000)};
      }
      const body={expected_revision:revision,...fields};
      const signature=JSON.stringify(body);
      if(attempt.current?.signature!==signature)attempt.current={signature,id:crypto.randomUUID()};
      setBusy(true);
      await request('/workspace/records',{...body,request_id:attempt.current.id});
      setDone(true);await onSaved();
    }catch(e){setError(e instanceof Error?e.message:'Could not save. Please check the details.');}
    finally{setBusy(false);}
  }
  if(done)return <div className="draft-card saved" role="status"><strong>✓ Added to your records.</strong><p className="small muted">It now appears in your balance, forecast and activity.</p></div>;
  return <div className={'draft-card'+(compact?' compact':'')}>
    <div className="draft-head"><strong>Check and add this</strong>{draft.confidence!==null&&<span className="badge">{draft.confidence>=0.8?'Looks clear':'Please double-check'}</span>}</div>
    {draft.warnings.map((w,i)=><p className="notice small" key={i}>{w}</p>)}
    {draft.currency_mismatch&&<p className="error small" role="alert">This looks like {draft.currency}. Switch to a {draft.currency} workspace, or type the {currency} amount below.</p>}
    <div className="form-grid">
      <label>What is it
        <select value={kind} onChange={e=>setKind(e.target.value as 'cash'|'invoice')}><option value="cash">Money paid or received</option><option value="invoice">A bill I still have to pay</option></select></label>
      <label>Amount ({currency})<input inputMode="decimal" value={amount} onChange={e=>setAmount(e.target.value)}/></label>
      {kind==='cash'?<>
        <label>Money<select value={direction} onChange={e=>setDirection(e.target.value as 'inflow'|'outflow')}><option value="outflow">Paid out</option><option value="inflow">Received</option></select></label>
        <label>Date<input type="date" value={date} onChange={e=>setDate(e.target.value)}/></label>
        <label>Status<select value={status} onChange={e=>setStatus(e.target.value as 'cleared'|'scheduled')}><option value="cleared">Already happened</option><option value="scheduled">Planned</option></select></label>
      </>:<>
        <label>Supplier<input value={vendor} onChange={e=>setVendor(e.target.value)} maxLength={80}/></label>
        <label>Invoice number<input value={number} onChange={e=>setNumber(e.target.value)} maxLength={80}/></label>
        <label>Bill date<input type="date" max={today} value={date} onChange={e=>setDate(e.target.value)}/></label>
        <label>Due date<input type="date" min={date} value={due} onChange={e=>setDue(e.target.value)}/></label>
      </>}
    </div>
    <label>Note<input value={memo} maxLength={200} onChange={e=>setMemo(e.target.value)}/></label>
    {kind==='invoice'&&<label className="check"><input type="checkbox" checked={allow} onChange={e=>setAllow(e.target.checked)}/>Allow payments to this supplier (a second person must still approve each one).</label>}
    {error&&<p className="error" role="alert">{error}</p>}
    <div className="actions"><button disabled={busy} onClick={()=>void save()}>{busy?'Saving…':'Add to my records'}</button><button className="secondary" disabled={busy} onClick={onDiscard}>Discard</button></div>
  </div>;
}
