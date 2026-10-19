import {useCallback,useEffect,useRef,useState,type FormEvent,type ReactNode} from 'react';
import {CurrencySelect} from './Currency';
import {PasswordStrength} from './PasswordStrength';
import {formatTime,initials,prepareAvatar} from './format';
import {Avatar} from './Avatar';
import type {Invitation,Member,Profile,Session,WorkspaceItem} from './types';

type Request=<T>(path:string,body?:unknown)=>Promise<T>;
type Lists={workspaces:WorkspaceItem[];cleared:WorkspaceItem[]};
export type SettingsProps={session:Session;profile:Profile|null;request:Request;reloadProfile:()=>Promise<void>;changeSession:(s:Session)=>void;lists:Lists;reloadLists:()=>Promise<void>;onExportPdf:()=>Promise<void>;onExportJson:()=>Promise<void>;exporting:boolean;cloudAvailable:boolean};
const tabs=['Profile','Security','Sharing','Data'] as const;
type Tab=typeof tabs[number];
const tabNames:Record<Tab,string>={Profile:'Profile',Security:'Password & 2-step',Sharing:'Sharing',Data:'Data & workspaces'};

function Section({title,hint,children}:{title:string;hint?:string;children:ReactNode}){return <section className="panel settings-section"><h2>{title}</h2>{hint&&<p className="muted">{hint}</p>}{children}</section>;}
function useMessage(){const [m,setM]=useState<{kind:'ok'|'error';text:string}|null>(null);return {message:m,ok:(text:string)=>setM({kind:'ok',text}),fail:(e:unknown)=>setM({kind:'error',text:e instanceof Error?e.message:'Something went wrong. Please try again.'}),clear:()=>setM(null)};}
function Notice({m}:{m:{kind:'ok'|'error';text:string}|null}){return m?<p className={m.kind==='ok'?'success':'error'} role={m.kind==='ok'?'status':'alert'}>{m.text}</p>:null;}

export default function Settings(props:SettingsProps){
  const [tab,setTab]=useState<Tab>('Profile');
  const {session,profile}=props;
  const name=profile?.display_name||session.display_name||session.username||'You';
  return <div className="settings">
    <div className="settings-head"><Avatar profile={profile} name={name} size={56}/><div><h2>{name}</h2><p className="muted">{profile?.email||session.username}</p></div></div>
    <div className="settings-tabs" role="tablist" aria-label="Settings sections">{tabs.map(t=><button key={t} role="tab" aria-selected={tab===t} className={tab===t?'active':'secondary'} onClick={()=>setTab(t)}>{tabNames[t]}</button>)}</div>
    {tab==='Profile'&&<ProfileTab {...props}/>}
    {tab==='Security'&&<SecurityTab {...props}/>}
    {tab==='Sharing'&&<SharingTab {...props}/>}
    {tab==='Data'&&<DataTab {...props}/>}
  </div>;
}

