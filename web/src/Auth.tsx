import {Brand} from './Logo';
import {useEffect,useState,type FormEvent} from 'react';
import {accountRequest} from './api';
import {CurrencySelect} from './Currency';
import {PasswordStrength} from './PasswordStrength';
import {initials} from './format';
import {ThemeButton} from './Theme';
import type {Session} from './types';

type Mode='signup'|'login'|'forgot';
type Forgot='choose'|'email'|'code'|'key'|'done';
type Caps={email_codes:boolean;cloud_assist:boolean};

/** Sign up, sign in (with a two-step code when it is on) and every way back into an account. */
type Invite={workspace_name:string;role:string;invited_by:string};
export function Auth({onSession,joinCode,notice}:{onSession:(s:Session)=>void;joinCode:string;notice:string}){
  const joinPending=!!joinCode;
  const [mode,setMode]=useState<Mode>('signup');
  const [username,setUsername]=useState('');const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [show,setShow]=useState(false);const [currency,setCurrency]=useState('BDT');
  const [challenge,setChallenge]=useState('');const [code,setCode]=useState('');
  const [forgot,setForgot]=useState<Forgot>('choose');const [resetCode,setResetCode]=useState('');const [second,setSecond]=useState('');const [needSecond,setNeedSecond]=useState(false);const [recoveryKey,setRecoveryKey]=useState('');
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [info,setInfo]=useState('');
  const [caps,setCaps]=useState<Caps>({email_codes:false,cloud_assist:false});
  useEffect(()=>{const c=new AbortController();void accountRequest<Caps>('/auth/capabilities',undefined,c.signal).then(setCaps).catch(()=>{});return()=>c.abort();},[]);
  const [invite,setInvite]=useState<Invite|'bad'|null>(null);
  useEffect(()=>{if(!joinCode)return;const c=new AbortController();void accountRequest<Invite>('/invitations/preview',{code:joinCode},c.signal).then(setInvite).catch(e=>{if(!c.signal.aborted)setInvite('bad');});return()=>c.abort();},[joinCode]);
  const go=(m:Mode)=>{setMode(m);setError('');setInfo('');setChallenge('');setCode('');setForgot('choose');};
  async function run(task:()=>Promise<void>){if(busy)return;setBusy(true);setError('');setInfo('');try{await task();}catch(e){setError(e instanceof Error?e.message:'Could not connect. Please try again.');}finally{setBusy(false);}}
  const submit=(e:FormEvent)=>{e.preventDefault();void run(async()=>{
    if(mode==='signup'){onSession(await accountRequest<Session>('/auth/signup',{username,password,currency,...(email.trim()?{email:email.trim()}:{})}));setPassword('');return;}
    if(challenge){onSession(await accountRequest<Session>('/auth/login/2fa',{challenge,code}));setCode('');setChallenge('');setPassword('');return;}
    const r=await accountRequest<Session>('/auth/login',{username,password});
    if(r.mfa_required&&r.challenge){setChallenge(r.challenge);setInfo('Enter the 6-digit code from your authenticator app, or one of your backup codes.');return;}
    onSession(r);setPassword('');
  });};
  const requestCode=(e:FormEvent)=>{e.preventDefault();void run(async()=>{await accountRequest('/auth/reset/request',{email});setForgot('code');setInfo('If that email belongs to an account, a 6-digit code is on its way. It works for 10 minutes.');});};
  const confirmReset=(e:FormEvent)=>{e.preventDefault();void run(async()=>{
    try{await accountRequest('/auth/reset/confirm',{email,code:resetCode,new_password:password,...(second?{second_factor:second}:{})});}
    catch(err){if(err instanceof Error&&/two-factor/i.test(err.message))setNeedSecond(true);throw err;}
    setForgot('done');setPassword('');setResetCode('');setSecond('');setNeedSecond(false);setInfo('Your password was changed. Sign in with the new one.');});};
  const useKey=(e:FormEvent)=>{e.preventDefault();void run(async()=>{onSession(await accountRequest<Session>('/auth/recover',{username,password,recovery_code:recoveryKey}));setPassword('');setRecoveryKey('');});};
  const passwordField=(id:string,label:string,autoComplete:string)=><><label htmlFor={id}>{label}</label><div className="password-field"><input id={id} type={show?'text':'password'} autoComplete={autoComplete} minLength={8} maxLength={128} required value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/><button type="button" className="secondary" aria-label={show?'Hide password':'Show password'} onClick={()=>setShow(!show)}>{show?'Hide':'Show'}</button></div></>;
  return <main className="welcome">
    <section className="welcome-story"><Brand/><p className="eyebrow">YOUR BUSINESS MONEY, MADE CLEAR</p><h1>See the numbers.<br/><em>Trust the decision.</em></h1><p className="welcome-copy">Snap a bill, say what you paid, and see your cash flow, loans and payments in one place. Every payment needs a second person’s approval.</p><div className="welcome-benefits"><span>✓ Photo and chat entry</span><span>✓ Live currency rates</span><span>✓ Safe approvals</span></div></section>
    <section className="welcome-entry"><div className="panel auth-card"><div className="auth-theme"><ThemeButton/></div>
      {mode!=='forgot'&&<>{joinPending&&invite&&invite!=='bad'&&<div className="invite-card" role="status"><span className="avatar avatar-initials" aria-hidden="true">{initials(invite.invited_by)}</span><div><strong>{invite.invited_by} invited you</strong><small>to {invite.workspace_name} · you will {invite.role==='approver'?'approve payments':'view the records'}</small></div></div>}{joinPending&&invite==='bad'&&<p className="notice" role="status">This invitation has expired or was already used. Ask for a new link, or create your own workspace below.</p>}<h2>{joinPending&&invite&&invite!=='bad'?(mode==='signup'?'Create your account to join':'Sign in to join'):mode==='signup'?'Create your workspace':'Welcome back'}</h2><p className="muted">{joinPending?'Sign in or create an account to accept your invitation.':mode==='signup'?'Free, and it takes a minute.':'Sign in to your workspace.'}</p>
        <div className="auth-tabs" role="group" aria-label="Account access"><button className={mode==='signup'?'active':''} aria-pressed={mode==='signup'} onClick={()=>go('signup')} disabled={busy}>Create account</button><button className={mode==='login'?'active':''} aria-pressed={mode==='login'} onClick={()=>go('login')} disabled={busy}>Sign in</button></div>
        {notice&&<p className="notice" role="status">{notice}</p>}
        <form onSubmit={submit}>
          {!challenge&&<><label htmlFor="username">Username</label><input id="username" autoComplete="username" autoCapitalize="none" spellCheck={false} minLength={3} maxLength={32} pattern="[A-Za-z0-9_]{3,32}" placeholder="letters, numbers, underscore" required value={username} onChange={e=>setUsername(e.target.value)} disabled={busy}/>
            {mode==='signup'&&<><label htmlFor="signup-email">Email <span className="muted">(recommended, lets you reset your password)</span></label><input id="signup-email" type="email" autoComplete="email" maxLength={254} placeholder="you@example.com" value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/></>}
            {passwordField('password','Password',mode==='login'?'current-password':'new-password')}
            {mode==='signup'&&<><PasswordStrength password={password} username={username}/><label htmlFor="signup-currency">Your business currency</label><CurrencySelect id="signup-currency" value={currency} onChange={setCurrency} disabled={busy}/><p className="small muted">You can add more workspaces for other currencies later.</p></>}</>}
          {challenge&&<><label htmlFor="mfa-code">Verification code</label><input id="mfa-code" autoComplete="one-time-code" autoFocus required maxLength={12} value={code} onChange={e=>setCode(e.target.value)} disabled={busy}/></>}
          {info&&<p className="notice" role="status">{info}</p>}{error&&<p role="alert" className="error">{error}</p>}
          <button className="full-width" disabled={busy}>{busy?'Please wait…':challenge?'Verify and sign in':mode==='signup'?'Create my workspace':'Sign in'}</button></form>
        {mode==='login'&&!challenge&&<button type="button" className="link recovery-link" disabled={busy} onClick={()=>{setMode('forgot');setForgot(caps.email_codes?'choose':'key');setError('');setInfo('');}}>Forgot your password?</button>}
        {busy&&<p className="notice" role="status">Opening your workspace… The free server may need up to a minute to wake up the first time.</p>}</>}
      {mode==='forgot'&&<><h2>Reset your password</h2>
        {forgot==='choose'&&<><p className="muted">Choose how you want to get back in.</p><div className="actions"><button onClick={()=>setForgot('email')}>Email me a code</button><button className="secondary" onClick={()=>setForgot('key')}>Use my recovery key</button></div></>}
        {forgot==='email'&&<form onSubmit={requestCode}><label htmlFor="reset-email">Your account email</label><input id="reset-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/>{error&&<p role="alert" className="error">{error}</p>}<button className="full-width" disabled={busy||!email}>{busy?'Sending…':'Send my code'}</button></form>}
        {forgot==='code'&&<form onSubmit={confirmReset}>{info&&<p className="notice" role="status">{info}</p>}<label htmlFor="reset-code">6-digit code</label><input id="reset-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={resetCode} onChange={e=>setResetCode(e.target.value.replace(/\D/g,''))} disabled={busy}/>
          {needSecond&&<><label htmlFor="reset-second">Authenticator or backup code</label><input id="reset-second" required value={second} onChange={e=>setSecond(e.target.value)} disabled={busy}/></>}
          {passwordField('reset-password','New password','new-password')}<PasswordStrength password={password} username=""/>{error&&<p role="alert" className="error">{error}</p>}<button className="full-width" disabled={busy||resetCode.length!==6}>{busy?'Please wait…':'Change my password'}</button>
          <button type="button" className="link" onClick={()=>{setForgot('email');setError('');}}>Send a new code</button></form>}
        {forgot==='key'&&<form onSubmit={useKey}><p className="muted">Enter the recovery key you saved when you created your account.</p><label htmlFor="rk-user">Username</label><input id="rk-user" autoComplete="username" autoCapitalize="none" required value={username} onChange={e=>setUsername(e.target.value)} disabled={busy}/><label htmlFor="rk-code">Recovery key</label><input id="rk-code" autoComplete="off" required minLength={20} maxLength={100} value={recoveryKey} onChange={e=>setRecoveryKey(e.target.value)} disabled={busy}/>{passwordField('rk-password','New password','new-password')}<PasswordStrength password={password} username={username}/>{error&&<p role="alert" className="error">{error}</p>}<button className="full-width" disabled={busy}>{busy?'Please wait…':'Reset and sign in'}</button></form>}
        {forgot==='done'&&<><p className="success" role="status">{info}</p><button className="full-width" onClick={()=>go('login')}>Go to sign in</button></>}
        {forgot!=='done'&&<button type="button" className="link recovery-link" disabled={busy} onClick={()=>go('login')}>Back to sign in</button>}</>}
    </div></section></main>;
}
