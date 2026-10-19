import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from 'react';
import {money,parseMinor,currencyDigits} from './api';
import {currencies} from './currencies';
import {convertMinor,formatConverted,parseRate,readCurrencyView,type CurrencyView} from './currencyView';
import type {FxRate} from './types';

type FetchRate=(from:string,to:string)=>Promise<FxRate>;
type CurrencyState={currency:string;view:CurrencyView|null;saveView:(view:CurrencyView|null)=>void;fetchRate?:FetchRate};
const CurrencyContext=createContext<CurrencyState>({currency:'BDT',view:null,saveView:()=>{}});
const HOUR=3600_000;
export function CurrencyProvider({currency,storageKey,fetchRate,children}:{currency:string;storageKey:string;fetchRate?:FetchRate;children:ReactNode}){
 const [view,setView]=useState<CurrencyView|null>(()=>readCurrencyView(storageKey));
 function saveView(next:CurrencyView|null){setView(next);try{if(next)localStorage.setItem(storageKey,JSON.stringify(next));else localStorage.removeItem(storageKey);}catch{/* Currency selection still works when browser storage is unavailable. */}}
 return <CurrencyContext.Provider value={{currency,view:view?.base===currency?view:null,saveView,fetchRate}}>{children}</CurrencyContext.Provider>;
}
export function useCurrency(){
 const {currency,view}=useContext(CurrencyContext);
 const converted=view&&view.currency!==currency;
 return {currency,digits:currencyDigits(currency),displayCurrency:converted?view.currency:currency,
 money:(n:number)=>converted?'≈ '+formatConverted(convertMinor(n,currency,view.currency,view.rate),view.currency):money(n,currency),
 nativeMoney:(n:number)=>money(n,currency),parseMinor:(text:string)=>parseMinor(text,currency)};
}
const clock=(iso:string)=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'':d.toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'});};
export function CurrencyControls({ready}:{ready:boolean}){
 const {currency,view,saveView,fetchRate}=useContext(CurrencyContext);
 const [target,setTarget]=useState(view?.currency||currency);
 const [manual,setManual]=useState(false);const [rate,setRate]=useState('');const [error,setError]=useState('');const [loading,setLoading]=useState(false);
 const alive=useRef(true);useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 async function live(code:string,silent=false){
  if(!fetchRate)return false;
  if(!silent){setLoading(true);setError('');}
  try{
   const r=await fetchRate(currency,code);if(!alive.current)return true;
   parseRate(r.rate);
   saveView({base:currency,currency:code,rate:r.rate,updatedAt:r.as_of||new Date().toISOString(),source:'live',provider:r.provider,stale:r.stale});setManual(false);return true;
  }catch(e){if(alive.current&&!silent){setError((e instanceof Error?e.message:'Live rates are unavailable.')+' You can enter a rate yourself.');setManual(true);setRate(view?.currency===code?view.rate:'');}return false;}
  finally{if(alive.current&&!silent)setLoading(false);}
 }
 // Keep a live rate fresh: refresh quietly when it is more than an hour old.
 useEffect(()=>{if(view&&view.currency!==currency&&view.source==='live'&&Date.now()-Date.parse(view.updatedAt||'')>HOUR*2){void live(view.currency,true);}},[view?.currency,view?.base]);// eslint-disable-line react-hooks/exhaustive-deps
 const converted=view&&view.currency!==currency;
 return <section className="currency-controls" aria-label="Currency preferences">
  <div><label htmlFor="view-currency">Show amounts in</label>
   <CurrencySelect id="view-currency" value={target} disabled={!ready||loading} onChange={code=>{setTarget(code);setError('');setManual(false);if(code===currency){saveView(null);return;}void live(code);}}/></div>
  {loading&&<p role="status">Getting today’s exchange rate…</p>}
  {!loading&&manual&&target!==currency&&<form onSubmit={e=>{e.preventDefault();try{parseRate(rate);saveView({base:currency,currency:target,rate,updatedAt:new Date().toISOString(),source:'manual'});setManual(false);setError('');}catch(err){setError(err instanceof Error?err.message:'Invalid rate.');}}}>
   <label htmlFor="view-currency-rate">1 {currency} = {target}<input id="view-currency-rate" inputMode="decimal" autoComplete="off" required value={rate} onChange={e=>setRate(e.target.value)} placeholder="Your exchange rate"/></label>
   <button>Use my rate</button><button type="button" className="secondary" onClick={()=>{setManual(false);setTarget(view?.currency||currency);setError('');}}>Cancel</button></form>}
  {!loading&&!manual&&converted&&<p>≈ Converted to {view.currency} · 1 {currency} = {view.rate.replace(/(\.\d*?[1-9])0+$|\.0+$/,'$1')} {view.currency}
   <small>{view.source==='live'?`Live rate${view.provider?' from '+view.provider:''} · ${clock(view.updatedAt)}${view.stale?' · latest available':''}`:'Your own rate · not a live quote'}</small>
   <span className="inline-actions">{view.source==='live'&&fetchRate&&<button className="link" onClick={()=>void live(view.currency)}>Refresh rate</button>}<button className="link" onClick={()=>{setManual(true);setRate(view.rate);}}>Use my own rate</button></span></p>}
  {!loading&&!manual&&!converted&&<p>Amounts are shown in {currency}, the currency of this workspace. Pick another currency to see today’s converted values.</p>}
  {converted&&!manual&&<p className="small muted">Converted values are for reference. Your records, payments and exports stay in {currency}.{view.source==='live'?' Rates by Exchange Rate API.':''}</p>}
  {error&&<p className="error" role="alert">{error}</p>}
 </section>;
}
export function CurrencySelect({value,onChange,id,disabled=false}:{value:string;onChange:(code:string)=>void;id:string;disabled?:boolean}){return <select id={id} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}>{currencies.map(c=><option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}</select>;}
