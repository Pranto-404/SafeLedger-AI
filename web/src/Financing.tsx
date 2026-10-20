import {useEffect,useState,type FormEvent} from 'react';
import {useCurrency} from './Currency';
import type {FinancingMatch,LenderQuote,Session,Snapshot,Forecast} from './types';
import {t,T} from './i18n';

const products:Record<LenderQuote['product_type'],string>={term_loan:T('Term loan'),working_capital_line:T('Working-capital line'),invoice_financing:T('Invoice financing'),equipment_loan:T('Equipment loan'),other:T('Other financing')};
const statuses:Record<string,string>={FITS_CASH_FLOW:T('Fits cash flow'),DOES_NOT_COVER_SHORTFALL:T('Does not cover shortfall'),REPAYMENT_BREACHES_RESERVE:T('Repayment breaches reserve'),VERIFY_TERMS_WITH_LENDER:T('Verify terms with lender')};
const warnings:Record<string,string>={QUOTE_OLDER_THAN_30_DAYS:T('Quote is more than 30 days old; ask the lender to reconfirm.'),FLAT_RATE_UNDERSTATES_EFFECTIVE_COST:T('Flat rate on installments: the effective annual cost is much higher than the quoted rate.'),HIGH_COST_FINANCING:T('High-cost financing: estimated effective annual rate above 36%.'),BORROWS_MORE_THAN_NEEDED:T('Proceeds exceed the projected need by more than 50%; consider a smaller amount.')};
const pct=(bps:number)=>(bps/100).toFixed(2)+'%';
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Dhaka',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
function parseRate(text:string){
  if(!/^\d{1,3}(\.\d{1,2})?$/.test(text.trim()))throw new Error('Enter the quoted rate as a percentage with at most two decimals, e.g. 12.5');
  const [whole,fraction='']=text.trim().split('.');const bps=Number(whole)*100+Number(fraction.padEnd(2,'0'));
  if(bps>20000)throw new Error('Rates above 200% are not supported. Check the quote.');
  return bps;
}
const kinds=['term_loan','working_capital_line','invoice_financing','equipment_loan','other'];
const intIn=(v:unknown,lo:number,hi:number)=>typeof v==='number'&&Number.isInteger(v)&&v>=lo&&v<=hi;
const text=(v:unknown,max:number)=>typeof v==='string'&&v.length>0&&v.length<=max;
function validQuote(q:unknown):q is LenderQuote{
  if(!q||typeof q!=='object')return false;const x=q as Record<string,unknown>;
  return text(x.quote_id,80)&&text(x.lender_name,100)&&kinds.includes(x.product_type as string)&&text(x.currency,3)&&intIn(x.principal_minor,1,10**12)&&intIn(x.upfront_fee_minor,0,10**12)&&(x.rate_type==='flat_per_term'||x.rate_type==='annual_reducing')&&intIn(x.rate_bps,0,20000)&&(x.repayment==='single_payment'||x.repayment==='equal_installments')&&intIn(x.installments,1,60)&&intIn(x.term_days,1,1825)&&text(x.quote_source,200)&&typeof x.quoted_on==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(x.quoted_on);
}
// Session storage: quotes are private business data and should not outlive the browser tab.
function load(key:string):LenderQuote[]{try{const v=JSON.parse(sessionStorage.getItem(key)||'[]');return Array.isArray(v)?v.filter(validQuote).slice(0,10):[];}catch{return [];}}

