import {useEffect,useRef,useState} from 'react';
import {Icon} from './Icon';
import {LANGUAGES,t,T} from './i18n';
import {Logo} from './Logo';

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
const audiences:{icon:string;title:string;text:string}[]=[
 {icon:'Invoices',title:T('Shops and retailers'),text:T('Track daily cash and supplier bills without a spreadsheet.')},
 {icon:'Financing',title:T('Wholesalers and distributors'),text:T('Plan payments around customer receipts and compare credit lines.')},
 {icon:'Data',title:T('Freelancers and services'),text:T('Record what you are owed and what you spent, from your phone.')},
 {icon:'Approvals',title:T('Accountants and partners'),text:T('Invite a teammate to review or approve, with clear roles.')},
];
const faq:{q:string;a:string}[]=[
 {q:T('Is it free?'),a:T('Yes. You can create a workspace and use every feature at no cost.')},
 {q:T('Does it move my money?'),a:T('No. It records and plans. Approving a payment writes it in your books; no bank transfer is made.')},
 {q:T('Who can see my records?'),a:T('Only you and people you invite. You choose whether they can approve payments or only view.')},
 {q:T('Which currencies are supported?'),a:T('Over 170 currencies, with live exchange rates for converted values.')},
 {q:T('What if I forget my password?'),a:T('Ask for a code by email, or use the recovery key you saved when you signed up.')},
];
const stats:{n:string;label:string}[]=[
 {n:'37',label:T('languages')},{n:'170+',label:T('currencies with live rates')},{n:'2',label:T('people on every payment')},{n:'30',label:T('days to undo clearing data')},
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
/** A small, honest preview of the workspace with sample numbers. Plain HTML so it costs nothing to load. */
function Preview(){
  const bars=[46,58,52,70,64,82,76];
  return <div className="preview" role="img" aria-label={t('Preview of the workspace with sample numbers')}>
    <div className="pv-top"><span className="pv-dot"/><span className="pv-dot"/><span className="pv-dot"/><b>{t('Financial overview')}</b></div>
    <div className="pv-cards">
      <div><small>{t('Available balance')}</small><strong>BDT 146,500</strong><em>≈ USD 1,196</em></div>
      <div><small>{t('Cleared income')}</small><strong>BDT 150,000</strong></div>
      <div><small>{t('Cleared expenses')}</small><strong>BDT 3,500</strong></div>
    </div>
    <div className="pv-body">
      <div className="pv-chart" aria-hidden="true">{bars.map((h,i)=><i key={i} className={'pv-bar h'+h}/>)}</div>
      <ul className="pv-list" aria-hidden="true"><li><span>Dhaka Packaging</span><b>BDT 12,500</b></li><li><span>Rahman Logistics</span><b>BDT 4,500</b></li><li><span>Karim Traders</span><b className="in">+ BDT 20,000</b></li></ul>
    </div>
  </div>;
}

/** Everything a visitor can read before signing in. Plain markup and CSS, so it costs almost nothing to load. */
export function Landing({onStart}:{onStart:()=>void}){
  const root=useRef<HTMLDivElement>(null);const [bar,setBar]=useState(false);
  useEffect(()=>{
    const nodes=root.current?.querySelectorAll('[data-reveal]');
    if(!nodes||!('IntersectionObserver' in window)){nodes?.forEach(n=>n.classList.add('in'));return;}
    const io=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}},{rootMargin:'0px 0px -8% 0px'});
    nodes.forEach(n=>io.observe(n));
    return()=>io.disconnect();
  },[]);
  // The slim top bar appears once the visitor has scrolled past the first screen.
  useEffect(()=>{
    const onScroll=()=>setBar(window.scrollY>window.innerHeight*.6);
    onScroll();window.addEventListener('scroll',onScroll,{passive:true});return()=>window.removeEventListener('scroll',onScroll);
  },[]);
  const go=(id:string)=>document.getElementById(id)?.scrollIntoView({behavior:'smooth'});
  const names=LANGUAGES.map(l=>l.name);
  return <div className="landing" ref={root}>
    <nav className={bar?'land-nav show':'land-nav'} aria-label={t('Page sections')}>
      <button type="button" className="land-brand" onClick={()=>window.scrollTo({top:0,behavior:'smooth'})} aria-label="Capzoryx Copilot"><Logo size={28}/><span>Capzoryx <b>Copilot</b></span></button>
      <div className="land-links"><button type="button" className="link" onClick={()=>go('features')}>{t('Features')}</button><button type="button" className="link" onClick={()=>go('preview')}>{t('See it work')}</button><button type="button" className="link" onClick={()=>go('safety')}>{t('Safety')}</button><button type="button" className="link" onClick={()=>go('faq')}>{t('Questions')}</button></div>
      <button type="button" className="land-signin" onClick={onStart}>{t('Sign in')}</button>
    </nav>
    <div className="stats" data-reveal>{stats.map(s=><div key={s.label}><strong>{s.n}</strong><span>{t(s.label)}</span></div>)}</div>
    <section id="features" className="land-section" aria-labelledby="land-features">
      <p className="eyebrow" data-reveal>{t('WHAT YOU GET')}</p>
      <h2 id="land-features" data-reveal>{t('Everything your business money needs, in one place')}</h2>
      <div className="feature-grid">{features.map((f,i)=><article key={f.title} className="feature" data-reveal data-i={i%4}><span className="feature-icon"><Icon name={f.icon}/></span><h3>{t(f.title)}</h3><p>{t(f.text)}</p></article>)}</div>
    </section>
    <section id="preview" className="land-section land-visuals" aria-labelledby="land-see">
      <p className="eyebrow" data-reveal>{t('SEE IT WORK')}</p>
      <h2 id="land-see" data-reveal>{t('From a photo to a clear picture')}</h2>
      <div className="visual-row">
        <figure data-reveal><ScanIllustration/><figcaption>{t('Photograph a bill. Check what we read. Add it in one tap.')}</figcaption></figure>
        <figure data-reveal><OutlookIllustration/><figcaption>{t('Know if cash will run short before it happens.')}</figcaption></figure>
      </div>
      <div className="preview-wrap" data-reveal><Preview/><p className="small muted">{t('A preview with sample numbers.')}</p></div>
    </section>
    <section className="land-section" aria-labelledby="land-how">
      <p className="eyebrow" data-reveal>{t('HOW IT WORKS')}</p>
      <h2 id="land-how" data-reveal>{t('Three simple steps')}</h2>
      <ol className="steps">{steps.map((s,i)=><li key={s.title} data-reveal><span className="step-n">{i+1}</span><h3>{t(s.title)}</h3><p>{t(s.text)}</p></li>)}</ol>
    </section>
    <section className="land-section" aria-labelledby="land-who">
      <p className="eyebrow" data-reveal>{t('MADE FOR')}</p>
      <h2 id="land-who" data-reveal>{t('Built for the way small businesses work')}</h2>
      <div className="feature-grid">{audiences.map(f=><article key={f.title} className="feature" data-reveal><span className="feature-icon"><Icon name={f.icon}/></span><h3>{t(f.title)}</h3><p>{t(f.text)}</p></article>)}</div>
    </section>
    <section id="safety" className="land-section" aria-labelledby="land-safe">
      <p className="eyebrow" data-reveal>{t('BUILT TO BE SAFE')}</p>
      <h2 id="land-safe" data-reveal>{t('Your money, your control')}</h2>
      <div className="trust-grid">{trust.map(x=><article key={x.title} data-reveal><span className="feature-icon"><Icon name={x.icon}/></span><div><h3>{t(x.title)}</h3><p>{t(x.text)}</p></div></article>)}</div>
    </section>
    <section className="land-section land-langs" aria-labelledby="land-lang" data-reveal>
      <p className="eyebrow">{t('FOR EVERYONE')}</p>
      <h2 id="land-lang">{t('Use it in your own language')}</h2>
      <div className="marquee" aria-hidden="true"><div className="marquee-track">{[...names,...names].map((n,i)=><span key={i}>{n}</span>)}</div></div>
    </section>
    <section id="faq" className="land-section" aria-labelledby="land-faq">
      <p className="eyebrow" data-reveal>{t('QUESTIONS')}</p>
      <h2 id="land-faq" data-reveal>{t('Good to know')}</h2>
      <div className="faq" data-reveal>{faq.map(x=><details key={x.q}><summary>{t(x.q)}</summary><p>{t(x.a)}</p></details>)}</div>
    </section>
    <section className="land-cta" data-reveal>
      <h2>{t('Ready to see your numbers clearly?')}</h2>
      <p>{t('Free to start. It takes a minute.')}</p>
      <button onClick={onStart}>{t('Create my free workspace')}<Icon name="arrow"/></button>
    </section>
    <p className="land-foot">{t('Capzoryx Copilot · Your records · A second person approves every payment · Nothing leaves your control')}</p>
  </div>;
}
