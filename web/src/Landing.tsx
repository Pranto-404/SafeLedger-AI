import {useEffect,useMemo,useRef,useState,type PointerEvent as RPointerEvent} from 'react';
import {Icon} from './Icon';
import {LANGUAGES,t,T} from './i18n';
import {Logo} from './Logo';

const audiences:{icon:string;title:string;text:string}[]=[
 {icon:'Invoices',title:T('Shops and retailers'),text:T('Track daily cash and supplier bills without a spreadsheet.')},
 {icon:'Financing',title:T('Wholesalers and distributors'),text:T('Plan payments around customer receipts and compare credit lines.')},
 {icon:'Data',title:T('Freelancers and services'),text:T('Record what you are owed and what you spent, from your phone.')},
 {icon:'Approvals',title:T('Accountants and partners'),text:T('Invite a teammate to review or approve, with clear roles.')},
];
const trust:{icon:string;title:string;text:string}[]=[
 {icon:'Approvals',title:T('Two people for every payment'),text:T('The person who prepares a payment can never approve it.')},
 {icon:'Audit',title:T('History nobody can quietly change'),text:T('Each entry is signed and linked, so edits show up.')},
 {icon:'Settings',title:T('Two-step sign-in'),text:T('Add an authenticator app and backup codes in a minute.')},
 {icon:'check',title:T('Private by default'),text:T('Only people you invite can see your records. You can clear them any time.')},
];
const faq:{q:string;a:string}[]=[
 {q:T('Is it free?'),a:T('Yes. You can create a workspace and use every feature at no cost.')},
 {q:T('Does it move my money?'),a:T('No. It records and plans. Approving a payment writes it in your books; no bank transfer is made.')},
 {q:T('Who can see my records?'),a:T('Only you and people you invite. You choose whether they can approve payments or only view.')},
 {q:T('Which currencies are supported?'),a:T('Over 170 currencies, with live exchange rates for converted values.')},
 {q:T('What if I forget my password?'),a:T('Ask for a code by email, or use the recovery key you saved when you signed up.')},
];
const soon:{icon:string;title:string;text:string}[]=[
 {icon:'Data',title:T('Bank and wallet import'),text:T('Paste a bKash, Nagad, Rocket or bank message, or upload a statement, and we propose the records for you to confirm.')},
 {icon:'Cash flow',title:T('Live payment feed'),text:T('For businesses that take online payments: each received payment can arrive as a record by itself.')},
 {icon:'Settings',title:T('Install on your phone'),text:T('Add the site to your home screen and share a message straight into your records.')},
 {icon:'Invoices',title:T('Bill reminders'),text:T('Get a nudge before a bill is due, by email.')},
];
const stats:{n:number;suffix:string;label:string}[]=[
 {n:37,suffix:'',label:T('languages')},{n:170,suffix:'+',label:T('currencies with live rates')},{n:2,suffix:'',label:T('people on every payment')},{n:30,suffix:'',label:T('days to undo clearing data')},
];
const story:{title:string;text:string}[]=[
 {title:T('Add'),text:T('Photograph a bill or type what happened. Check it, then confirm.')},
 {title:T('Understand'),text:T('See your balance, bills and the weeks ahead in plain words.')},
 {title:T('Decide'),text:T('Prepare payments, share with your accountant, compare loans.')},
];
const reduced=()=>{try{return matchMedia('(prefers-reduced-motion: reduce)').matches;}catch{return false;}};

/** Counts up once when it scrolls into view. */
function Counter({to,suffix}:{to:number;suffix:string}){
  const ref=useRef<HTMLElement>(null);const [v,setV]=useState(reduced()?to:0);
  useEffect(()=>{
    if(reduced()){setV(to);return;}
    const el=ref.current;if(!el||!('IntersectionObserver' in window)){setV(to);return;}
    let raf=0;
    const io=new IntersectionObserver(es=>{if(!es[0].isIntersecting)return;io.disconnect();const t0=performance.now();const tick=(now:number)=>{const p=Math.min(1,(now-t0)/1100);setV(Math.round(to*(1-Math.pow(1-p,3))));if(p<1)raf=requestAnimationFrame(tick);};raf=requestAnimationFrame(tick);});
    io.observe(el);return()=>{io.disconnect();cancelAnimationFrame(raf);};
  },[to]);
  return <strong ref={ref}>{v}{suffix}</strong>;
}

