import {Brand} from './Logo';
import {QuickTour} from './QuickTour';
import {LazyBoundary} from './LazyBoundary';
import {ThemeButton} from './Theme';
import {Icon} from './Icon';
import {Dashboard} from './Dashboard';
import {CashChart} from './Charts';
import {CurrencyProvider,CurrencyControls,useCurrency,usePreferredCurrency} from './Currency';
import {lazy,Suspense,useEffect,useRef,useState,useCallback,type ReactNode,type KeyboardEvent} from 'react';
import {ApiError,client,accountRequest,currencyDigits,fxRate} from './api';
import type {Audit,Forecast,Invoice,Profile,Proposal,Session,Snapshot,CashEvent,WorkspaceItem} from './types';
import {ImportEvidence} from './ImportEvidence';
import {sampleBusiness} from './sampleBusiness';
import {DataEntry} from './DataEntry';
import {Financing} from './Financing';
import {QuickAdd} from './QuickAdd';
import {Avatar} from './Avatar';
import {formatDate,formatTime,prettyVendor,workspaceLabel} from './format';
import {t,T,LanguagePicker,useI18n,hasChosenLanguage} from './i18n';
import './serverText';

const Settings=lazy(()=>import('./Settings'));
const Assistant=lazy(()=>import('./Assistant'));
const tabs=['Overview','Data','Invoices','Cash flow','Financing','Assistant','Approvals','Audit','Settings'] as const;
type Tab=typeof tabs[number];
const tabLabel:Record<Tab,string>={Overview:T('Overview'),Data:T('Add records'),Invoices:T('Invoices'),'Cash flow':T('Cash flow'),Financing:T('Loans'),Assistant:T('Assistant'),Approvals:T('Approvals'),Audit:T('Activity'),Settings:T('Settings')};
const pageTitle:Record<Tab,string>={Overview:T('Financial overview'),Data:T('Add your records'),Invoices:T('Invoices'),'Cash flow':T('Cash flow'),Financing:T('Loan offers'),Assistant:T('Assistant'),Approvals:T('Payment approvals'),Audit:T('Activity'),Settings:T('Settings')};

function Basis({count}:{count:number}){return <p className="small muted">{t('Based on {count} of your records.',{count})}</p>;}
function Notes({values}:{values:string[]}){return <ul className="notes">{values.map((v,i)=><li key={i}>{t(v)}</li>)}</ul>;}
function Metric({label,value,hint}:{label:string;value:number;hint?:string}){const {money}=useCurrency();return <article className="metric"><p>{label}</p><strong className={value<0?'negative':''}>{money(value)}</strong>{hint&&<small>{hint}</small>}</article>;}
function Panel({title,children}:{title:string;children:ReactNode}){return <section className="panel"><h2>{title}</h2>{children}</section>;}

type WorkspaceProps={token:string;session:Session;logout:()=>void;expired:()=>void;changeSession:(session:Session)=>void};
export default function Workspace(props:WorkspaceProps){
  const [currency,setCurrency]=useState('BDT');
  return <CurrencyProvider currency={currency} fetchRate={(from,to)=>fxRate(from,to)} storageKey={`safeledger-currency-view-v2:${props.session.user_id}:${props.session.business_id}`}><WorkspaceContent {...props} setCurrency={setCurrency}/></CurrencyProvider>;
}

const AUDIT_TEXT:Record<string,string>={IMPORTED:T('Records imported'),RECORD_ADDED:T('Record added'),PROPOSED:T('Payment prepared for approval'),APPROVED:T('Payment approved'),REJECTED:T('Payment rejected'),EXECUTED:T('Payment recorded'),EXPIRED:T('A payment proposal expired'),DENIED:T('An action was blocked'),IDEMPOTENT_REPLAY:T('A repeated approval was ignored'),FINANCING_ANALYZED:T('Loan offers compared'),INVITATION_CREATED:T('Invitation created'),WORKSPACE_JOINED:T('Someone joined this workspace'),WORKSPACE_CREATED:T('Workspace created'),CURRENCY_CHANGED:T('Currency changed'),PAYEE_PERMISSION_CHANGED:T('Supplier permission changed'),ACCOUNT_RECOVERED:T('Account recovered'),MEMBER_REMOVED:T('Someone was removed'),MEMBER_ROLE_CHANGED:T('A role was changed'),MEMBER_LEFT:T('Someone left this workspace')};