export function Financing({snapshot,forecast,session,request}:{snapshot:Snapshot|null;forecast:Forecast|null;session:Session;request:<T>(path:string,body?:unknown)=>Promise<T>}){
  const {currency,digits,parseMinor,nativeMoney:money}=useCurrency();
  const key=`safeledger-financing-quotes-v1:${session.user_id}:${session.business_id}`;
  const [quotes,setQuotes]=useState<LenderQuote[]>(()=>load(key));
  const [result,setResult]=useState<FinancingMatch|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const [lender,setLender]=useState('');const [product,setProduct]=useState<LenderQuote['product_type']>('term_loan');
  const [amount,setAmount]=useState('');const [fee,setFee]=useState('0');const [rate,setRate]=useState('');
  const [rateType,setRateType]=useState<LenderQuote['rate_type']>('annual_reducing');const [term,setTerm]=useState('12');const [unit,setUnit]=useState<'months'|'days'>('months');
  const [repayment,setRepayment]=useState<LenderQuote['repayment']>('equal_installments');const [source,setSource]=useState('');const [quotedOn,setQuotedOn]=useState(today);
  useEffect(()=>{try{sessionStorage.setItem(key,JSON.stringify(quotes));}catch{/* Quotes still work for this session. */}},[key,quotes]);
  // An imported workspace can be dated before today; quotes cannot postdate its snapshot.
  useEffect(()=>{if(snapshot&&quotedOn>snapshot.as_of)setQuotedOn(snapshot.as_of);},[snapshot,quotedOn]);
  const canAnalyze=session.role==='owner'||session.role==='approver';
  const shortfall=forecast&&forecast.first_shortfall_on;
  function add(e:FormEvent){e.preventDefault();setError('');try{
    const length=Number(term);if(!Number.isInteger(length)||length<1)throw new Error('Enter a whole-number term.');
    const term_days=unit==='months'?length*30:length;if(term_days>1825)throw new Error('Terms up to five years are supported.');
    if(repayment==='equal_installments'&&unit!=='months')throw new Error('Monthly installments need a term in months.');
    if(repayment==='equal_installments'&&length>60)throw new Error('Up to 60 monthly installments are supported.');
    const principal_minor=parseMinor(amount);if(principal_minor<=0)throw new Error('Amount must be greater than zero.');
    const upfront_fee_minor=parseMinor(fee||'0');if(upfront_fee_minor>=principal_minor)throw new Error('Fees must be less than the amount.');
    if(quotes.length>=10)throw new Error('Compare up to 10 quotes at a time. Remove one first.');
    const quote:LenderQuote={quote_id:'quote-'+crypto.randomUUID().slice(0,8),lender_name:lender.trim(),product_type:product,currency,principal_minor,upfront_fee_minor,rate_type:rateType,rate_bps:parseRate(rate),repayment,installments:repayment==='equal_installments'?length:1,term_days,quote_source:source.trim(),quoted_on:quotedOn};
    setQuotes([...quotes,quote]);setResult(null);setLender('');setAmount('');setFee('0');setRate('');setSource('');
  }catch(err){setError(err instanceof Error?err.message:'Check the quote details.');}}
  async function analyze(){if(!snapshot||busy)return;setBusy(true);setError('');try{
    const valid=quotes.filter(q=>q.currency===currency);
    if(valid.length!==quotes.length)throw new Error('Some saved quotes use a different currency. Remove them first.');
    setResult(await request<FinancingMatch>('/financing/match',{as_of:snapshot.as_of,quotes:valid}));
  }catch(err){setError(err instanceof Error?err.message:'Analysis failed. Refresh and retry.');}finally{setBusy(false);}}
  const best=result?.quotes.find(q=>q.quote_id===result.best_match_quote_id);
  return <>
    <section className="panel"><span className="badge">{t('YOUR QUOTES · NO LENDER CONNECTION')}</span><h2>{t('Match financing to your cash flow')}</h2>
      <p>{t('Enter real offers you received from banks, NBFIs or lenders. Capzoryx Copilot computes every repayment exactly, converts each offer to an estimated effective annual cost, and tests it against your recorded cash flow and reserve. It does not apply for credit or check eligibility.')}</p>
      {forecast&&<div className="metrics"><article className="metric"><p>{t('Lowest projected balance · 30 days')}</p><strong className={forecast.minimum_balance_minor<0?'negative':''}>{money(forecast.minimum_balance_minor)}</strong></article><article className="metric"><p>{t('First reserve breach')}</p><strong>{shortfall||t('None')}</strong><small>{shortfall?t('Financing may bridge this gap'):t('No projected gap; borrowing is optional')}</small></article><article className="metric"><p>{t('Quotes to compare')}</p><strong>{quotes.length}</strong><small>{t('Up to 10')}</small></article></div>}
    </section>
    <section className="panel"><h2>{t('Add a lender quote')}</h2>{!canAnalyze?<p className="notice">{t('Viewers can read results. Ask the owner or approver to enter quotes.')}</p>:<form onSubmit={add}><div className="form-grid">
      <label>{t('Lender')}<input required maxLength={100} value={lender} onChange={e=>setLender(e.target.value)} placeholder={t('e.g. City Bank SME desk')}/></label>
      <label>{t('Product')}<select value={product} onChange={e=>setProduct(e.target.value as LenderQuote['product_type'])}>{Object.entries(products).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
      <label>{t('Amount ({currency})',{currency})}<input required inputMode="decimal" value={amount} onChange={e=>setAmount(e.target.value)} placeholder={digits?'e.g. 500000.'+'0'.repeat(digits):'e.g. 500000'}/></label>
      <label>{t('Upfront fees ({currency})',{currency})}<input inputMode="decimal" value={fee} onChange={e=>setFee(e.target.value)}/></label>
      <label>{t('Quoted rate (%)')}<input required inputMode="decimal" value={rate} onChange={e=>setRate(e.target.value)} placeholder={t('e.g. 12.5')}/></label>
      <label>{t('Rate basis')}<select value={rateType} onChange={e=>setRateType(e.target.value as LenderQuote['rate_type'])}><option value="annual_reducing">{t('Per year, on reducing balance')}</option><option value="flat_per_term">{t('Flat, for the whole term')}</option></select></label>
      <label>{t('Term')}<span className="inline-fields"><input required inputMode="numeric" value={term} onChange={e=>setTerm(e.target.value)} aria-label={t('Term length')}/><select value={unit} onChange={e=>setUnit(e.target.value as 'months'|'days')} aria-label={t('Term unit')}><option value="months">{t('months')}</option><option value="days">{t('days')}</option></select></span></label>
      <label>{t('Repayment')}<select value={repayment} onChange={e=>setRepayment(e.target.value as LenderQuote['repayment'])}><option value="equal_installments">{t('Equal monthly installments')}</option><option value="single_payment">{t('One payment at the end')}</option></select></label>
      <label>{t('Quote source')}<input required minLength={3} maxLength={200} value={source} onChange={e=>setSource(e.target.value)} placeholder={t('e.g. Offer letter ref. 2026/114, branch email')}/></label>
      <label>{t('Quoted on')}<input type="date" required max={snapshot?.as_of} value={quotedOn} onChange={e=>setQuotedOn(e.target.value)}/></label>
    </div><button className="secondary">{t('Add quote')}</button></form>}
      {error&&<p className="error" role="alert">{error}</p>}
      {!!quotes.length&&<div className="table-wrap" tabIndex={0} role="region" aria-label={t('Scrollable table')}><table><caption>{t('Quotes entered in this browser')}</caption><thead><tr><th>{t('Lender')}</th><th>{t('Amount / fees')}</th><th>{t('Rate')}</th><th>{t('Term')}</th><th></th></tr></thead><tbody>{quotes.map(q=><tr key={q.quote_id}><td><strong>{q.lender_name}</strong><small>{t(products[q.product_type])} · {q.quote_source} · {q.quoted_on}</small></td><td className="amount">{money(q.principal_minor)}<small>fees {money(q.upfront_fee_minor)}</small></td><td>{pct(q.rate_bps)}<small>{q.rate_type==='flat_per_term'?'flat for term':'per year, reducing'}</small></td><td>{q.repayment==='equal_installments'?`${q.installments} monthly`:`${q.term_days} days, one payment`}</td><td><button className="secondary small" disabled={busy} onClick={()=>{setQuotes(quotes.filter(x=>x.quote_id!==q.quote_id));setResult(null);}} aria-label={`Remove quote from ${q.lender_name}`}>{t('Remove')}</button></td></tr>)}</tbody></table></div>}
      {canAnalyze&&<button disabled={busy||!quotes.length||!snapshot} onClick={()=>void analyze()}>{busy?t('Matching…'):t('Match quotes to my cash flow')}</button>}
      <p className="small muted">{t('Quotes are kept only in this browser for this workspace. Each analysis is recorded as a signed audit event; your ledger is not changed.')}</p>
    </section>
    {result&&<section className="panel" aria-live="polite"><h2>{t('Financing match')}</h2>
      <div className="metrics"><article className="metric"><p>{t('Projected funding need')}</p><strong>{money(result.funding_need_minor)}</strong><small>{result.baseline_first_shortfall_on?`Reserve breach from ${result.baseline_first_shortfall_on}`:t('No breach in 30 days')}</small></article><article className="metric"><p>{t('Reserve kept')}</p><strong>{money(result.reserve_minor)}</strong></article><article className="metric"><p>{t('Lowest effective rate')}</p><strong>{pct(Math.min(...result.quotes.map(q=>q.effective_annual_rate_bps)))}</strong></article></div>
      {best?<p className="success"><strong>Best match: {best.lender_name}.</strong> Net proceeds {money(best.net_proceeds_minor)}, total cost {money(best.total_cost_minor)}, estimated effective annual rate {pct(best.effective_annual_rate_bps)}. {result.funding_need_minor?t('It covers the projected shortfall and'):'It'} keeps your balance at or above the reserve through the last repayment (lowest {money(best.lowest_balance_with_financing_minor)}).</p>:<p className="notice">No quote both covers the need and keeps your balance above the reserve during repayment. Ask for a longer term, a larger amount or lower fees, or record expected receipts first.</p>}
      <div className="table-wrap" tabIndex={0} role="region" aria-label={t('Scrollable table')}><table className="wrap-cells"><caption>{t('Quotes ranked by cash-flow fit, then total cost')}</caption><thead><tr><th>#</th><th>{t('Lender and result')}</th><th>{t('Net proceeds')}</th><th>{t('Total cost')}</th><th>{t('Quoted → effective rate')}</th><th>{t('Lowest balance in term')}</th></tr></thead><tbody>{result.quotes.map((q,n)=><tr key={q.quote_id}><td>{n+1}</td><td><strong>{q.lender_name}</strong><small>{products[q.product_type as LenderQuote['product_type']]||q.product_type} · {q.quote_source}</small><span className="badge">{t(statuses[q.status]||'')||q.status}</span>{q.warnings.map(w=><small key={w}>{t(warnings[w]||"")||w}</small>)}{q.additional_receipts_needed_minor>0&&<small>Needs {money(q.additional_receipts_needed_minor)} more recorded receipts</small>}<details><summary>Repayment schedule · {q.schedule.length}</summary><ul className="notes">{q.schedule.map(s=><li key={s.date}>{s.date}: {money(s.payment_minor)} (interest {money(s.interest_minor)})</li>)}</ul></details></td><td className="amount">{money(q.net_proceeds_minor)}</td><td className="amount">{money(q.total_cost_minor)}<small>interest {money(q.interest_minor)} + fees {money(q.upfront_fee_minor)}</small></td><td>{pct(q.rate_bps)} {q.rate_type==='flat_per_term'?'flat':'p.a.'} → <strong>{pct(q.effective_annual_rate_bps)}</strong></td><td className={q.lowest_balance_with_financing_minor<result.reserve_minor?'negative':''}>{money(q.lowest_balance_with_financing_minor)}{q.first_reserve_breach_on&&<small>breach {q.first_reserve_breach_on}</small>}</td></tr>)}</tbody></table></div>
      <p className="small muted">{t('Based on {count} of your records. This comparison is saved in your activity log.',{count:result.source_ids.length})}</p>
      <ul className="notes">{result.assumptions.map((a,i)=><li key={i}>{a}</li>)}</ul>
    </section>}
  </>;
}
