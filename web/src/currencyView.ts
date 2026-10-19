import {currencyDigits} from './api';
import {currencies} from './currencies';

export type CurrencyView = {base:string;currency:string;rate:string;updatedAt:string;source?:'live'|'manual';provider?:string;stale?:boolean};
const supported = new Set<string>(currencies.map(c=>c.code));
// A rate is target major units per one source major unit. Never infer a rate.
export function parseRate(text:string):{numerator:bigint;denominator:bigint} {
  if(!/^\d{1,9}(\.\d{1,12})?$/.test(text))throw new Error('Enter a positive exchange rate, with up to 12 decimal places.');
  const [whole,fraction='']=text.split('.');
  const numerator=BigInt(whole+fraction),denominator=10n**BigInt(fraction.length);
  if(numerator===0n)throw new Error('The exchange rate must be greater than zero.');
  return {numerator,denominator};
}
export function convertMinor(amount:number,base:string,target:string,rate:string):bigint {
  if(!Number.isSafeInteger(amount)||!supported.has(base)||!supported.has(target))throw new Error('Invalid currency amount.');
  const {numerator,denominator}=parseRate(rate);
  const source=BigInt(amount),negative=source<0n;
  const n=(negative?-source:source)*numerator*10n**BigInt(currencyDigits(target));
  const d=denominator*10n**BigInt(currencyDigits(base));
  const rounded=(n+d/2n)/d; // Half away from zero, once, at the display boundary.
  return negative?-rounded:rounded;
}
export function formatConverted(amount:bigint,currency:string):string {
  const digits=currencyDigits(currency),factor=10n**BigInt(digits),abs=amount<0n?-amount:amount;
  const whole=abs/factor,negative=amount<0n;
  const parts=new Intl.NumberFormat(undefined,{style:'currency',currency,currencyDisplay:'code',minimumFractionDigits:digits,maximumFractionDigits:digits}).formatToParts(negative?(whole===0n?-0:-whole):whole);
  return parts.map(p=>p.type==='fraction'?(abs%factor).toString().padStart(digits,'0'):p.value).join('');
}
export function readCurrencyView(key:string):CurrencyView|null {
  try {
    const v=JSON.parse(localStorage.getItem(key)||'null');
    if(!v||!supported.has(v.base)||!supported.has(v.currency)||typeof v.rate!=='string'||typeof v.updatedAt!=='string'||!Number.isFinite(Date.parse(v.updatedAt)))return null;
    parseRate(v.rate);return {base:v.base,currency:v.currency,rate:v.rate,updatedAt:v.updatedAt,source:v.source==='live'?'live':'manual',provider:typeof v.provider==='string'?v.provider.slice(0,60):undefined,stale:v.stale===true};
  } catch {return null;}
}
