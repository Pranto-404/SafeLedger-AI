import type {Draft} from './types';

/** Reads a sentence such as "I paid Rahman 5k for freight yesterday" into a draft record. Everything here is a
 *  suggestion shown to the user for confirmation; nothing is saved until the owner presses Save. */
const BN='০১২৩৪৫৬৭৮৯';
const ascii=(s:string)=>s.replace(/[০-৯]/g,c=>String(BN.indexOf(c)));
const IN=/\b(?:received|receive|got paid|got|earned|earn|sold|sale|sales|collected|collect|deposit(?:ed)?|income|came in|paid me|peyechi|pelam|peyesi|nilam)\b|পেয়েছি|পেলাম|বিক্রি|আয়|জমা|গ্রহণ/i;
const OUT=/\b(?:paid|pay|spent|spend|bought|buy|purchased|purchase|expense|rent|salary|wages|withdrew|gave|dilam|diyechi|disi|kinechi|kinlam)\b|দিলাম|দিয়েছি|খরচ|কিনেছি|কিনলাম|ভাড়া|বেতন|পরিশোধ/i;
const INVOICE=/\b(?:bill|invoice|payable|owe|owed|due)\b|বাকি|বিল|পাওনা/i;
const QUESTION=/\?|^(?:how|what|why|when|where|which|who|can|could|should|do|does|is|are|will|would|please explain|show|tell|list|কত|কি|কী|কেন|কিভাবে|কীভাবে)\b/i;
const MULT:Record<string,number>={k:1e3,thousand:1e3,হাজার:1e3,hajar:1e3,lakh:1e5,lac:1e5,লাখ:1e5,lakhs:1e5,crore:1e7,কোটি:1e7,m:1e6,million:1e6};
const MONTHS=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
const pad=(n:number)=>String(n).padStart(2,'0');
const iso=(d:Date)=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
const addDays=(d:Date,n:number)=>{const x=new Date(d);x.setDate(x.getDate()+n);return x;};
const title=(s:string)=>s.replace(/\s+/g,' ').trim();

function findAmount(text:string,digits:number):{minor:number;span:[number,number]}|null{
  const re=/(?:bdt|tk\.?|taka|৳|\$|€|£|usd|eur)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|হাজার|hajar|lakhs?|lac|লাখ|crore|কোটি|million|m)?\b\s*(?:taka|tk\.?|bdt|টাকা)?/gi;
  let best:{minor:number;span:[number,number];score:number}|null=null;
  for(const m of text.matchAll(re)){
    const numeric=m[1].replace(/,/g,'');
    // Skip dates (12/10/2026, 2026-10-12) and invoice-like references glued to letters.
    const before=text[(m.index??0)-1]||'',after=text[(m.index??0)+m[0].length]||'';
    if(/[\/\-]/.test(before)||/[\/\-]\d/.test(after+(text[(m.index??0)+m[0].length+1]||'')))continue;
    const value=Number(numeric)*(MULT[(m[2]||'').toLowerCase()]||1);
    if(!Number.isFinite(value)||value<=0||value>1e12)continue;
    const score=(m[2]?2:0)+(/taka|tk|bdt|৳|\$|€|£|টাকা/i.test(m[0])?3:0)+(numeric.includes(',')?1:0)+(value>=100?1:0);
    if(!best||score>best.score)best={minor:Math.round(value*10**digits),span:[m.index??0,(m.index??0)+m[0].length],score};
  }
  return best?{minor:best.minor,span:best.span}:null;
}

function findDate(text:string,today:Date):{date:string;explicit:boolean}{
  const t=text.toLowerCase();
  if(/\b(?:today|aj|আজ)\b|আজ/.test(t))return {date:iso(today),explicit:true};
  if(/\byesterday\b|গতকাল|\bgotokal\b/.test(t))return {date:iso(addDays(today,-1)),explicit:true};
  if(/\btomorrow\b|আগামীকাল|\bkal\b|কাল/.test(t)&&!/গতকাল/.test(t))return {date:iso(addDays(today,1)),explicit:true};
  const isoM=t.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/);if(isoM)return {date:isoM[0],explicit:true};
  const dmy=t.match(/\b(\d{1,2})[\/.](\d{1,2})[\/.](20\d{2})\b/);if(dmy)return {date:`${dmy[3]}-${pad(+dmy[2])}-${pad(+dmy[1])}`,explicit:true};
  const named=t.match(new RegExp(`\\b(\\d{1,2})(?:st|nd|rd|th)?\\s+(${MONTHS.join('|')})[a-z]*(?:\\s+(20\\d{2}))?\\b`));
  if(named){const y=named[3]?+named[3]:today.getFullYear();return {date:`${y}-${pad(MONTHS.indexOf(named[2])+1)}-${pad(+named[1])}`,explicit:true};}
  const named2=t.match(new RegExp(`\\b(${MONTHS.join('|')})[a-z]*\\s+(\\d{1,2})(?:st|nd|rd|th)?(?:,?\\s+(20\\d{2}))?\\b`));
  if(named2){const y=named2[3]?+named2[3]:today.getFullYear();return {date:`${y}-${pad(MONTHS.indexOf(named2[1])+1)}-${pad(+named2[2])}`,explicit:true};}
  return {date:iso(today),explicit:false};
}