function WorkspaceContent({token,session,logout,expired,changeSession,setCurrency}:WorkspaceProps&{setCurrency:(currency:string)=>void}){
  const {currency,money,nativeMoney,parseMinor}=useCurrency();
  const [chatOpen,setChatOpen]=useState(false);const [chatLoaded,setChatLoaded]=useState(false);
  const chatButton=useRef<HTMLButtonElement>(null);
  function closeChat(){setChatOpen(false);chatButton.current?.focus();}
  const [tab,setTab]=useState<Tab>('Overview');
  const tourNavigate=useCallback((page:string)=>{setTab(page as Tab);setSelected(null);setChatOpen(false);},[]);
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [invoices,setInvoices]=useState<Invoice[]>([]);
  const [events,setEvents]=useState<CashEvent[]>([]);
  const [proposals,setProposals]=useState<Proposal[]>([]);
  const [audit,setAudit]=useState<Audit|null>(null);
  const [week,setWeek]=useState<Forecast|null>(null);
  const [forecast,setForecast]=useState<Forecast|null>(null);
  const [baselineMonth,setBaselineMonth]=useState<Forecast|null>(null);
  const [error,setError]=useState('');const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(true);const [missing,setMissing]=useState(false);const [exporting,setExporting]=useState(false);
  const [reserve,setReserve]=useState('0');const [delay,setDelay]=useState('0');
  const [query,setQuery]=useState('');const [selected,setSelected]=useState<Proposal|null>(null);
  const [revision,setRevision]=useState('');
  const [profile,setProfile]=useState<Profile|null>(null);
  const setPreferredCode=usePreferredCurrency();const {setLanguage}=useI18n();
  useEffect(()=>{setPreferredCode(profile?.display_currency||'USD');},[profile?.display_currency,setPreferredCode]);
  useEffect(()=>{if(profile?.language&&profile.language!=='en'&&!hasChosenLanguage())setLanguage(profile.language);},[profile?.language,setLanguage]);
  const [lists,setLists]=useState<{workspaces:WorkspaceItem[];cleared:WorkspaceItem[]}>({workspaces:[],cleared:[]});
  const [cloudAvailable,setCloudAvailable]=useState(false);
  const scope=useRef(new AbortController());
  const request=<T,>(path:string,body?:unknown)=>client(token,scope.current.signal,expired)<T>(path,body);
  const actionLock=useRef(false);
  function report(e:unknown){if(!scope.current.signal.aborted)setError(e instanceof Error?e.message:'Request failed');}
  async function reloadProfile(){try{const p=await request<Profile>('/account/profile');if(!scope.current.signal.aborted)setProfile(p);}catch{/* The profile is optional for viewing records. */}}
  async function reloadLists(){try{const l=await request<{workspaces:WorkspaceItem[];cleared:WorkspaceItem[]}>('/account/workspaces');if(!scope.current.signal.aborted)setLists(l);}catch{/* The workspace menu falls back to the current workspace. */}}
  async function refresh(){
    const mine=scope.current;  // this call belongs to one mount: a newer mount must not make an aborted call look current
    try{
      const data=await request<{dataset_revision:string;snapshot:Snapshot;invoices:Invoice[];events:CashEvent[];proposals:Proposal[];audit:Audit;week:Forecast;month:Forecast;policy:{reserve_minor:number;payment_limit_minor:number}}>('/workspace');
      if(mine.signal.aborted)return;
      setRevision(data.dataset_revision);setSnapshot(data.snapshot);setCurrency(data.snapshot.currency);setInvoices(data.invoices);setEvents(data.events);setProposals(data.proposals);setAudit(data.audit);
      setWeek(data.week);setForecast(data.month);setBaselineMonth(data.month);
      setReserve(String(data.policy.reserve_minor/10**currencyDigits(data.snapshot.currency)));setDelay('0');setMissing(false);
    }catch(e){
      if(mine.signal.aborted)return;
      setSnapshot(null);setInvoices([]);setEvents([]);setProposals([]);setAudit(null);setWeek(null);setForecast(null);setBaselineMonth(null);
      const noData=e instanceof ApiError&&e.code==='DATASET_NOT_FOUND';setMissing(noData);if(!noData)report(e);
    }
  }
  async function run(action:()=>Promise<void>){
    if(actionLock.current)return;actionLock.current=true;setBusy(true);setError('');setMessage('');
    const mine=scope.current;
    try{await action();}catch(e){if(!mine.signal.aborted)report(e);}finally{if(mine===scope.current){actionLock.current=false;if(!mine.signal.aborted)setBusy(false);}}
  }
  useEffect(()=>{
    // StrictMode remounts effects in development; each mount gets its own cancellation scope.
    const controller=new AbortController();scope.current=controller;actionLock.current=false;
    void run(refresh);void reloadProfile();void reloadLists();
    void accountRequest<{cloud_assist:boolean}>('/auth/capabilities',undefined,controller.signal).then(c=>setCloudAvailable(c.cloud_assist)).catch(()=>{});
    return()=>controller.abort();
    // The workspace is keyed by session. It cannot reuse another session's financial state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  async function importRaw(raw:string){let saved=false;await run(async()=>{const r=await fetch('/api/workspace/import',{method:'POST',credentials:'same-origin',headers:{...(token?{Authorization:`Bearer ${token}`}:{}),'Content-Type':'application/json','X-SafeLedger-Client':'web'},body:raw,signal:AbortSignal.any([scope.current.signal,AbortSignal.timeout(90000)])});const data=await r.json();if(r.status===401)expired();if(!r.ok)throw new Error(data?.error?.fields?.map((x:{field:string;message:string})=>`${x.field}: ${x.message}`).join('; ')||data?.error?.code||'Import failed.');if(data.simulation_only!==true)throw new Error('Invalid server response.');saved=true;await refresh();setMessage('Records imported. Allow each supplier before preparing payments.');});if(!saved)throw new Error('The import was not completed. See the message above.');}
  async function propose(invoiceId:string){
    const proposal=await request<Proposal>('/proposals',{invoice_id:invoiceId});
    setSelected(proposal);await refresh();setTab('Approvals');setMessage(t('Payment prepared. Nothing is paid yet: a second person must approve it.'));
  }
  async function decide(proposal:Proposal,decision:'approve'|'reject'){
    const result=await request<{state:string}>(`/proposals/${proposal.proposal_id}/approve`,{proposal_hash:proposal.action_hash,decision});
    setSelected(null);await refresh();
    setMessage(result.state==='EXECUTED'?t('Payment recorded in your books. Your balance and activity are updated.'):t('Payment rejected. Nothing was recorded.'));
  }
  function save(blob:Blob,name:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function exportJson(){await run(async()=>{const data=await request('/workspace/export');save(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),'capzoryx-backup.json');setMessage(t('Backup file downloaded. It contains your financial records, so keep it private.'));});}
  async function exportPdf(){
    if(!snapshot||exporting)return;setExporting(true);setError('');
    try{
      const {downloadPdf}=await import('./exportPdf');
      await downloadPdf({workspace:session.workspace_name||lists.workspaces.find(w=>w.business_id===session.business_id)?.name||t('My workspace'),owner:profile?.display_name||session.username||'',currency,snapshot,week,month:baselineMonth,invoices,events,proposals},`capzoryx-report-${snapshot.as_of}.pdf`);
      setMessage('Your PDF report was downloaded.');
    }catch(e){report(e);}finally{setExporting(false);}
  }
  async function switchTo(id:string){
    if(id===session.business_id)return;
    await run(async()=>{changeSession(await request<Session>('/account/switch',{business_id:id}));});
  }
  const canPropose=session.role==='owner';
  const name=profile?.display_name||session.display_name||session.username||'You';
  const number=(id:string)=>invoices.find(i=>i.invoice_id===id)?.invoice_number||'';
  const visible=invoices.filter(i=>`${i.vendor_id} ${i.invoice_number}`.toLowerCase().includes(query.toLowerCase()));
  return <div className="shell"><aside>
    <Brand/>
    <nav aria-label={t('Workspace')}>{tabs.map(tb=><button key={tb} data-tour={tb} aria-current={tab===tb?'page':undefined} onClick={()=>{setTab(tb);setSelected(null);if(tb==='Assistant'){setChatLoaded(true);setChatOpen(false);}}}><Icon name={tb}/>{t(tabLabel[tb])}</button>)}</nav>
    <div className="identity">
      <button className="identity-user" onClick={()=>setTab('Settings')} title={t('Open your profile and settings')}><Avatar profile={profile} name={name}/><span><strong>{name}</strong><small>{session.role==='owner'?t('Owner'):session.role==='approver'?t('Approver'):t('Viewer')}</small></span></button>
      {lists.workspaces.length>1&&<><label htmlFor="workspace-switch" className="sr-only">{t('Switch workspace')}</label><select id="workspace-switch" value={session.business_id} disabled={busy} onChange={e=>void switchTo(e.target.value)}>{lists.workspaces.map(w=><option key={w.business_id} value={w.business_id}>{workspaceLabel(w.name)}{w.currency?` · ${w.currency}`:''}{w.role!=='owner'?' · '+t('shared'):''}</option>)}</select></>}
      <LanguagePicker compact id="language-side" onPicked={code=>{void request('/account/profile',{language:code}).catch(()=>{});}}/>
      <button className="secondary" onClick={logout}>{t('Sign out')}</button></div></aside>
    <main id="workspace"><header><div><p className="eyebrow">{workspaceLabel(session.workspace_name||'My workspace')}</p><h1>{t(pageTitle[tab])}</h1><p className="muted">{snapshot?t('Up to date as of {date} · {currency}',{date:formatDate(snapshot.as_of),currency}):t('Your business finances in one place')}</p></div>
      <div className="header-actions"><QuickTour ready={!!snapshot&&!busy} userId={session.user_id} currentPage={tab} navigate={tourNavigate}/><ThemeButton/><button className="secondary" disabled={busy||!snapshot||exporting} onClick={()=>void exportPdf()}>{exporting?t('Preparing PDF…'):t('Download PDF')}</button><button className="secondary" disabled={busy} onClick={()=>void run(refresh)}>{t('Refresh')}</button></div></header>
      <CurrencyControls key={currency} ready={!!snapshot}/>
      <div aria-live="polite" role="status">{busy&&<p className="notice">{t('Loading your latest data…')}</p>}{message&&<p className="success">{message}</p>}</div>
      {error&&<p className="error" role="alert">{error}</p>}
      {profile&&profile.email&&!profile.email_verified&&profile.email_service&&tab!=='Settings'&&<p className="notice">{t('Verify your email so you can reset your password with a code.')} <button className="link" onClick={()=>setTab('Settings')}>{t('Verify now')}</button></p>}
      {profile&&!profile.email&&tab==='Overview'&&<p className="notice">{t('Add an email address to reset your password with a code if you ever forget it.')} <button className="link" onClick={()=>setTab('Settings')}>{t('Add email')}</button></p>}
      {missing&&<p className="notice">Nothing here yet. {session.role==='owner'?<button className="link" onClick={()=>setTab('Data')}>{t('Add your first record')}</button>:t('Ask the owner to add records.')}</p>}
      {tab==='Overview'&&<Dashboard snapshot={snapshot} week={week} month={baselineMonth} invoices={invoices} events={events} proposals={proposals} audit={audit} navigate={t=>setTab(t as Tab)} openAssistant={()=>{setChatLoaded(true);setChatOpen(true);}} onSample={session.role==='owner'&&!!snapshot&&snapshot.opening_balance_minor===0&&snapshot.income_minor===0&&snapshot.expenses_minor===0&&invoices.length===0&&proposals.length===0?()=>void importRaw(sampleBusiness(snapshot.currency)).catch(e=>report(e)):undefined}/>}
      {tab==='Invoices'&&<Panel title={t('Invoices')}>
        <label htmlFor="invoice-search">{t('Search by supplier or invoice number')}</label><input id="invoice-search" type="search" value={query} onChange={e=>setQuery(e.target.value)}/>
        <p className="muted">{visible.length} {visible.length===1?'invoice':'invoices'}. A possible duplicate pauses payment until you review it.</p>
        <div className="table-wrap" tabIndex={0} role="region" aria-label={t('Scrollable table')}><table><caption className="sr-only">{t('Your supplier invoices')}</caption><thead><tr><th>{t('Supplier')}</th><th>{t('Invoice')}</th><th>{t('Due')}</th><th>{t('Amount')}</th><th>{t('Status')}</th></tr></thead><tbody>
          {visible.map(i=><tr key={i.invoice_id}><td><strong>{prettyVendor(i.vendor_id)}</strong></td><td>{i.invoice_number}{i.memo&&<details><summary>{t('Note')}</summary><p>{i.memo}</p></details>}</td><td>{formatDate(i.due_on)}{i.status==='open'&&snapshot&&i.due_on<snapshot.as_of&&<small className="negative">{t('Overdue')}</small>}</td><td className="amount">{money(i.amount_minor)}</td>
            <td><span className="badge">{i.status==='open'?t('To pay'):'Paid'}</span>
              {i.status==='open'&&session.role==='owner'&&<details><summary>{t('Supplier permission')}</summary><button className="secondary small" disabled={busy} onClick={()=>void run(async()=>{await request('/workspace/vendor-permission',{vendor_id:i.vendor_id,enabled:true});setMessage(t('This supplier can now be paid through approvals.'));})}>{t('Allow payments to this supplier')}</button><button className="secondary small" disabled={busy} onClick={()=>void run(async()=>{await request('/workspace/vendor-permission',{vendor_id:i.vendor_id,enabled:false});setMessage(t('Payments to this supplier are blocked.'));})}>{t('Block this supplier')}</button></details>}
              {i.status==='open'&&session.role==='approver'&&<small className="muted">{t('Approvers review payments the owner prepares.')}</small>}
              {i.status==='open'&&canPropose&&<button className="small" disabled={busy} onClick={()=>void run(()=>propose(i.invoice_id))} aria-label={`Prepare payment for ${i.invoice_number}`}>{t('Prepare payment')}</button>}</td></tr>)}</tbody></table></div>
        {!visible.length&&<p>{t('No invoices match. Add a bill on the')} <button className="link" onClick={()=>setTab('Data')}>{t('Add records')}</button> {t('page, or photograph one.')}</p>}</Panel>}
      {tab==='Cash flow'&&<><Panel title={t('Where your cash is heading')}>
        <form className="form-row" onSubmit={e=>{e.preventDefault();void run(async()=>{if(!snapshot)throw new Error(t('Add a record first.'));const result=await request<Forecast>('/cashflow/scenarios',{as_of:snapshot.as_of,horizon_days:30,reserve_minor:parseMinor(reserve),delay_inflows_days:Number(delay)});setForecast(result);});}}>
          <label>{t('Cash you want to keep as a safety reserve ({currency})',{currency})}<input value={reserve} onChange={e=>setReserve(e.target.value)} inputMode="decimal" required/></label>
          <label>{t('What if customers pay late?')}<select value={delay} onChange={e=>setDelay(e.target.value)}>{[0,7,14,30].map(n=><option key={n} value={n}>{n===0?t('On time'):`${n} days late`}</option>)}</select></label>
          <button disabled={busy||!snapshot}>{t('Update forecast')}</button></form>
        <p className="muted">{t('Try “what if” changes here. They never change your records.')}</p>
        {forecast&&<><div className="metrics"><Metric label={t('Balance in 30 days')} value={forecast.closing_balance_minor}/><Metric label={t('Lowest balance')} value={forecast.minimum_balance_minor}/><article className="metric"><p>{t('First time below your reserve')}</p><strong>{forecast.first_shortfall_on?formatDate(forecast.first_shortfall_on):t('Never')}</strong></article></div><CashChart forecast={forecast}/><Basis count={forecast.source_ids.length}/><Notes values={forecast.assumptions}/></>}</Panel>
        {forecast&&<Panel title={t('Warnings and daily detail')}>
          {forecast.risk_flags.map((risk,n)=><div className="notice" key={n}><strong>{risk.risk==='DUPLICATE_POSSIBLE'?t('Possible duplicate bill'):risk.risk==='DUPLICATE_EXACT'?t('Duplicate bill'):risk.risk.replaceAll('_',' ').toLowerCase()}</strong><p>{risk.invoice_ids.map(number).filter(Boolean).join(', ')} · {risk.execution_blocked?'Payment is paused until you review it.':t('Review before paying.')}</p></div>)}
          <div className="table-wrap" tabIndex={0} role="region" aria-label={t('Scrollable table')}><table><caption>{t('Next 30 days')}</caption><thead><tr><th>{t('Date')}</th><th>{t('In')}</th><th>{t('Out')}</th><th>{t('Balance')}</th></tr></thead><tbody>{forecast.days.map(d=><tr key={d.date}><td>{formatDate(d.date)}</td><td>{money(d.inflow_minor)}</td><td>{money(d.outflow_minor)}</td><td className={d.projected_balance_minor<0?'negative':''}>{money(d.projected_balance_minor)}</td></tr>)}</tbody></table></div></Panel>}</>}
      {tab==='Financing'&&<Financing snapshot={snapshot} forecast={baselineMonth} session={session} request={request}/>}
      {tab==='Approvals'&&<Panel title={t('Approve payments')}>
        <p>{t('A second person approves each payment you prepare. Approving records the payment in your books; no money moves from a bank. Proposals expire after 15 minutes.')}</p>
        {selected&&<ProposalDetails proposal={selected} number={number(selected.details.invoice_id)}/>}
        {!proposals.length&&<p>{t('Nothing to approve yet. Open')} <button className="link" onClick={()=>setTab('Invoices')}>{t('Invoices')}</button> {t('and choose Prepare payment.')}</p>}
        <div className="proposal-list">{proposals.map(p=><article key={p.proposal_id} className="proposal"><div><span className="badge">{p.state==='AWAITING_APPROVAL'?t('Waiting'):p.state==='EXECUTED'?'Paid':p.state==='REJECTED'?t('Rejected'):p.state==='EXPIRED'?t('Expired'):p.state}</span><h3>{prettyVendor(p.details.vendor_id)} · {nativeMoney(p.details.amount_minor)}</h3><p>{number(p.details.invoice_id)&&`Invoice ${number(p.details.invoice_id)} · `}{t('Prepared by')} {p.details.proposer_id===session.user_id?t('you'):'a teammate'}</p>{p.state==='AWAITING_APPROVAL'&&<small>{t('Expires {time}',{time:formatTime(p.details.expires_at)})}</small>}</div>
          <button className="secondary" onClick={()=>setSelected(p)}>{t('Details')}</button>{p.state==='AWAITING_APPROVAL'&&session.role==='approver'&&<button disabled={busy} onClick={()=>setSelected(p)}>{t('Review and decide')}</button>}</article>)}</div>
        {selected&&selected.state==='AWAITING_APPROVAL'&&session.role==='approver'&&<ApprovalDialog proposal={selected} number={number(selected.details.invoice_id)} error={error} balance={snapshot?.balance_minor} busy={busy} onClose={()=>setSelected(null)} onDecision={d=>void run(()=>decide(selected,d))}/>}</Panel>}
      {tab==='Audit'&&<Panel title={t('Everything that happened')}>
        {audit?<><p className={audit.chain_verified?'success':'error'}>{audit.chain_verified?t('History verified: nothing has been changed or removed.'):t('History could not be verified. Contact support.')}</p>
          {!audit.events.length&&<p>{t('No activity yet.')}</p>}
          <ol className="audit-list">{audit.events.slice().reverse().map(event=>{const p=(event.payload||{}) as Record<string,unknown>;const who=event.actor_id===session.user_id?'You':t('A teammate');return <li key={event.event_id}><strong>{t(AUDIT_TEXT[event.kind]||'')||event.kind.replaceAll('_',' ').toLowerCase()}</strong><small>{formatTime(event.created_at)} · {who}{typeof p.note==='string'&&p.note?` · ${p.note}`:''}{event.kind==='EXECUTED'&&typeof p.cash_delta_minor==='number'?` · ${nativeMoney(Math.abs(p.cash_delta_minor))}`:''}{event.kind==='DENIED'?' · blocked by a safety rule':''}</small></li>;})}</ol>
          <details className="advanced"><summary>{t('For auditors')}</summary><p className="muted small">{t('Each entry is linked to the one before it and signed by the server, so any later change is detectable.')} {t('This is not a claim of protection from the system administrator.')}</p><button className="secondary" onClick={()=>save(new Blob([JSON.stringify(audit,null,2)],{type:'application/json'}),'capzoryx-activity-log.json')}>{t('Download the full signed log')}</button></details></>:<p>{t('Activity is unavailable. Refresh to try again.')}</p>}</Panel>}
      {tab==='Data'&&<>
        <QuickAdd request={request} revision={revision} profile={profile} cloudAvailable={cloudAvailable} onSaved={async()=>{await refresh();}}/>
        <DataEntry events={events} session={session} revision={revision} snapshot={snapshot} busy={busy} submit={async body=>{let saved=false;await run(async()=>{await request('/workspace/records',body);saved=true;await refresh();setMessage(t('Record saved. Your balance, forecast and activity are updated.'));});if(!saved)throw new Error(t('The record was not saved. Check the message above and try again.'));}}/>
        {session.role==='owner'&&<ImportEvidence busy={busy} enabled={!!snapshot&&snapshot.opening_balance_minor===0&&snapshot.income_minor===0&&snapshot.expenses_minor===0&&invoices.length===0&&proposals.length===0} upload={importRaw}/>}</>}
      {tab==='Settings'&&<LazyBoundary><Suspense fallback={<section className="panel" role="status">{t('Opening settings…')}</section>}><Settings session={session} profile={profile} request={request} reloadProfile={reloadProfile} changeSession={changeSession} lists={lists} reloadLists={reloadLists} onExportPdf={exportPdf} onExportJson={exportJson} exporting={exporting} cloudAvailable={cloudAvailable}/></Suspense></LazyBoundary>}
      {chatLoaded&&<div id="workspace-assistant" hidden={tab!=='Assistant'&&!chatOpen} className={tab==='Assistant'?'assistant-page':'chat-float'} onKeyDown={(e:KeyboardEvent)=>{if(e.key==='Escape'&&tab!=='Assistant')closeChat();}}><LazyBoundary><Suspense fallback={<section className="panel" role="status">{t('Opening assistant…')}</section>}><Assistant visible={tab==='Assistant'||chatOpen} snapshot={snapshot} forecast={baselineMonth} week={week} events={events} invoices={invoices} session={session} profile={profile} cloudAvailable={cloudAvailable} revision={revision} request={request} onSaved={refresh} onNavigate={action=>{setTab(action);closeChat();}} onProposal={async()=>{await refresh();setTab('Approvals');closeChat();}} onClose={tab==='Assistant'?undefined:closeChat}/></Suspense></LazyBoundary></div>}
      {tab!=='Assistant'&&<button ref={chatButton} className="chat-launcher" aria-label={chatOpen?t('Close assistant'):t('Open assistant')} aria-expanded={chatOpen} aria-controls="workspace-assistant" onClick={()=>{setChatLoaded(true);setChatOpen(!chatOpen);}}><Icon name="spark"/> <span>{chatOpen?t('Close'):t('Assistant')}</span></button>}
      <footer>{t('Capzoryx Copilot · Your records · A second person approves every payment · Nothing leaves your control')}</footer></main></div>;
}

function ProposalDetails({proposal:p,number}:{proposal:Proposal;number:string}){
  const {nativeMoney:money}=useCurrency();
  return <article className="proposal-detail"><h3>{t('Payment details')}</h3><dl><div><dt>{t('Supplier')}</dt><dd>{prettyVendor(p.details.vendor_id)}</dd></div>{number&&<div><dt>{t('Invoice')}</dt><dd>{number}</dd></div>}<div><dt>{t('Amount')}</dt><dd>{money(p.details.amount_minor)}</dd></div></dl>{p.preview&&<p>You have {money(p.preview.available_minor)} now; after this payment {money(p.preview.after_payment_minor)}. Safety reserve: {money(p.preview.reserve_minor)}. Payment limit: {money(p.preview.payment_limit_minor)}.</p>}<p className="muted">{t('The amount, supplier and your balance are checked again when this is approved.')}</p></article>;
}
function ApprovalDialog({proposal,number,error,balance,busy,onClose,onDecision}:{proposal:Proposal;number:string;error:string;balance?:number;busy:boolean;onClose:()=>void;onDecision:(decision:'approve'|'reject')=>void}){
  const {nativeMoney:money}=useCurrency();
  const dialog=useRef<HTMLDialogElement>(null);const [confirmed,setConfirmed]=useState(false);
  useEffect(()=>{const current=dialog.current;const opener=document.activeElement as HTMLElement|null;current?.showModal();return()=>{current?.close();opener?.focus();};},[]);
  function containFocus(event:KeyboardEvent<HTMLDialogElement>){
    if(event.key!=='Tab')return;
    const items=Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],summary,[tabindex]:not([tabindex="-1"])')).filter(el=>el.getClientRects().length>0);
    const first=items[0],last=items.at(-1);
    if(!first){event.preventDefault();event.currentTarget.focus();return;}
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
  }
  return <dialog ref={dialog} onKeyDown={containFocus} aria-labelledby="approval-title" onCancel={e=>{if(busy)e.preventDefault();else onClose();}}><h2 id="approval-title">{t('Approve this payment?')}</h2><ProposalDetails proposal={proposal} number={number}/>{balance!==undefined&&<p>{t('Your balance now: {amount}.',{amount:money(balance)})}</p>}{error&&<p className="error" role="alert">{error}</p>}<p>{t('Approving records this payment in your books. No bank transfer is made.')}</p><label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={busy}/>{t('I checked the supplier and the amount.')}</label><div className="actions"><button disabled={busy||!confirmed} onClick={()=>onDecision('approve')}>{busy?t('Working…'):t('Approve and record')}</button><button className="danger" disabled={busy||!confirmed} onClick={()=>onDecision('reject')}>{t('Reject')}</button><button className="secondary" disabled={busy} onClick={onClose}>{t('Cancel')}</button></div></dialog>;
}