/** Types a sentence, then shows the record it becomes. Loops quietly; static for reduced motion. */
const demos:{say:string;who:string;what:string;amount:string;kind:string}[]=[
 {say:'I paid Rahman 5000 for freight yesterday',who:'Rahman',what:'Freight',amount:'BDT 5,000',kind:T('Money out')},
 {say:'Received 20,000 from Karim Traders',who:'Karim Traders',what:'Payment',amount:'+ BDT 20,000',kind:T('Money in')},
 {say:'Bill from Dhaka Packaging 12000 due in 10 days',who:'Dhaka Packaging',what:'Bill',amount:'BDT 12,000',kind:T('Unpaid supplier invoice')},
];
export function HeroDemo(){
  const [i,setI]=useState(0);const [n,setN]=useState(reduced()?999:0);const [done,setDone]=useState(reduced());
  const d=demos[i];
  useEffect(()=>{
    if(reduced())return;
    let id=0;
    if(n<d.say.length){id=window.setTimeout(()=>setN(n+1),n===0?500:38);}
    else if(!done){id=window.setTimeout(()=>setDone(true),350);}
    else{id=window.setTimeout(()=>{setDone(false);setN(0);setI((i+1)%demos.length);},3200);}
    return()=>window.clearTimeout(id);
  },[n,done,d.say.length,i]);
  return <div className="hero-demo" aria-hidden="true">
    <div className="hd-bar"><span className="hd-dot"/><span className="hd-dot"/><span className="hd-dot"/><b>{t('Assistant')}</b></div>
    <div className="hd-body">
      <p className="hd-user">{d.say.slice(0,n)}<span className="hd-caret"/></p>
      <div className={done?'hd-card show':'hd-card'}><span className="hd-badge">{t(d.kind)}</span><strong>{d.who}</strong><small>{d.what}</small><em>{d.amount}</em><span className="hd-add"><Icon name="check"/>{t('Add to my records')}</span></div>
    </div>
  </div>;
}

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
function ApprovalMock(){
  return <div className="approve-mock" role="img" aria-label={t('A payment waiting for a second person to approve')}>
    <div className="am-head"><b>{t('Pay supplier')}</b><span className="hd-badge">{t('Waiting')}</span></div>
    <div className="am-row"><span>Dhaka Packaging</span><strong>BDT 12,500</strong></div>
    <div className="am-steps">
      <div className="am-step done"><span><Icon name="check"/></span>{t('Prepared by you')}</div>
      <div className="am-line"/>
      <div className="am-step wait"><span/>{t('Approved by a second person')}</div>
      <div className="am-line"/>
      <div className="am-step"><span/>{t('Recorded in your books')}</div>
    </div>
  </div>;
}

/** Drag the slider: a late customer payment moves the whole outlook, and the page says whether cash runs short. */
function OutlookPlayground(){
  const [late,setLate]=useState(0);
  const reserve=30000;
  const model=useMemo(()=>{
    const days=22;const bal:number[]=[];let b=150000;
    for(let d=0;d<days;d++){
      if(d===3)b-=35000;
      if(d===6+late)b+=40000;
      if(d===9)b-=60000;
      if(d===13)b-=45000;
      if(d===18+Math.min(late,3))b+=30000;
      bal.push(b);
    }
    const low=Math.min(...bal);const first=bal.findIndex(x=>x<reserve);
    return {bal,low,first};
  },[late]);
  const W=420,H=190,pad=24;const max=Math.max(...model.bal,180000),min=Math.min(...model.bal,0);
  const x=(i:number)=>pad+i*(W-pad*2)/(model.bal.length-1);const y=(v:number)=>H-pad-((v-min)/(max-min))*(H-pad*2);
  const line=model.bal.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(v).toFixed(1)).join(' ');
  const area=line+` L${x(model.bal.length-1)} ${H-pad} L${x(0)} ${H-pad}Z`;
  const short=model.first>=0;
  return <div className="playground">
    <svg viewBox={`0 0 ${W} ${H}`} className="pg-chart" role="img" aria-label={t('A cash outlook chart')}>
      <path d={area} className={short?'pg-area bad':'pg-area'}/><path d={line} className={short?'pg-line bad':'pg-line'} fill="none"/>
      <line x1={pad} x2={W-pad} y1={y(reserve)} y2={y(reserve)} className="pg-reserve"/>
      {short&&<circle cx={x(model.first)} cy={y(model.bal[model.first])} r="6" className="pg-dot"/>}
    </svg>
    <label htmlFor="pg-late" className="pg-label">{t('A customer pays {n} days late',{n:late})}</label>
    <input id="pg-late" className="pg-range" type="range" min="0" max="12" step="1" value={late} onChange={e=>setLate(Number(e.target.value))}/>
    <p className={short?'pg-result bad':'pg-result'} role="status">{short?t('Cash runs below your safety reserve on day {n}.',{n:model.first+1}):t('Your cash stays above your safety reserve.')}</p>
  </div>;
}

