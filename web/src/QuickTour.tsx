import {useEffect,useRef,useState,type KeyboardEvent} from 'react';
import {t,T} from './i18n';

type Step={page:string;target:string;title:string;body:string};
const steps:Step[]=[
 {page:'Overview',target:'#workspace h1',title:T('Welcome to Capzoryx Copilot'),body:T('Your business money in one place: balance, bills, cash outlook, loans and safe payments. This one-minute tour shows where everything is. Reopen it any time with Quick tutorial.')},
 {page:'Data',target:'.quick-add',title:T('Add records in seconds'),body:T('Photograph a bill, or type what happened like a message. Check what we read, then press Add. Nothing is saved until you confirm it.')},
 {page:'Data',target:'.quick-grid .quick-box:first-child',title:T('Photo to record'),body:T('Take or choose a photo of an invoice or receipt. We read the supplier, number, date and amount for you. If something is wrong, fix it before adding.')},
 {page:'Data',target:'.quick-grid .quick-box:nth-child(2)',title:T('Or just say it'),body:T('Type something like: I paid Rahman 5000 for freight yesterday. We turn it into a record for you to confirm.')},
 {page:'Overview',target:'.balance-cards',title:T('Your numbers at a glance'),body:T('Balance, money received and money spent come from the records you added. Cleared means it really happened; planned items appear in your outlook.')},
 {page:'Overview',target:'#view-currency',title:T('See amounts in any currency'),body:T('Choose a currency and your figures convert at today’s live exchange rate. Your records stay in the workspace currency.')},
 {page:'Invoices',target:'[data-tour="Invoices"]',title:T('Bills you still have to pay'),body:T('Invoices lists every unpaid bill with its due date. Press Prepare payment on a bill to start a safe payment.')},
 {page:'Cash flow',target:'[data-tour="Cash flow"]',title:T('See what is coming'),body:T('Check the next 7 and 30 days and test what-if cases, such as a customer paying late. Scenarios never change your records.')},
 {page:'Approvals',target:'[data-tour="Approvals"]',title:T('A second person approves'),body:T('Every payment needs an approver who did not prepare it. Approving records the payment in your books. It never sends a bank transfer.')},
 {page:'Financing',target:'[data-tour="Financing"]',title:T('Compare loan offers'),body:T('Enter the offers you received. We work out the true yearly cost and show which one your cash flow can handle.')},
 {page:'Overview',target:'.chat-launcher',title:T('Ask the assistant'),body:T('Ask about your balance or bills, or say what you paid and it adds a record for you. Simple questions are answered right on your device.')},
 {page:'Settings',target:'[data-tour="Settings"]',title:T('Make it yours'),body:T('Add your photo, change your password, turn on two-step sign-in, pick a language, invite teammates and manage your data.')},
 {page:'Overview',target:'.header-actions',title:T('You are ready'),body:T('Download a PDF report any time. Open this tour again with Quick tutorial in the header.')},
];