function ProfileTab({session,profile,request,reloadProfile,cloudAvailable}:SettingsProps){
  const info=useMessage();const mail=useMessage();
  const [name,setName]=useState(profile?.display_name||'');const [email,setEmail]=useState(profile?.email||'');const [code,setCode]=useState('');const [busy,setBusy]=useState(false);
  const file=useRef<HTMLInputElement>(null);
  useEffect(()=>{setName(profile?.display_name||'');setEmail(profile?.email||'');},[profile?.display_name,profile?.email]);
  async function run(task:()=>Promise<void>,report:{ok:(t:string)=>void;fail:(e:unknown)=>void},done:string){setBusy(true);try{await task();await reloadProfile();report.ok(done);}catch(e){report.fail(e);}finally{setBusy(false);}}
  return <>
    <Section title="Your profile" hint="Your name and picture are shown to people you share a workspace with.">
      <div className="profile-row"><Avatar profile={profile} name={name||session.username||''} size={72}/>
        <div className="actions"><input ref={file} type="file" accept="image/*" hidden onChange={e=>{const f=e.target.files?.[0];if(f)void run(async()=>{await request('/account/photo',{image:await prepareAvatar(f)});},info,'Photo updated.');if(file.current)file.current.value='';}}/>
          <button className="secondary" disabled={busy} onClick={()=>file.current?.click()}>{profile?.photo?'Change photo':'Add a photo'}</button>
          {profile?.photo&&<button className="secondary" disabled={busy} onClick={()=>void run(async()=>{await request('/account/photo/remove',{});},info,'Photo removed.')}>Remove</button>}</div></div>
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();void run(async()=>{await request('/account/profile',{display_name:name});},info,'Name saved.');}}>
        <label htmlFor="display-name">Your name</label><input id="display-name" value={name} maxLength={60} onChange={e=>setName(e.target.value)} placeholder="How should we call you?" autoComplete="name"/>
        <label htmlFor="settings-username">Username</label><input id="settings-username" value={profile?.username||session.username||''} readOnly aria-readonly="true"/>
        <button disabled={busy}>Save name</button></form>
      <Notice m={info.message}/>
    </Section>
    <Section title="Email" hint="Add your email to reset your password with a code, and to receive workspace invitations.">
      <p>{profile?.email?<>Current: <strong>{profile.email}</strong> {profile.email_verified?<span className="badge">Verified</span>:<span className="badge warn">Not verified</span>}</>:'No email added yet.'}</p>
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();void run(async()=>{const r=await request<{sent:boolean;email_service:boolean}>('/account/email',{email});if(!r.email_service)throw new Error('Email is saved, but this site cannot send codes yet. You can still reset your password with your recovery key.');if(!r.sent)throw new Error('We could not send the code. Please try again.');},mail,'We sent a 6-digit code to that address. Enter it below.');}}>
        <label htmlFor="email">{profile?.email?'Change email':'Email address'}</label><input id="email" type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/>
        <button disabled={busy||!email.trim()}>{profile?.email&&!profile.email_verified?'Send a new code':'Save and send code'}</button></form>
      {profile?.email&&!profile.email_verified&&<form onSubmit={(e:FormEvent)=>{e.preventDefault();void run(async()=>{await request('/account/email/verify',{code});setCode('');},mail,'Email verified.');}}>
        <label htmlFor="email-code">6-digit code</label><input id="email-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))}/><button disabled={busy||code.length!==6}>Verify email</button></form>}
      <Notice m={mail.message}/>
    </Section>
    <Section title="Smart assist" hint="When the assistant cannot answer on your device, it can ask a cloud AI. It also reads photos of bills and receipts. Only your question or photo and a short summary of your figures are sent; nothing is stored by us for training.">
      <label className="check"><input type="checkbox" checked={profile?.smart_assist??true} disabled={busy||!cloudAvailable} onChange={e=>void run(async()=>{await request('/account/profile',{smart_assist:e.target.checked});},info,e.target.checked?'Smart assist is on.':'Smart assist is off.')}/>Use smart assist for answers and for reading photos</label>
      {!cloudAvailable&&<p className="small muted">Smart assist is not available on this site right now.</p>}
    </Section>
  </>;
}