/** The slim top bar, a thin scroll progress line, and the spotlight that follows the pointer on cards. */
export function Landing({onStart}:{onStart:()=>void}){
  const root=useRef<HTMLDivElement>(null);const bar=useRef<HTMLDivElement>(null);const [nav,setNav]=useState(false);const [step,setStep]=useState(0);
  useEffect(()=>{
    const nodes=root.current?.querySelectorAll('[data-reveal]');
    if(!nodes||!('IntersectionObserver' in window)){nodes?.forEach(n=>n.classList.add('in'));return;}
    const io=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}},{rootMargin:'0px 0px -8% 0px'});
    nodes.forEach(n=>io.observe(n));
    return()=>io.disconnect();
  },[]);
  useEffect(()=>{
    let raf=0;
    const update=()=>{raf=0;const h=document.documentElement.scrollHeight-window.innerHeight;if(bar.current)bar.current.style.transform=`scaleX(${h>0?Math.min(1,window.scrollY/h):0})`;setNav(window.scrollY>window.innerHeight*.5);};
    const onScroll=()=>{if(!raf)raf=requestAnimationFrame(update);};
    update();window.addEventListener('scroll',onScroll,{passive:true});return()=>{window.removeEventListener('scroll',onScroll);cancelAnimationFrame(raf);};
  },[]);
  // Which story step is on screen decides which picture the sticky phone shows.
  useEffect(()=>{
    const els=root.current?.querySelectorAll<HTMLElement>('[data-step]');if(!els||!('IntersectionObserver' in window))return;
    const io=new IntersectionObserver(es=>{for(const e of es)if(e.isIntersecting)setStep(Number((e.target as HTMLElement).dataset.step));},{rootMargin:'-45% 0px -45% 0px'});
    els.forEach(n=>io.observe(n));return()=>io.disconnect();
  },[]);
  const spot=(e:RPointerEvent<HTMLElement>)=>{const r=e.currentTarget.getBoundingClientRect();e.currentTarget.style.setProperty('--mx',(e.clientX-r.left)+'px');e.currentTarget.style.setProperty('--my',(e.clientY-r.top)+'px');};
  const go=(id:string)=>document.getElementById(id)?.scrollIntoView({behavior:'smooth'});
  const names=LANGUAGES.map(l=>l.name);
  return <div className="landing" ref={root}>
    <div className="scroll-progress" ref={bar} aria-hidden="true"/>
    <nav className={nav?'land-nav show':'land-nav'} aria-label={t('Page sections')}>
      <button type="button" className="land-brand" onClick={()=>window.scrollTo({top:0,behavior:'smooth'})} aria-label="Capzoryx Copilot"><Logo size={28}/><span>Capzoryx <b>Copilot</b></span></button>
      <div className="land-links"><button type="button" className="link" onClick={()=>go('features')}>{t('Features')}</button><button type="button" className="link" onClick={()=>go('preview')}>{t('See it work')}</button><button type="button" className="link" onClick={()=>go('safety')}>{t('Safety')}</button><button type="button" className="link" onClick={()=>go('soon')}>{t('Coming soon')}</button><button type="button" className="link" onClick={()=>go('faq')}>{t('Questions')}</button></div>
      <button type="button" className="land-signin" onClick={onStart}>{t('Sign in')}</button>
    </nav>
    <div className="stats" data-reveal>{stats.map(s=><div key={s.label}><Counter to={s.n} suffix={s.suffix}/><span>{t(s.label)}</span></div>)}</div>

    <section id="features" className="land-section" aria-labelledby="land-features">
      <p className="eyebrow" data-reveal>{t('WHAT YOU GET')}</p>
      <h2 id="land-features" data-reveal>{t('Everything your business money needs, in one place')}</h2>
      <div className="bento">
        <article className="tile tile-wide spot" data-reveal onPointerMove={spot}><div><span className="feature-icon"><Icon name="camera"/></span><h3>{t('Photo to record')}</h3><p>{t('Snap a bill or receipt and we read the supplier, date, amount and due date for you.')}</p></div><ScanIllustration/></article>
        <article className="tile spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name="pen"/></span><h3>{t('Just say it')}</h3><p>{t('Type what you paid or received, like a message, and it becomes a record.')}</p></article>
        <article className="tile spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name="Invoices"/></span><h3>{t('Bills and due dates')}</h3><p>{t('Every unpaid bill in one list, so nothing is paid late or twice.')}</p></article>
        <article className="tile tile-wide spot" data-reveal onPointerMove={spot}><div><span className="feature-icon"><Icon name="Approvals"/></span><h3>{t('Safe payments')}</h3><p>{t('A second person approves each payment before it is recorded.')}</p></div><ApprovalMock/></article>
        <article className="tile spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name="Financing"/></span><h3>{t('Compare loan offers')}</h3><p>{t('Find the true yearly cost and the offer your cash flow can carry.')}</p></article>
        <article className="tile spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name="globe"/></span><h3>{t('Your language, any currency')}</h3><p>{t('Use it in your language and see amounts at live exchange rates.')}</p></article>
        <article className="tile tile-half spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name="Audit"/></span><h3>{t('Reports and history')}</h3><p>{t('Download a PDF report and see a clear, tamper-evident history.')}</p></article><article className="tile tile-half spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name="Settings"/></span><h3>{t('Work with your team')}</h3><p>{t('Invite your accountant or a partner and choose what they can do.')}</p></article>
      </div>
    </section>

    <section className="land-section" aria-labelledby="land-play">
      <p className="eyebrow" data-reveal>{t('TRY IT')}</p>
      <h2 id="land-play" data-reveal>{t('Will your cash last? Move the slider.')}</h2>
      <div className="play-wrap" data-reveal><OutlookPlayground/><p className="small muted">{t('Sample numbers. Your own outlook uses your records.')}</p></div>
    </section>

    <section id="preview" className="land-section" aria-labelledby="land-how">
      <p className="eyebrow" data-reveal>{t('HOW IT WORKS')}</p>
      <h2 id="land-how" data-reveal>{t('Three simple steps')}</h2>
      <div className="story">
        <ol className="story-steps">{story.map((s,i)=><li key={s.title} data-step={i} className={step===i?'active':''}><span className="step-n">{i+1}</span><h3>{t(s.title)}</h3><p>{t(s.text)}</p><div className="story-inline">{i===0?<ScanIllustration/>:i===1?<Preview/>:<ApprovalMock/>}</div></li>)}</ol>
        <div className="story-visual" aria-hidden="true"><div className={'sv sv0'+(step===0?' on':'')}><ScanIllustration/></div><div className={'sv sv1'+(step===1?' on':'')}><Preview/></div><div className={'sv sv2'+(step===2?' on':'')}><ApprovalMock/></div></div>
      </div>
    </section>

    <section className="land-section" aria-labelledby="land-who">
      <p className="eyebrow" data-reveal>{t('MADE FOR')}</p>
      <h2 id="land-who" data-reveal>{t('Built for the way small businesses work')}</h2>
      <div className="feature-grid">{audiences.map(f=><article key={f.title} className="feature spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name={f.icon}/></span><h3>{t(f.title)}</h3><p>{t(f.text)}</p></article>)}</div>
    </section>
    <section id="safety" className="land-section" aria-labelledby="land-safe">
      <p className="eyebrow" data-reveal>{t('BUILT TO BE SAFE')}</p>
      <h2 id="land-safe" data-reveal>{t('Your money, your control')}</h2>
      <div className="trust-grid">{trust.map(x=><article key={x.title} className="spot" data-reveal onPointerMove={spot}><span className="feature-icon"><Icon name={x.icon}/></span><div><h3>{t(x.title)}</h3><p>{t(x.text)}</p></div></article>)}</div>
    </section>
    <section id="soon" className="land-section" aria-labelledby="land-soon">
      <p className="eyebrow" data-reveal>{t('COMING SOON')}</p>
      <h2 id="land-soon" data-reveal>{t('What we are building next')}</h2>
      <div className="soon-grid">{soon.map(x=><article key={x.title} className="soon-card spot" data-reveal onPointerMove={spot}><span className="soon-badge">{t('Planned')}</span><span className="feature-icon"><Icon name={x.icon}/></span><h3>{t(x.title)}</h3><p>{t(x.text)}</p></article>)}</div>
      <p className="small muted soon-note" data-reveal>{t('Nothing here connects to your bank today. When it does, you will always confirm each record yourself.')}</p>
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