type Box={x:number;y:number;width:number;height:number;above:boolean};
export function QuickTour({ready,userId,currentPage,navigate}:{ready:boolean;userId:string;currentPage:string;navigate:(page:string)=>void}){
 const key=`safeledger-tour-v2:${userId}`;
 const [step,setStep]=useState<number|null>(null);
 const [box,setBox]=useState<Box|null>(null);
 const checked=useRef(false),returnPage=useRef(currentPage),dialog=useRef<HTMLDialogElement>(null),launcher=useRef<HTMLButtonElement>(null),scrollPosition=useRef(0),heading=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{
  if(!ready||checked.current)return;checked.current=true;
  try{if(localStorage.getItem(key)==='done'||localStorage.getItem(key)==='skipped')return;}catch{/* Offer the tour once this session if storage is unavailable. */}
  returnPage.current=currentPage;scrollPosition.current=window.scrollY;setStep(0);
 },[ready,key,currentPage]);
 useEffect(()=>{
  if(step===null)return;
  if(step>0)navigate(steps[step].page);
  if(!dialog.current?.open)dialog.current?.showModal();
  heading.current?.focus({preventScroll:true});
  let tries=0;const timer={id:0};
  function measure(){
   const target=document.querySelector(steps[step!].target);
   if(!target){setBox(null);return false;}
   const r=target.getBoundingClientRect();
   if(!r.width||!r.height){setBox(null);return false;}
   setBox({x:Math.max(4,r.x-8),y:Math.max(4,r.y-8),width:Math.min(r.width+16,innerWidth-8),height:r.height+16,above:r.bottom>innerHeight*.55});return true;
  }
  // The page for a step may still be loading, so look for the target for a short while.
  function find(){
   const target=document.querySelector(steps[step!].target);
   if(target){target.scrollIntoView({block:'center',behavior:'instant'});measure();return;}
   if(++tries<12)timer.id=window.setTimeout(find,120);else setBox(null);
  }
  timer.id=window.setTimeout(find,30);
  window.addEventListener('resize',measure);window.addEventListener('scroll',measure,true);
  return()=>{window.clearTimeout(timer.id);window.removeEventListener('resize',measure);window.removeEventListener('scroll',measure,true);};
 },[step,navigate]);
 function finish(completed:boolean){try{localStorage.setItem(key,completed?'done':'skipped');}catch{/* Dismissal always works. */}dialog.current?.close();setStep(null);setBox(null);navigate(returnPage.current);requestAnimationFrame(()=>{window.scrollTo({top:scrollPosition.current,behavior:'instant'});launcher.current?.focus({preventScroll:true});});}
 const last=steps.length-1;
 const go=(n:number)=>setStep(Math.min(last,Math.max(0,n)));
 const onKey=(e:KeyboardEvent)=>{
  if(step===null)return;
  const rtl=document.documentElement.dir==='rtl';
  if(e.key==='ArrowRight'){e.preventDefault();go(step+(rtl?-1:1));}
  if(e.key==='ArrowLeft'){e.preventDefault();go(step+(rtl?1:-1));}
 };
 const active=step===null?null:steps[step];
 return <><button ref={launcher} className="secondary" disabled={!ready} onClick={()=>{returnPage.current=currentPage;scrollPosition.current=window.scrollY;setStep(0);}}>{t('Quick tutorial')}</button>
  <dialog ref={dialog} className={'quick-tour'+(box?.above?' tour-above':'')} aria-labelledby="tour-title" aria-describedby="tour-body" onKeyDown={onKey} onCancel={e=>{e.preventDefault();finish(false);}}>
   {active&&<>
    <svg className="tour-highlight" aria-hidden="true">{box&&<rect x={box.x} y={box.y} width={box.width} height={box.height} rx="12"/>}</svg>
    <div className="tour-top"><span className="badge">{t('QUICK START')}</span><span className="tour-count" role="status">{t('Step {n} of {total}',{n:(step??0)+1,total:steps.length})}</span><button className="link" aria-label={t('Close tutorial')} onClick={()=>finish(false)}>×</button></div>
    <div className="tour-progress" role="group" aria-label={t('Tutorial steps')}>{steps.map((s,i)=><button key={i} type="button" className={step!==null&&i<=step?'complete':''} aria-label={t('Go to step {n}',{n:i+1})} aria-current={i===step?'step':undefined} onClick={()=>go(i)}/>)}</div>
    <h2 id="tour-title" ref={heading} tabIndex={-1}>{t(active.title)}</h2>
    <p id="tour-body">{t(active.body)}</p>
    <div className="tour-actions"><button className="link" onClick={()=>finish(false)}>{t('Skip tour')}</button><div><button className="secondary" disabled={step===0} onClick={()=>go((step??0)-1)}>{t('Back')}</button><button onClick={()=>step===last?finish(true):go((step??0)+1)}>{step===last?t('Get started'):t('Next')}</button></div></div>
   </>}
  </dialog></>;
}
