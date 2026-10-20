import {useEffect,useRef,useState} from 'react';
import {Icon} from './Icon';
import {t,T} from './i18n';

const features:{icon:string;title:string;text:string}[]=[
 {icon:'camera',title:T('Photo to record'),text:T('Snap a bill or receipt and we read the supplier, date, amount and due date for you.')},
 {icon:'pen',title:T('Just say it'),text:T('Type what you paid or received, like a message, and it becomes a record.')},
 {icon:'Cash flow',title:T('Cash outlook'),text:T('See your balance for the next 7 and 30 days and test what-if cases.')},
 {icon:'Invoices',title:T('Bills and due dates'),text:T('Every unpaid bill in one list, so nothing is paid late or twice.')},
 {icon:'Approvals',title:T('Safe payments'),text:T('A second person approves each payment before it is recorded.')},
 {icon:'Financing',title:T('Compare loan offers'),text:T('Find the true yearly cost and the offer your cash flow can carry.')},
 {icon:'globe',title:T('Your language, any currency'),text:T('Use it in your language and see amounts at live exchange rates.')},
 {icon:'Audit',title:T('Reports and history'),text:T('Download a PDF report and see a clear, tamper-evident history.')},
];
const steps:{title:string;text:string}[]=[
 {title:T('Add'),text:T('Photograph a bill or type what happened. Check it, then confirm.')},
 {title:T('Understand'),text:T('See your balance, bills and the weeks ahead in plain words.')},
 {title:T('Decide'),text:T('Prepare payments, share with your accountant, compare loans.')},
];
const trust:{icon:string;title:string;text:string}[]=[
 {icon:'Approvals',title:T('Two people for every payment'),text:T('The person who prepares a payment can never approve it.')},
 {icon:'Audit',title:T('History nobody can quietly change'),text:T('Each entry is signed and linked, so edits show up.')},
 {icon:'Settings',title:T('Two-step sign-in'),text:T('Add an authenticator app and backup codes in a minute.')},
 {icon:'check',title:T('Private by default'),text:T('Only people you invite can see your records. You can clear them any time.')},
];

function ScanIllustration(){
  return <svg className="illus" viewBox="0 0 420 260" role="img" aria-label={t('A photographed bill turning into a record')}>
    <rect x="30" y="18" width="130" height="224" rx="20" className="il-phone"/>
    <rect x="44" y="40" width="102" height="170" rx="8" className="il-paper"/>
    <rect x="54" y="52" width="46" height="7" rx="3" className="il-ink"/><rect x="54" y="68" width="80" height="5" rx="2.5" className="il-soft"/><rect x="54" y="80" width="70" height="5" rx="2.5" className="il-soft"/><rect x="54" y="92" width="76" height="5" rx="2.5" className="il-soft"/><rect x="54" y="104" width="60" height="5" rx="2.5" className="il-soft"/>
    <rect x="54" y="170" width="82" height="9" rx="4" className="il-ink"/>
    <rect x="44" y="40" width="102" height="3" className="il-scan"/>
    <path d="M178 130h52" className="il-arrow"/><path d="M222 120l12 10-12 10" className="il-arrow" fill="none"/>
    <rect x="250" y="56" width="150" height="148" rx="16" className="il-card"/>
    <text x="268" y="84" className="il-label">{t('Supplier')}</text><text x="268" y="102" className="il-value">Dhaka Packaging</text>
    <text x="268" y="130" className="il-label">{t('Amount')}</text><text x="268" y="150" className="il-big">BDT 12,500</text>
    <text x="268" y="178" className="il-label">{t('Due')}</text><text x="268" y="196" className="il-value">5 Nov 2026</text>
  </svg>;
}
function OutlookIllustration(){
  return <svg className="illus" viewBox="0 0 420 260" role="img" aria-label={t('A cash outlook chart')}>
    <rect x="10" y="10" width="400" height="240" rx="18" className="il-card"/>
    <path d="M40 200h340" className="il-axis"/><path d="M40 60v140" className="il-axis"/>
    <path d="M40 170 C90 150 120 120 160 128 S230 170 270 120 S340 70 380 82 L380 200 L40 200Z" className="il-area"/>
    <path d="M40 170 C90 150 120 120 160 128 S230 170 270 120 S340 70 380 82" className="il-line" fill="none"/>
    <path d="M40 150h340" className="il-reserve"/>
    <circle cx="270" cy="120" r="6" className="il-dot"/>
  </svg>;
}

