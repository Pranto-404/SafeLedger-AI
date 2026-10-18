import {createContext,useContext,type ReactNode} from 'react';
import {money,parseMinor,currencyDigits} from './api';
import {currencies} from './currencies';
const CurrencyContext=createContext('BDT');
export function CurrencyProvider({currency,children}:{currency:string;children:ReactNode}){return <CurrencyContext.Provider value={currency}>{children}</CurrencyContext.Provider>;}
export function useCurrency(){const currency=useContext(CurrencyContext);return {currency,digits:currencyDigits(currency),money:(n:number)=>money(n,currency),parseMinor:(text:string)=>parseMinor(text,currency)};}
export function CurrencySelect({value,onChange,id,disabled=false}:{value:string;onChange:(code:string)=>void;id:string;disabled?:boolean}){return <select id={id} value={value} onChange={e=>onChange(e.target.value)} disabled={disabled}>{currencies.map(c=><option key={c.code} value={c.code}>{c.code} — {c.name}</option>)}</select>;}
