import {createContext,useContext,useState,type ReactNode} from 'react';
import {money,parseMinor,currencyDigits} from './api';
import {currencies} from './currencies';
import {convertMinor,formatConverted,parseRate,readCurrencyView,type CurrencyView} from './currencyView';

type CurrencyState={currency:string;view:CurrencyView|null;saveView:(view:CurrencyView|null)=>void};
const CurrencyContext=createContext<CurrencyState>({currency:'BDT',view:null,saveView:()=>{}});
export function CurrencyProvider({currency,storageKey,children}:{currency:string;storageKey:string;children:ReactNode}){
 const [view,setView]=useState<CurrencyView|null>(()=>readCurrencyView(storageKey));
 function saveView(next:CurrencyView|null){setView(next);try{if(next)localStorage.setItem(storageKey,JSON.stringify(next));else localStorage.removeItem(storageKey);}catch{/* Currency selection still works when browser storage is unavailable. */}}
 return <CurrencyContext.Provider value={{currency,view:view?.base===currency?view:null,saveView}}>{children}</CurrencyContext.Provider>;
}
export function useCurrency(){
 const {currency,view}=useContext(CurrencyContext);
 const converted=view&&view.currency!==currency;
 return {currency,digits:currencyDigits(currency),displayCurrency:converted?view.currency:currency,
 money:(n:number)=>converted?'≈ '+formatConverted(convertMinor(n,currency,view.currency,view.rate),view.currency):money(n,currency),
 nativeMoney:(n:number)=>money(n,currency),parseMinor:(text:string)=>parseMinor(text,currency)};
}
export function CurrencyControls({ready}:{ready:boolean}){
 const {currency,view,saveView}=useContext(CurrencyContext);
 const [pending,setPending]=useState('');const [rate,setRate]=useState('');const [error,setError]=useState('');
 const target=pending||view?.currency||currency;
 const editing=!!pending&&pending!==currency;
 return <section className="currency-controls" aria-label="Currency preferences"><div><label htmlFor="view-currency">View currency</label><CurrencySelect id="view-currency" value={target} disabled={!ready} onChange={code=>{setError('');setPending(code===currency?'':code);setRate(view?.currency===code?view.rate:'');if(code===currency)saveView(null);}}/></div>{editing?<form onSubmit={e=>{e.preventDefault();try{parseRate(rate);saveView({base:currency,currency:target,rate,updatedAt:new Date().toISOString()});setPending('');setError('');}catch(e){setError(e instanceof Error?e.message:'Invalid rate.');}}}><label htmlFor="view-currency-rate">1 {currency} = {target}<input id="view-currency-rate" inputMode="decimal" autoComplete="off" required value={rate} onChange={e=>setRate(e.target.value)} placeholder="Enter your exchange rate"/></label><button>Apply rate</button><button type="button" className="secondary" onClick={()=>{setPending('');setError('');}}>Cancel</button></form>:view&&view.currency!==currency?<p>≈ Converted view · 1 {currency} = {view.rate} {view.currency}<small>Your rate · {new Date(view.updatedAt).toLocaleDateString()} · not a live quote</small><button className="link" onClick={()=>{setPending(view.currency);setRate(view.rate);}}>Edit rate</button></p>:<p>Original amounts in {currency}. Change the view at any time.</p>}{editing&&<p className="small muted">Until you apply a rate, figures stay in {view?.currency||currency}. Original records, new entries, approvals and exports stay in {currency}.</p>}{!editing&&view&&view.currency!==currency&&<p className="small muted">Entries, approvals, exports and assistant facts use original {currency}. Conversion is for reference only.</p>}{error&&<p className="error" role="alert">{error}</p>}</section>;
}
export function CurrencySelect({value,onChange,id,disabled=false}:{value:string;onChange:(code:string)=>void;id:string;disabled?:boolean}){return <select id={id} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}>{currencies.map(c=><option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}</select>;}