function SecurityTab({profile,request,reloadProfile}:SettingsProps){
  const pw=useMessage();const tf=useMessage();
  const [current,setCurrent]=useState('');const [next,setNext]=useState('');const [show,setShow]=useState(false);const [busy,setBusy]=useState(false);
  const [setup,setSetup]=useState<{secret:string;uri:string;qr:string}|null>(null);const [step,setStep]=useState<'idle'|'password'|'scan'|'done'|'off'>('idle');
  const [pass,setPass]=useState('');const [code,setCode]=useState('');const [backup,setBackup]=useState<string[]>([]);const [copied,setCopied]=useState(false);
  async function begin(){setBusy(true);tf.clear();try{const r=await request<{secret:string;uri:string}>('/account/2fa/setup',{password:pass});const QR=await import('qrcode');setSetup({...r,qr:await QR.toDataURL(r.uri,{margin:1,width:220})});setStep('scan');setPass('');setCode('');}catch(e){tf.fail(e);}finally{setBusy(false);}}
  async function enable(){setBusy(true);tf.clear();try{const r=await request<{backup_codes:string[]}>('/account/2fa/enable',{code});setBackup(r.backup_codes);setStep('done');setSetup(null);await reloadProfile();}catch(e){tf.fail(e);}finally{setBusy(false);}}
  async function disable(){setBusy(true);tf.clear();try{await request('/account/2fa/disable',{password:pass,code});setStep('idle');setPass('');setCode('');await reloadProfile();tf.ok('Two-step sign-in is off.');}catch(e){tf.fail(e);}finally{setBusy(false);}}
  return <>
    <Section title="Change password" hint="You will stay signed in here; every other device is signed out.">
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();setBusy(true);pw.clear();void request('/account/password',{current_password:current,new_password:next}).then(()=>{setCurrent('');setNext('');pw.ok('Password changed. Other devices were signed out.');}).catch(pw.fail).finally(()=>setBusy(false));}}>
        <label htmlFor="current-password">Current password</label><input id="current-password" type={show?'text':'password'} autoComplete="current-password" required value={current} onChange={e=>setCurrent(e.target.value)}/>
        <label htmlFor="new-password">New password</label><div className="password-field"><input id="new-password" type={show?'text':'password'} autoComplete="new-password" minLength={8} maxLength={128} required value={next} onChange={e=>setNext(e.target.value)}/><button type="button" className="secondary" onClick={()=>setShow(!show)}>{show?'Hide':'Show'}</button></div>
        <PasswordStrength password={next} username={profile?.username||''}/>
        <button disabled={busy||!current||next.length<8}>Change password</button></form>
      <Notice m={pw.message}/>
    </Section>
    <Section title="Two-step sign-in" hint="Adds a 6-digit code from an authenticator app (Google Authenticator, Microsoft Authenticator, Authy) when you sign in.">
      <p>Status: {profile?.two_factor?<span className="badge">On</span>:<span className="badge warn">Off</span>}</p>
      {!profile?.two_factor&&step==='idle'&&<button onClick={()=>setStep('password')}>Turn on two-step sign-in</button>}
      {step==='password'&&<form onSubmit={(e:FormEvent)=>{e.preventDefault();void begin();}}><label htmlFor="mfa-pass">Confirm your password</label><input id="mfa-pass" type="password" autoComplete="current-password" required value={pass} onChange={e=>setPass(e.target.value)}/><div className="actions"><button disabled={busy||!pass}>Continue</button><button type="button" className="secondary" onClick={()=>{setStep('idle');setPass('');}}>Cancel</button></div></form>}
      {step==='scan'&&setup&&<div className="mfa-setup"><ol><li>Open your authenticator app and scan this picture.</li><li>Enter the 6-digit code it shows.</li></ol><img className="qr" src={setup.qr} alt="QR code to add SafeLedger to your authenticator app" width={220} height={220}/>
        <details><summary>Can’t scan? Enter the key by hand</summary><code className="secret">{setup.secret.match(/.{1,4}/g)?.join(' ')}</code></details>
        <form onSubmit={(e:FormEvent)=>{e.preventDefault();void enable();}}><label htmlFor="mfa-code">6-digit code</label><input id="mfa-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))}/><div className="actions"><button disabled={busy||code.length!==6}>Turn on</button><button type="button" className="secondary" onClick={()=>{setStep('idle');setSetup(null);}}>Cancel</button></div></form></div>}
      {step==='done'&&<div className="backup-codes" role="status"><h3>Save your backup codes</h3><p>Each code works once if you lose your phone. They are shown only now.</p><ul>{backup.map(b=><li key={b}><code>{b}</code></li>)}</ul>
        <div className="actions"><button className="secondary" onClick={()=>void navigator.clipboard.writeText(backup.join('\n')).then(()=>setCopied(true)).catch(()=>setCopied(false))}>{copied?'Copied':'Copy codes'}</button><button className="secondary" onClick={()=>{const url=URL.createObjectURL(new Blob([backup.join('\n')+'\n'],{type:'text/plain'}));const a=document.createElement('a');a.href=url;a.download='safeledger-backup-codes.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Download</button><button onClick={()=>{setStep('idle');setBackup([]);}}>I saved them</button></div></div>}
      {profile?.two_factor&&step==='idle'&&<button className="secondary" onClick={()=>setStep('off')}>Turn off two-step sign-in</button>}
      {step==='off'&&<form onSubmit={(e:FormEvent)=>{e.preventDefault();void disable();}}><label htmlFor="off-pass">Password</label><input id="off-pass" type="password" autoComplete="current-password" required value={pass} onChange={e=>setPass(e.target.value)}/><label htmlFor="off-code">Code from your app, or a backup code</label><input id="off-code" required value={code} onChange={e=>setCode(e.target.value)}/><div className="actions"><button disabled={busy||!pass||!code}>Turn off</button><button type="button" className="secondary" onClick={()=>{setStep('idle');setPass('');setCode('');}}>Cancel</button></div></form>}
      <Notice m={tf.message}/>
    </Section>
  </>;
}

const age=(expires:number)=>{const h=Math.max(1,Math.round((expires*1000-Date.now())/3600_000));return h>=48?`${Math.round(h/24)} days`:`${h} hours`;};
function SharingTab({session,request,changeSession}:SettingsProps){
  const msg=useMessage();
  const [members,setMembers]=useState<Member[]>([]);const [invites,setInvites]=useState<Invitation[]>([]);const [loaded,setLoaded]=useState(false);
  const [role,setRole]=useState<'approver'|'viewer'>('approver');const [hours,setHours]=useState(72);const [email,setEmail]=useState('');
  const [link,setLink]=useState('');const [copied,setCopied]=useState(false);const [busy,setBusy]=useState(false);
  const owner=session.role==='owner';
  const load=useCallback(async()=>{try{const r=await request<{members:Member[];invitations:Invitation[]}>('/account/members');setMembers(r.members);setInvites(r.invitations);}catch(e){msg.fail(e);}finally{setLoaded(true);}},[request]);// eslint-disable-line react-hooks/exhaustive-deps
  useEffect(()=>{void load();},[load,session.business_id]);
  async function act(task:()=>Promise<void>,done:string){setBusy(true);msg.clear();try{await task();await load();msg.ok(done);}catch(e){msg.fail(e);}finally{setBusy(false);}}
  const label=(m:Member)=>m.display_name||m.username;
  return <>
    <Section title="People in this workspace" hint={owner?'Invite a teammate or your accountant. An approver can approve payments you prepare; a viewer can only look.':'You are in this workspace as '+session.role+'.'}>
      {!loaded?<p role="status">Loading…</p>:<ul className="people">{members.map(m=><li key={m.member_id}><span className="avatar avatar-initials" aria-hidden="true">{initials(label(m))}</span><div><strong>{label(m)}{m.you&&' (you)'}</strong><small>@{m.username} · {m.role==='owner'?'Owner':m.role==='approver'?'Approver':'Viewer'}</small></div>
        {owner&&m.role!=='owner'&&<div className="actions"><select aria-label={`Role for ${label(m)}`} value={m.role} disabled={busy} onChange={e=>void act(async()=>{await request('/account/members/role',{member_id:m.member_id,role:e.target.value});},'Role updated.')}><option value="approver">Approver</option><option value="viewer">Viewer</option></select><button className="secondary small" disabled={busy} onClick={()=>{if(confirm(`Remove ${label(m)} from this workspace?`))void act(async()=>{await request('/account/members/remove',{member_id:m.member_id});},'Removed.');}}>Remove</button></div>}</li>)}</ul>}
      {!owner&&<button className="secondary" disabled={busy} onClick={()=>{if(confirm('Leave this workspace? You can be invited again later.'))void act(async()=>{changeSession(await request<Session>('/account/leave',{}));},'You left the workspace.');}}>Leave this workspace</button>}
      <Notice m={msg.message}/>
    </Section>
    {owner&&<Section title="Invite someone" hint="Send them a link. They sign in or create a free account and are added automatically.">
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();void act(async()=>{const r=await request<{code:string;emailed:boolean}>('/account/invitations',{role,hours,...(email.trim()?{email:email.trim()}:{})});setLink(`${window.location.origin}/?join=${r.code}`);setCopied(false);setEmail('');if(email.trim()&&!r.emailed)throw new Error('The invitation link is ready below, but we could not email it. Copy the link and send it yourself.');},'Invitation ready. Copy the link below.');}}>
        <div className="form-grid"><label>They can<select value={role} onChange={e=>setRole(e.target.value as 'approver'|'viewer')}><option value="approver">Approve payments</option><option value="viewer">View only</option></select></label>
          <label>Link works for<select value={hours} onChange={e=>setHours(Number(e.target.value))}><option value={24}>1 day</option><option value={72}>3 days</option><option value={168}>7 days</option></select></label></div>
        <label htmlFor="invite-email">Their email (optional, we will email the link)</label><input id="invite-email" type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="friend@example.com"/>
        <button disabled={busy}>Create invitation</button></form>
      {link&&<div className="invite-code"><label htmlFor="invite-link">Invitation link</label><input id="invite-link" readOnly value={link} onFocus={e=>e.currentTarget.select()}/><button className="secondary" onClick={()=>void navigator.clipboard.writeText(link).then(()=>setCopied(true)).catch(()=>msg.fail(new Error('Select the link and copy it manually.')))}>{copied?'Copied':'Copy link'}</button></div>}
      {!!invites.length&&<><h3>Open invitations</h3><ul className="people">{invites.map(i=><li key={i.invite_id}><div><strong>{i.role==='approver'?'Approver':'Viewer'} invitation</strong><small>Expires in {age(i.expires_at)}</small></div><button className="secondary small" disabled={busy} onClick={()=>void act(async()=>{await request('/account/invitations/revoke',{invite_id:i.invite_id});},'Invitation cancelled.')}>Cancel</button></li>)}</ul></>}
    </Section>}
  </>;
}

function DataTab({session,request,changeSession,lists,reloadLists,onExportPdf,onExportJson,exporting}:SettingsProps){
  const msg=useMessage();const [busy,setBusy]=useState(false);
  const owned=lists.workspaces.filter(w=>w.role==='owner');
  const [picked,setPicked]=useState<string[]>([]);const [confirming,setConfirming]=useState(false);
  const [name,setName]=useState('');const [newName,setNewName]=useState('');const [newCurrency,setNewCurrency]=useState('USD');
  const current=lists.workspaces.find(w=>w.business_id===session.business_id);
  useEffect(()=>setName(current?.name||''),[current?.name]);
  async function act(task:()=>Promise<void>,done:string){setBusy(true);msg.clear();try{await task();await reloadLists();msg.ok(done);}catch(e){msg.fail(e);}finally{setBusy(false);}}
  const allPicked=owned.length>0&&picked.length===owned.length;
  return <>
    <Section title="Your reports" hint="Download your records as a clean PDF with your balance, invoices, activity and payments.">
      <div className="actions"><button disabled={exporting} onClick={()=>void onExportPdf()}>{exporting?'Preparing…':'Download PDF report'}</button><button className="secondary" disabled={exporting} onClick={()=>void onExportJson()}>Backup file (JSON)</button></div>
      <p className="small muted">The PDF uses this workspace’s own currency. The backup file is for restoring or moving your data.</p>
    </Section>
    <Section title="Switch data" hint="Each workspace keeps one currency, so your records never get mixed. Switch any time from the menu at the top.">
      <ul className="people">{lists.workspaces.map(w=><li key={w.business_id}><div><strong>{w.name}{w.business_id===session.business_id&&' · open now'}</strong><small>{w.currency||'—'} · {w.role==='owner'?'You own it':w.role==='approver'?'Shared with you (approver)':'Shared with you (viewer)'}</small></div>
        {w.business_id!==session.business_id&&<button className="secondary small" disabled={busy} onClick={()=>void act(async()=>{changeSession(await request<Session>('/account/switch',{business_id:w.business_id}));},'Switched.')}>Open</button>}</li>)}</ul>
      {session.role==='owner'&&<form onSubmit={(e:FormEvent)=>{e.preventDefault();void act(async()=>{await request('/account/workspaces/rename',{name});},'Renamed.');}}><label htmlFor="ws-name">Rename this workspace</label><input id="ws-name" value={name} maxLength={60} onChange={e=>setName(e.target.value)}/><button className="secondary" disabled={busy||!name.trim()||name===current?.name}>Save name</button></form>}
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();void act(async()=>{changeSession(await request<Session>('/account/workspaces',{kind:'personal',name:newName.trim()||newCurrency+' workspace',currency:newCurrency}));setNewName('');},'New workspace created.');}}><h3>Add a workspace for another currency</h3>
        <div className="form-grid"><label>Name (optional)<input value={newName} maxLength={60} onChange={e=>setNewName(e.target.value)} placeholder="e.g. Export sales"/></label><label htmlFor="new-ws-currency">Currency<CurrencySelect id="new-ws-currency" value={newCurrency} onChange={setNewCurrency}/></label></div><button className="secondary" disabled={busy}>Create workspace</button></form>
    </Section>
    <Section title="Clear data" hint="Hide the data of one or more currencies, or everything. Cleared data disappears from your account right away and can be restored for 30 days.">
      {!owned.length?<p className="muted">You do not own any workspace that can be cleared.</p>:<>
        <label className="check"><input type="checkbox" checked={allPicked} onChange={e=>setPicked(e.target.checked?owned.map(w=>w.business_id):[])}/>Select all</label>
        <ul className="people">{owned.map(w=><li key={w.business_id}><label className="check"><input type="checkbox" checked={picked.includes(w.business_id)} onChange={e=>setPicked(e.target.checked?[...picked,w.business_id]:picked.filter(x=>x!==w.business_id))}/><span><strong>{w.name}</strong><small> {w.currency||''} data</small></span></label></li>)}</ul>
        {!confirming?<button className="danger" disabled={!picked.length||busy} onClick={()=>setConfirming(true)}>Clear selected data…</button>:<div className="notice"><p><strong>Clear {picked.length===owned.length?'all your data':`${picked.length} ${picked.length===1?'workspace':'workspaces'}`}?</strong> People you shared it with lose access. You can restore it within 30 days.</p><div className="actions"><button className="danger" disabled={busy} onClick={()=>void act(async()=>{changeSession(await request<Session>('/account/workspaces/clear',{business_ids:picked}));setPicked([]);setConfirming(false);},'Data cleared. You can restore it below for 30 days.')}>Yes, clear it</button><button className="secondary" onClick={()=>setConfirming(false)}>Keep it</button></div></div>}</>}
      {!!lists.cleared.length&&<><h3>Recently cleared</h3><ul className="people">{lists.cleared.map(w=><li key={w.business_id}><div><strong>{w.name}</strong><small>{w.currency||''} · restore until {formatTime(w.restorable_until||0).split(',')[0]}</small></div><button className="secondary small" disabled={busy} onClick={()=>void act(async()=>{await request('/account/workspaces/restore',{business_id:w.business_id});},'Restored. Open it from the menu at the top.')}>Undo</button></li>)}</ul></>}
      <Notice m={msg.message}/>
    </Section>
  </>;
}
