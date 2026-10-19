import {createContext,useContext,useEffect,useRef,useState,type ReactNode} from 'react';
import {money,parseMinor,currencyDigits} from './api';
import {currencies} from './currencies';
import {convertMinor,formatConverted,parseRate,readCurrencyView,type CurrencyView} from './currencyView';
import type {FxRate} from './types';
import {t} from './i18n';

type FetchRate=(from:string,to:string)=>Promise<FxRate>;
type Preferred={code:string;rate:string}|null;
type CurrencyState={currency:string;view:CurrencyView|null;saveView:(view:CurrencyView|null)=>void;fetchRate?:FetchRate;preferred:Preferred;setPreferredCode:(code:string)=>void};
const CurrencyContext=createContext<CurrencyState>({currency:'BDT',view:null,saveView:()=>{},preferred:null,setPreferredCode:()=>{}});
const HOUR=3600_000;
export function CurrencyProvider({currency,storageKey,fetchRate,children}:{currency:string;storageKey:string;fetchRate?:FetchRate;children:ReactNode}){
 const [view,setView]=useState<CurrencyView|null>(()=>readCurrencyView(storageKey));
 function saveView(next:CurrencyView|null){setView(next);try{if(next)localStorage.setItem(storageKey,JSON.stringify(next));else localStorage.removeItem(storageKey);}catch{/* Currency selection still works when browser storage is unavailable. */}}
 // The person's chosen conversion currency (USD until they pick another) shown as a small approximate value next to key figures.
 const [code,setCode]=useState('USD');const [preferred,setPreferred]=useState<Preferred>(null);
 const fetchRef=useRef(fetchRate);fetchRef.current=fetchRate;const canFetch=!!fetchRate;
 useEffect(()=>{
  setPreferred(null);
  if(!canFetch||!code||code===currency)return;
  const cacheKey=`safeledger-pref-rate-v1:${currency}:${code}`;let cancelled=false;
  try{const raw=localStorage.getItem(cacheKey);if(raw){const c=JSON.parse(raw) as {rate:string;at:number};if(Date.now()-c.at<HOUR&&typeof c.rate==='string'){parseRate(c.rate);setPreferred({code,rate:c.rate});return;}}}catch{/* cache is optional */}
  void fetchRef.current!(currency,code).then(r=>{if(cancelled)return;parseRate(r.rate);setPreferred({code,rate:r.rate});try{localStorage.setItem(cacheKey,JSON.stringify({rate:r.rate,at:Date.now()}));}catch{/* optional */}}).catch(()=>{});
  return()=>{cancelled=true;};
 },[currency,code,canFetch]);
 return <CurrencyContext.Provider value={{currency,view:view?.base===currency?view:null,saveView,fetchRate,preferred,setPreferredCode:setCode}}>{children}</CurrencyContext.Provider>;
}
export function usePreferredCurrency(){return useContext(CurrencyContext).setPreferredCode;}
export function useCurrency(){
 const {currency,view,preferred}=useContext(CurrencyContext);
 const converted=view&&view.currency!==currency;
 return {currency,digits:currencyDigits(currency),displayCurrency:converted?view.currency:currency,
 money:(n:number)=>converted?'≈ '+formatConverted(convertMinor(n,currency,view.currency,view.rate),view.currency):money(n,currency),
 nativeMoney:(n:number)=>money(n,currency),parseMinor:(text:string)=>parseMinor(text,currency),
 approx:(n:number):string|null=>!converted&&preferred?'≈ '+formatConverted(convertMinor(n,currency,preferred.code,preferred.rate),preferred.code):null};
}
const clock=(iso:string)=>{const d=new Date(iso);return Number.isNaN(d.getTime())?'':d.toLocaleString(document.documentElement.lang&&document.documentElement.lang!=='en'?document.documentElement.lang:undefined,{dateStyle:'medium',timeStyle:'short'});};
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
  }catch(e){if(alive.current&&!silent){setError((e instanceof Error?e.message:t('Live rates are unavailable.'))+' '+t('You can enter a rate yourself.'));setManual(true);setRate(view?.currency===code?view.rate:'');}return false;}
  finally{if(alive.current&&!silent)setLoading(false);}
 }
 // Keep a live rate fresh: refresh quietly when it is more than an hour old.
 useEffect(()=>{if(view&&view.currency!==currency&&view.source==='live'&&Date.now()-Date.parse(view.updatedAt||'')>HOUR*2){void live(view.currency,true);}},[view?.currency,view?.base]);// eslint-disable-line react-hooks/exhaustive-deps
 const converted=view&&view.currency!==currency;
 return <section className="currency-controls" aria-label={t('Currency preferences')}>
  <div><label htmlFor="view-currency">{t('Show amounts in')}</label>
   <CurrencySelect id="view-currency" value={target} disabled={!ready||loading} onChange={code=>{setTarget(code);setError('');setManual(false);if(code===currency){saveView(null);return;}void live(code);}}/></div>
  {loading&&<p role="status">{t('Getting today’s exchange rate…')}</p>}
  {!loading&&manual&&target!==currency&&<form onSubmit={e=>{e.preventDefault();try{parseRate(rate);saveView({base:currency,currency:target,rate,updatedAt:new Date().toISOString(),source:'manual'});setManual(false);setError('');}catch(err){setError(err instanceof Error?err.message:'Invalid rate.');}}}>
   <label htmlFor="view-currency-rate">1 {currency} = {target}<input id="view-currency-rate" inputMode="decimal" autoComplete="off" required value={rate} onChange={e=>setRate(e.target.value)} placeholder={t('Your exchange rate')}/></label>
   <button>{t('Use my rate')}</button><button type="button" className="secondary" onClick={()=>{setManual(false);setTarget(view?.currency||currency);setError('');}}>{t('Cancel')}</button></form>}
  {!loading&&!manual&&converted&&<p>{t('≈ Converted to {to} · 1 {from} = {rate} {to}',{to:view.currency,from:currency,rate:view.rate.replace(/(\.\d*?[1-9])0+$|\.0+$/,'$1')})}
   <small>{view.source==='live'?`${t('Live rate')}${view.provider?' · '+view.provider:''} · ${clock(view.updatedAt)}${view.stale?' · '+t('latest available'):''}`:t('Your own rate · not a live quote')}</small>
   <span className="inline-actions">{view.source==='live'&&fetchRate&&<button className="link" onClick={()=>void live(view.currency)}>{t('Refresh rate')}</button>}<button className="link" onClick={()=>{setManual(true);setRate(view.rate);}}>{t('Use my own rate')}</button></span></p>}
  {!loading&&!manual&&!converted&&<p>{t('Amounts are shown in {currency}, the currency of this workspace. Pick another currency to see today’s converted values.',{currency})}</p>}
  {converted&&!manual&&<p className="small muted">{t('Converted values are for reference. Your records, payments and exports stay in {currency}.',{currency})}{view.source==='live'?' '+t('Rates by Exchange Rate API.'):''}</p>}
  {error&&<p className="error" role="alert">{error}</p>}
 </section>;
}
export function CurrencySelect({value,onChange,id,disabled=false}:{value:string;onChange:(code:string)=>void;id:string;disabled?:boolean}){return <select id={id} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}>{currencies.map(c=><option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}</select>;}
