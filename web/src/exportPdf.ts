import {currencyDigits} from './api';
import {prettyVendor} from './format';
import type {CashEvent,Forecast,Invoice,Proposal,Snapshot} from './types';

export type ReportData={workspace:string;owner:string;currency:string;snapshot:Snapshot;week:Forecast|null;month:Forecast|null;invoices:Invoice[];events:CashEvent[];proposals:Proposal[]};

const PUNCT:Record<string,string>={'–':'-','—':'-','’':"'",'‘':"'",'“':'"','”':'"','…':'...','•':'-','·':'-',' ':' '};
/** The built-in PDF fonts only cover Latin text. Other scripts are replaced so the report stays readable. */
export function latin(text:string):string{
  const flat=text.replace(/[–—’‘“”…•· ]/g,c=>PUNCT[c]).replace(/[\u0000-\u001f]+/g,' ');
  const lost=[...flat].filter(c=>c.charCodeAt(0)>255).length;
  if(lost&&lost/Math.max(1,flat.length)>0.3)return '(note in another language)';
  return flat.replace(/[^ -ÿ]/g,'?').trim();
}
const fmt=(minor:number,currency:string)=>{const d=currencyDigits(currency);const sign=minor<0?'-':'';const abs=Math.abs(minor);const whole=Math.floor(abs/10**d);const frac=String(abs%10**d).padStart(d,'0');return `${sign}${currency} ${whole.toLocaleString('en-US')}${d?'.'+frac:''}`;};

export async function buildPdf(data:ReportData):Promise<Blob>{
  const [{jsPDF},autoTable]=await Promise.all([import('jspdf'),import('jspdf-autotable').then(m=>m.default)]);
  const doc=new jsPDF({unit:'pt',format:'a4'});
  const {currency,snapshot,invoices,events,proposals}=data;
  const W=doc.internal.pageSize.getWidth();const M=44;let y=0;
  const NAVY:[number,number,number]=[19,42,74],TEAL:[number,number,number]=[15,122,99];
  doc.setFillColor(...NAVY);doc.rect(0,0,W,86,'F');
  doc.setTextColor(255,255,255);doc.setFont('helvetica','bold');doc.setFontSize(22);doc.text('SafeLedger financial report',M,40);
  doc.setFont('helvetica','normal');doc.setFontSize(10.5);
  doc.text(`${latin(data.workspace)}  |  ${currency}  |  Prepared for ${latin(data.owner)}`,M,60);
  doc.text(`As of ${snapshot.as_of}  |  Generated ${new Date().toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'})}`,M,75);
  y=112;doc.setTextColor(30,40,55);
  const heading=(text:string)=>{if(y>740){doc.addPage();y=56;}doc.setFont('helvetica','bold');doc.setFontSize(13);doc.setTextColor(...TEAL);doc.text(text,M,y);y+=8;doc.setTextColor(30,40,55);};
  const table=(head:string[],body:string[][],opts:{right?:number[]}={})=>{
    autoTable(doc,{startY:y,head:[head],body:body.length?body:[[{content:'Nothing to show yet.',colSpan:head.length,styles:{textColor:[110,120,135],fontStyle:'italic'}} as never]],margin:{left:M,right:M},theme:'striped',styles:{font:'helvetica',fontSize:9,cellPadding:5},headStyles:{fillColor:NAVY,textColor:255},alternateRowStyles:{fillColor:[243,246,250]},columnStyles:Object.fromEntries((opts.right||[]).map(i=>[i,{halign:'right'}]))});
    y=((doc as unknown as {lastAutoTable:{finalY:number}}).lastAutoTable?.finalY||y)+24;
  };
  heading('Summary');
  table(['Measure','Amount'],[['Opening balance',fmt(snapshot.opening_balance_minor,currency)],['Money received (cleared)',fmt(snapshot.income_minor,currency)],['Money paid out (cleared)',fmt(snapshot.expenses_minor,currency)],['Current balance',fmt(snapshot.balance_minor,currency)]],{right:[1]});
  heading('Cash outlook');
  const f=(x:Forecast|null)=>x?[fmt(x.closing_balance_minor,currency),fmt(x.minimum_balance_minor,currency),x.first_shortfall_on||'None']:['-','-','-'];
  table(['Period','Expected balance','Lowest balance','First time below reserve'],[['Next 7 days',...f(data.week)],['Next 30 days',...f(data.month)]],{right:[1,2]});
  doc.setFont('helvetica','italic');doc.setFontSize(8.5);doc.setTextColor(110,120,135);doc.text('The outlook is a scenario built from your own records and planned items. It is not a prediction.',M,y-14);doc.setTextColor(30,40,55);y+=6;
  const open=invoices.filter(i=>i.status==='open');
  heading(`Bills to pay (${open.length})`);
  table(['Supplier','Invoice','Due','Amount'],open.slice().sort((a,b)=>a.due_on.localeCompare(b.due_on)).map(i=>[latin(prettyVendor(i.vendor_id)),latin(i.invoice_number),i.due_on+(i.due_on<snapshot.as_of?'  (overdue)':''),fmt(i.amount_minor,currency)]),{right:[3]});
  const paid=invoices.filter(i=>i.status==='paid');
  if(paid.length){heading(`Bills marked paid (${paid.length})`);table(['Supplier','Invoice','Due','Amount'],paid.map(i=>[latin(prettyVendor(i.vendor_id)),latin(i.invoice_number),i.due_on,fmt(i.amount_minor,currency)]),{right:[3]});}
  heading(`Cash activity (${events.length})`);
  table(['Date','What','Status','Amount'],events.slice().sort((a,b)=>b.effective_on.localeCompare(a.effective_on)).map(e=>[e.effective_on,latin(e.note||(e.invoice_id?'Bill payment':e.direction==='inflow'?'Money received':'Money paid out')),e.status==='cleared'?'Done':'Planned',(e.direction==='inflow'?'+ ':'- ')+fmt(e.amount_minor,currency)]),{right:[3]});
  const done=proposals.filter(p=>p.state==='EXECUTED'||p.state==='REJECTED');
  heading(`Payment decisions (${done.length})`);
  const byId=new Map(invoices.map(i=>[i.invoice_id,i]));
  table(['Supplier','Invoice','Decision','Amount'],done.map(p=>{const inv=byId.get(p.details.invoice_id);return [latin(prettyVendor(p.details.vendor_id)),latin(inv?.invoice_number||'-'),p.state==='EXECUTED'?'Approved and recorded':'Rejected',fmt(p.details.amount_minor,currency)];}),{right:[3]});
  const pages=doc.getNumberOfPages();
  for(let i=1;i<=pages;i++){doc.setPage(i);doc.setFont('helvetica','normal');doc.setFontSize(8);doc.setTextColor(120,130,145);
    doc.text('Based on records entered by the account holder. Not a bank statement and not verified by a bank. Every payment record needed an independent approver.',M,812);doc.text(`Page ${i} of ${pages}`,W-M,812,{align:'right'});}
  return doc.output('blob');
}

export async function downloadPdf(data:ReportData,filename:string){
  const blob=await buildPdf(data);const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000);
}