function findParty(text:string,amountSpan:[number,number]):string{
  const stops=/\b(?:for|on|at|yesterday|today|tomorrow|due|by|in|of|bill|invoice|taka|tk|bdt|about|around|and|because)\b/i;
  const tail=text.slice(amountSpan[1]);
  const head=text.slice(0,amountSpan[0]);
  const named=(from:string)=>{const m=from.match(/\b(?:from|to|with|by)\s+([A-Za-zঀ-৿][\wঀ-৿&.'-]*(?:\s+[A-Za-zঀ-৿][\wঀ-৿&.'-]*){0,3})/i);if(!m)return '';return m[1].split(/\s+/).reduce<string[]>((acc,w)=>stops.test(w)||acc.length>=4?acc:[...acc,w],[]).join(' ');};
  const direct=head.match(/\b(?:paid|pay|gave|sent)\s+([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,2})\s*$/);
  return title(named(tail)||named(head)||(direct?direct[1]:''));
}

export function parseRecordSentence(raw:string,opts:{currency:string;digits:number;today?:Date}):Draft|null{
  const text=ascii(raw).replace(/\s+/g,' ').trim();
  if(text.length<4||text.length>400||QUESTION.test(text))return null;
  const inflow=IN.test(text),outflow=OUT.test(text),invoice=INVOICE.test(text);
  if(!inflow&&!outflow&&!invoice)return null;
  const amount=findAmount(text,opts.digits);
  if(!amount||amount.minor<=0)return null;
  const today=opts.today||new Date();
  const {date,explicit}=findDate(text,today);
  const todayIso=iso(today);
  const party=findParty(text,amount.span);
  const warnings:string[]=[];
  // "paid"/"gave" with a past action is cash out; "owe"/"due"/"bill" without a payment verb is an unpaid supplier bill.
  const paidAlready=/\b(?:paid|gave|dilam|diyechi|disi)\b|দিলাম|দিয়েছি|পরিশোধ/i.test(text);
  const isInvoice=invoice&&!paidAlready&&!inflow;
  const memo=title(text).slice(0,200);
  const base={ok:true,currency:opts.currency,workspace_currency:opts.currency,currency_mismatch:false,can_save:true,confidence:0.8,memo};
  if(isInvoice){
    const dueIn=text.match(/\b(?:in|within)\s+(\d{1,3})\s+days?\b/i);
    const dueOn=text.match(/\bdue\s+(?:on\s+)?(.+)$/i);
    let due=dueIn?iso(addDays(today,+dueIn[1])):dueOn?findDate(dueOn[1],today).date:'';
    const issued=date>todayIso?todayIso:date;
    if(!due||due<issued){due=iso(addDays(new Date(issued+'T00:00:00'),30));warnings.push('No due date was given, so 30 days after the bill date was used.');}
    const vendor=party;if(!vendor)warnings.push('Add the supplier name before saving.');
    return {...base,kind:'invoice',amount_minor:amount.minor,effective_on:issued,due_on:due,vendor_name:vendor,vendor_id:slug(vendor)||'unknown-vendor',invoice_number:'INV-'+issued.replaceAll('-',''),warnings:[...warnings,'No invoice number was given; one was made up from the date. Please check.']};
  }
  const direction:'inflow'|'outflow'=inflow&&!outflow?'inflow':outflow&&!inflow?'outflow':/\b(?:paid me|from)\b/i.test(text)?'inflow':'outflow';
  if(inflow&&outflow&&!/\bpaid me\b/i.test(text))warnings.push('Check the direction: it could be money in or money out.');
  const future=date>todayIso;
  if(future)warnings.push('The date is in the future, so this is saved as planned.');
  return {...base,kind:'cash',direction,status:future?'scheduled':'cleared',amount_minor:amount.minor,effective_on:date,vendor_name:party||undefined,memo:party&&!explicit?memo:memo,warnings,confidence:explicit?0.9:0.8};
}

export const slug=(name:string)=>name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,60);

/** True when a sentence looks like someone describing a transaction but the on-device parser could not read it. */
export function looksLikeTransaction(raw:string):boolean{
  const text=ascii(raw);
  return !QUESTION.test(text)&&/\d/.test(text)&&(IN.test(text)||OUT.test(text)||INVOICE.test(text));
}