/** Everything a visitor can read before signing in. Plain markup and CSS, so it costs almost nothing to load. */
export function Landing({onStart}:{onStart:()=>void}){
  const root=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const nodes=root.current?.querySelectorAll('[data-reveal]');
    if(!nodes||!('IntersectionObserver' in window)){nodes?.forEach(n=>n.classList.add('in'));return;}
    const io=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}},{rootMargin:'0px 0px -8% 0px'});
    nodes.forEach(n=>io.observe(n));
    return()=>io.disconnect();
  },[]);
  return <div className="landing" ref={root}>
    <section id="features" className="land-section" aria-labelledby="land-features">
      <p className="eyebrow" data-reveal>{t('WHAT YOU GET')}</p>
      <h2 id="land-features" data-reveal>{t('Everything your business money needs, in one place')}</h2>
      <div className="feature-grid">{features.map((f,i)=><article key={f.title} className="feature" data-reveal style={undefined} data-i={i%4}><span className="feature-icon"><Icon name={f.icon}/></span><h3>{t(f.title)}</h3><p>{t(f.text)}</p></article>)}</div>
    </section>
    <section className="land-section land-visuals" aria-labelledby="land-see">
      <p className="eyebrow" data-reveal>{t('SEE IT WORK')}</p>
      <h2 id="land-see" data-reveal>{t('From a photo to a clear picture')}</h2>
      <div className="visual-row">
        <figure data-reveal><ScanIllustration/><figcaption>{t('Photograph a bill. Check what we read. Add it in one tap.')}</figcaption></figure>
        <figure data-reveal><OutlookIllustration/><figcaption>{t('Know if cash will run short before it happens.')}</figcaption></figure>
      </div>
    </section>
    <section className="land-section" aria-labelledby="land-how">
      <p className="eyebrow" data-reveal>{t('HOW IT WORKS')}</p>
      <h2 id="land-how" data-reveal>{t('Three simple steps')}</h2>
      <ol className="steps">{steps.map((s,i)=><li key={s.title} data-reveal><span className="step-n">{i+1}</span><h3>{t(s.title)}</h3><p>{t(s.text)}</p></li>)}</ol>
    </section>
    <section className="land-section" aria-labelledby="land-safe">
      <p className="eyebrow" data-reveal>{t('BUILT TO BE SAFE')}</p>
      <h2 id="land-safe" data-reveal>{t('Your money, your control')}</h2>
      <div className="trust-grid">{trust.map(x=><article key={x.title} data-reveal><span className="feature-icon"><Icon name={x.icon}/></span><div><h3>{t(x.title)}</h3><p>{t(x.text)}</p></div></article>)}</div>
    </section>
    <section className="land-cta" data-reveal>
      <h2>{t('Ready to see your numbers clearly?')}</h2>
      <p>{t('Free to start. It takes a minute.')}</p>
      <button onClick={onStart}>{t('Create my free workspace')}<Icon name="arrow"/></button>
    </section>
    <p className="land-foot">{t('Capzoryx Copilot · Your records · A second person approves every payment · Nothing leaves your control')}</p>
  </div>;
}

/** Big logo first, then it settles into the corner while the page comes in. Shown once per visit; skipped for reduced motion. */
export function Intro(){
  const seen=(()=>{try{return sessionStorage.getItem('capzoryx-intro')==='1'||matchMedia('(prefers-reduced-motion: reduce)').matches;}catch{return true;}})();
  const [gone,setGone]=useState(seen);
  useEffect(()=>{try{sessionStorage.setItem('capzoryx-intro','1');}catch{/* optional */}const id=window.setTimeout(()=>setGone(true),2000);return()=>window.clearTimeout(id);},[]);
  if(gone)return null;
  return <div className="intro" aria-hidden="true"><svg className="intro-logo" viewBox="0 0 40 40" width="132" height="132"><defs><linearGradient id="cz-intro" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#0f9b7c"/><stop offset="1" stopColor="#132a4a"/></linearGradient></defs><rect width="40" height="40" rx="11" fill="url(#cz-intro)"/><path d="M27.5 13.2A9.6 9.6 0 1 0 27.5 26.8" fill="none" stroke="#fff" strokeWidth="4" strokeLinecap="round"/><path className="intro-rise" d="M16.5 24.5l4-4.2 3 2.4 6-7.4" fill="none" stroke="#8cebd0" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"/></svg><span className="intro-name">Capzoryx <b>Copilot</b></span></div>;
}
