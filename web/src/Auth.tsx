import {Brand} from './Logo';
import {useEffect,useState,type FormEvent} from 'react';
import {accountRequest,AuthError} from './api';
import {CurrencySelect} from './Currency';
import {PasswordStrength} from './PasswordStrength';
import {initials} from './format';
import {Icon} from './Icon';
import {Landing,HeroDemo} from './Landing';
import {ThemeButton} from './Theme';
import type {Session} from './types';
import {t,LanguagePicker,T} from './i18n';

type Mode='signup'|'login'|'forgot';
type Forgot='choose'|'email'|'code'|'key'|'done';
type Caps={email_codes:boolean;cloud_assist:boolean};

const LAST_USER='capzoryx-last-user',KEEP='capzoryx-keep-signed-in';
const stored=(key:string)=>{try{return localStorage.getItem(key)||'';}catch{return '';}};
const store=(key:string,value:string)=>{try{if(value)localStorage.setItem(key,value);else localStorage.removeItem(key);}catch{/* private mode: the form still works */}};
const sleep=(ms:number)=>new Promise(resolve=>setTimeout(resolve,ms));
/** Ask the browser to offer saving the login (Chrome, Edge and Android). Never blocks or fails sign-in; the password is not kept anywhere by us. */
async function offerToSave(username:string,password:string){
  try{
    const Cred=(window as unknown as {PasswordCredential?:new(data:{id:string;password:string;name?:string})=>Credential}).PasswordCredential;
    if(Cred&&navigator.credentials&&typeof navigator.credentials.store==='function')await navigator.credentials.store(new Cred({id:username,password,name:username}));
  }catch{/* unsupported or declined */}
}
const waitText=(seconds:number)=>seconds<60?t('{n} seconds',{n:Math.max(1,Math.ceil(seconds))}):t('{n} minutes',{n:Math.ceil(seconds/60)});
function authMessage(e:unknown):string{
  if(!(e instanceof AuthError))return e instanceof Error?e.message:t('Could not connect. Please try again.');
  switch(e.code){
    case 'INVALID_USERNAME_OR_PASSWORD':return t('Check your username and password. Usernames are not case sensitive.');
    case 'TOO_MANY_FAILED_ATTEMPTS':return e.retryAfter?t('Too many unsuccessful attempts. For your protection, try again in {time}.',{time:waitText(e.retryAfter)}):t('Too many unsuccessful attempts. For your protection, wait a few minutes and try again.');
    case 'REQUEST_BUDGET_EXCEEDED':return t('Too many requests. Please wait a minute before trying again.');
    case 'CONNECTION_FAILED':return t('Could not reach the server. Check your connection and try again.');
    case 'SERVER_WAKING':return t('The server is waking up. Please try again in a moment.');
    case 'CHALLENGE_EXPIRED':return t('This sign-in step expired. Enter your password again.');
    case 'INVALID_CODE':return t('That code is not correct or has expired. Check it and try again.');
    default:return e.message;
  }
}

/** Sign up, sign in (with a two-step code when it is on) and every way back into an account. */
type Invite={workspace_name:string;role:string;invited_by:string};
export function Auth({onSession,joinCode,notice}:{onSession:(s:Session)=>void;joinCode:string;notice:string}){
  const joinPending=!!joinCode;
  const [mode,setMode]=useState<Mode>(()=>!joinCode&&stored(LAST_USER)?'login':'signup');
  const [username,setUsername]=useState(()=>stored(LAST_USER));const [keep,setKeep]=useState(()=>stored(KEEP)==='1');
  const [wait,setWait]=useState(0);const [slow,setSlow]=useState(false);const [waking,setWaking]=useState(false);const [capsSlow,setCapsSlow]=useState(false);const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [show,setShow]=useState(false);const [currency,setCurrency]=useState('BDT');
  const [challenge,setChallenge]=useState('');const [code,setCode]=useState('');
  const [forgot,setForgot]=useState<Forgot>('choose');const [resetCode,setResetCode]=useState('');const [second,setSecond]=useState('');const [needSecond,setNeedSecond]=useState(false);const [recoveryKey,setRecoveryKey]=useState('');
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [info,setInfo]=useState('');
  const [caps,setCaps]=useState<Caps>({email_codes:false,cloud_assist:false});
  useEffect(()=>{const c=new AbortController();const timer=window.setTimeout(()=>{if(!c.signal.aborted)setCapsSlow(true);},4000);void accountRequest<Caps>('/auth/capabilities',undefined,c.signal).then(setCaps).catch(()=>{}).finally(()=>{clearTimeout(timer);if(!c.signal.aborted)setCapsSlow(false);});return()=>{clearTimeout(timer);c.abort();};},[]);
  // Counts down a lockout or slow-down so the person sees exactly how long to wait.
  useEffect(()=>{if(wait<=0)return;const id=window.setInterval(()=>setWait(w=>Math.max(0,w-1)),1000);return()=>clearInterval(id);},[wait>0]);
  const [invite,setInvite]=useState<Invite|'bad'|null>(null);
  useEffect(()=>{if(!joinCode)return;const c=new AbortController();void accountRequest<Invite>('/invitations/preview',{code:joinCode},c.signal).then(setInvite).catch(e=>{if(!c.signal.aborted)setInvite('bad');});return()=>c.abort();},[joinCode]);
  const go=(m:Mode)=>{setMode(m);setError('');setInfo('');setChallenge('');setCode('');setForgot('choose');setWait(0);};
  async function run(task:()=>Promise<void>){
    if(busy)return;setBusy(true);setError('');setInfo('');
    const timer=window.setTimeout(()=>setSlow(true),3000);
    try{await task();}
    catch(e){
      if(e instanceof AuthError&&e.code==='TOO_MANY_FAILED_ATTEMPTS'&&e.retryAfter)setWait(e.retryAfter);else{setError(authMessage(e));if(e instanceof AuthError&&e.code==='REQUEST_BUDGET_EXCEEDED'&&e.retryAfter)setWait(e.retryAfter);}
      if(e instanceof AuthError){if(e.code==='CHALLENGE_EXPIRED'){setChallenge('');setCode('');}}
    }finally{clearTimeout(timer);setSlow(false);setWaking(false);setBusy(false);}
  }
  // Signing in is safe to repeat, so a server that is still waking up is retried instead of reported as a failure.
  async function loginRequest(body:{username:string;password:string;remember:boolean}){
    for(let attempt=0;;attempt++){
      try{return await accountRequest<Session>('/auth/login',body);}
      catch(e){if(attempt<3&&e instanceof AuthError&&(e.code==='CONNECTION_FAILED'||e.code==='SERVER_WAKING')){setWaking(true);await sleep(5000);continue;}throw e;}
    }
  }
  function remembered(name:string,pass:string){store(LAST_USER,name.toLowerCase());store(KEEP,keep?'1':'');void offerToSave(name,pass);}
  const submit=(e:FormEvent)=>{e.preventDefault();if(wait>0)return;void run(async()=>{
    const name=username.trim();
    if(mode==='signup'){const created=await accountRequest<Session>('/auth/signup',{username:name,password,currency,...(email.trim()?{email:email.trim()}:{})});remembered(name,password);onSession(created);setPassword('');return;}
    if(challenge){const done=await accountRequest<Session>('/auth/login/2fa',{challenge,code:code.trim(),remember:keep});remembered(name,password);onSession(done);setCode('');setChallenge('');setPassword('');return;}
    const r=await loginRequest({username:name,password,remember:keep});
    if(r.mfa_required&&r.challenge){setChallenge(r.challenge);setInfo(t('Enter the 6-digit code from your authenticator app, or one of your backup codes.'));return;}
    remembered(name,password);onSession(r);setPassword('');
  });};
  const requestCode=(e:FormEvent)=>{e.preventDefault();void run(async()=>{await accountRequest('/auth/reset/request',{email});setForgot('code');setInfo('If that email belongs to an account, a 6-digit code is on its way. It works for 10 minutes.');});};
  const confirmReset=(e:FormEvent)=>{e.preventDefault();void run(async()=>{
    try{await accountRequest('/auth/reset/confirm',{email,code:resetCode,new_password:password,...(second?{second_factor:second}:{})});}
    catch(err){if(err instanceof Error&&/two-factor/i.test(err.message))setNeedSecond(true);throw err;}
    setForgot('done');setPassword('');setResetCode('');setSecond('');setNeedSecond(false);setInfo('Your password was changed. Sign in with the new one.');});};
  const useKey=(e:FormEvent)=>{e.preventDefault();void run(async()=>{onSession(await accountRequest<Session>('/auth/recover',{username,password,recovery_code:recoveryKey}));setPassword('');setRecoveryKey('');});};
  const passwordField=(id:string,label:string,autoComplete:string)=><><label htmlFor={id}>{label}</label><div className="password-field"><input id={id} name={autoComplete==='current-password'?'password':'new-password'} type={show?'text':'password'} autoComplete={autoComplete} autoCapitalize="none" autoCorrect="off" spellCheck={false} minLength={8} maxLength={128} required value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/><button type="button" className="secondary" aria-label={show?t('Hide password'):t('Show password')} onClick={()=>setShow(!show)}>{show?t('Hide'):t('Show')}</button></div></>;
  // Gentle pointer parallax for the floating chips (large screens only, and only while the page is in view).
  useEffect(()=>{
    if(!matchMedia('(min-width: 1000px) and (prefers-reduced-motion: no-preference)').matches)return;
    let raf=0;const el=document.querySelector<HTMLElement>('main.welcome');
    const move=(e:PointerEvent)=>{if(raf)return;raf=requestAnimationFrame(()=>{raf=0;el?.style.setProperty('--px',String((e.clientX/innerWidth-.5)*2));el?.style.setProperty('--py',String((e.clientY/innerHeight-.5)*2));});};
    window.addEventListener('pointermove',move,{passive:true});return()=>{window.removeEventListener('pointermove',move);cancelAnimationFrame(raf);};
  },[]);
  const start=()=>{window.scrollTo({top:0,behavior:'smooth'});window.setTimeout(()=>document.getElementById(mode==='forgot'?'reset-email':'username')?.focus({preventScroll:true}),450);};
  return <><div className="aurora" aria-hidden="true"><i/><i/></div><main className="welcome">
    <section className="welcome-story"><Brand/><p className="eyebrow">{t('YOUR BUSINESS MONEY, MADE CLEAR')}</p><h1>{t('See the numbers.')}<br/><em>{t('Trust the decision.')}</em></h1><p className="welcome-copy">{t('Snap a bill, say what you paid, and see your cash flow, loans and payments in one place. Every payment needs a second person’s approval.')}</p><div className="welcome-benefits"><span><Icon name="check"/>{t('Photo and chat entry')}</span><span><Icon name="check"/>{t('Live currency rates')}</span><span><Icon name="check"/>{t('Safe approvals')}</span></div><HeroDemo/><div className="float-chips" aria-hidden="true"><span className="fc fc1"><Icon name="camera"/>{t('Bill scanned')}</span><span className="fc fc2"><Icon name="check"/>{t('Approved by a second person')}</span><span className="fc fc3"><Icon name="Cash flow"/>BDT 146,500</span></div><button type="button" className="scroll-cue" onClick={()=>document.getElementById('features')?.scrollIntoView({behavior:'smooth'})}>{t('See what it does')}<Icon name="arrow"/></button></section>
    <section className="welcome-entry"><div className="panel auth-card"><div className="auth-theme"><LanguagePicker compact id="language-auth"/><ThemeButton/></div>
      {mode!=='forgot'&&<>{joinPending&&invite&&invite!=='bad'&&<div className="invite-card" role="status"><span className="avatar avatar-initials" aria-hidden="true">{initials(invite.invited_by)}</span><div><strong>{t('{name} invited you',{name:invite.invited_by})}</strong><small>{t(invite.role==='approver'?T('to {workspace} · you will approve payments'):T('to {workspace} · you will view the records'),{workspace:invite.workspace_name})}</small></div></div>}{joinPending&&invite==='bad'&&<p className="notice" role="status">{t('This invitation has expired or was already used. Ask for a new link, or create your own workspace below.')}</p>}<h2>{joinPending&&invite&&invite!=='bad'?(mode==='signup'?t('Create your account to join'):t('Sign in to join')):mode==='signup'?t('Create your workspace'):t('Welcome back')}</h2><p className="muted">{joinPending?t('Sign in or create an account to accept your invitation.'):mode==='signup'?t('Free, and it takes a minute.'):t('Sign in to your workspace.')}</p>
        <div className="auth-tabs" role="group" aria-label={t('Account access')}><button className={mode==='signup'?'active':''} aria-pressed={mode==='signup'} onClick={()=>go('signup')} disabled={busy}>{t('Create account')}</button><button className={mode==='login'?'active':''} aria-pressed={mode==='login'} onClick={()=>go('login')} disabled={busy}>{t('Sign in')}</button></div>
        {notice&&<p className="notice" role="status">{notice}</p>}
        <form key={mode+(challenge?'-code':'')} id={mode==='signup'?'signup-form':'login-form'} name={mode==='signup'?'signup':'login'} method="post" action={mode==='signup'?'/api/auth/signup':'/api/auth/login'} onSubmit={submit}>
          {!challenge&&<><label htmlFor="username">{t('Username')}</label><input id="username" name="username" autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} maxLength={mode==='signup'?32:64} {...(mode==='signup'?{minLength:3,pattern:'[A-Za-z0-9_]{3,32}'}:{})} placeholder={t('letters, numbers, underscore')} required value={username} onChange={e=>setUsername(e.target.value)} disabled={busy}/>
            {mode==='signup'&&<><label htmlFor="signup-email">{t('Email')} <span className="muted">{t('(recommended, lets you reset your password)')}</span></label><input id="signup-email" type="email" autoComplete="email" maxLength={254} placeholder={t('you@example.com')} value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/></>}
            {passwordField('password',t('Password'),mode==='login'?'current-password':'new-password')}
            {mode==='login'&&<label className="check keep-signed-in" htmlFor="remember"><input id="remember" name="remember" type="checkbox" checked={keep} onChange={e=>setKeep(e.target.checked)} disabled={busy}/><span>{t('Keep me signed in')}<small>{t('Stay signed in on this device for 30 days. Use only on your own device.')}</small></span></label>}
            {mode==='signup'&&<><PasswordStrength password={password} username={username}/><label htmlFor="signup-currency">{t('Your business currency')}</label><CurrencySelect id="signup-currency" value={currency} onChange={setCurrency} disabled={busy}/><p className="small muted">{t('You can add more workspaces for other currencies later.')}</p></>}</>}
          {challenge&&<><label htmlFor="mfa-code">{t('Verification code')}</label><input id="mfa-code" name="code" autoComplete="one-time-code" inputMode="numeric" autoCapitalize="none" autoFocus required maxLength={12} value={code} onChange={e=>setCode(e.target.value)} disabled={busy}/></>}
          <div className={mode==='login'?'auth-status reserve':'auth-status'} aria-live="polite">{info&&<p className="notice" role="status">{info}</p>}{error&&<p role="alert" className="error">{error}</p>}{wait>0&&!error&&<p className="notice" role="status">{t('Too many unsuccessful attempts. For your protection, try again in {time}.',{time:waitText(wait)})}</p>}{!error&&!info&&(slow||waking||capsSlow)&&<p className="notice" role="status">{t('Opening your workspace… The free server may need up to a minute to wake up the first time.')}</p>}</div>
          <button className="full-width" disabled={busy||wait>0}>{busy?t('Please wait…'):wait>0?t('Try again in {time}',{time:waitText(wait)}):challenge?t('Verify and sign in'):mode==='signup'?t('Create my workspace'):t('Sign in')}</button>{challenge&&<button type="button" className="link recovery-link" disabled={busy} onClick={()=>go('login')}>{t('Use a different account')}</button>}</form>
        {mode==='login'&&!challenge&&<button type="button" className="link recovery-link" disabled={busy} onClick={()=>{setMode('forgot');setForgot(caps.email_codes?'choose':'key');setError('');setInfo('');}}>{t('Forgot your password?')}</button>}
</>}
      {mode==='forgot'&&<><h2>{t('Reset your password')}</h2>
        {forgot==='choose'&&<><p className="muted">{t('Choose how you want to get back in.')}</p><div className="actions"><button onClick={()=>setForgot('email')}>{t('Email me a code')}</button><button className="secondary" onClick={()=>setForgot('key')}>{t('Use my recovery key')}</button></div></>}
        {forgot==='email'&&<form onSubmit={requestCode}><label htmlFor="reset-email">{t('Your account email')}</label><input id="reset-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/>{error&&<p role="alert" className="error">{error}</p>}<button className="full-width" disabled={busy||!email}>{busy?t('Sending…'):t('Send my code')}</button></form>}
        {forgot==='code'&&<form onSubmit={confirmReset}>{info&&<p className="notice" role="status">{info}</p>}<label htmlFor="reset-code">{t('6-digit code')}</label><input id="reset-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required value={resetCode} onChange={e=>setResetCode(e.target.value.replace(/\D/g,''))} disabled={busy}/>
          {needSecond&&<><label htmlFor="reset-second">{t('Authenticator or backup code')}</label><input id="reset-second" required value={second} onChange={e=>setSecond(e.target.value)} disabled={busy}/></>}
          {passwordField('reset-password',t('New password'),'new-password')}<PasswordStrength password={password} username=""/>{error&&<p role="alert" className="error">{error}</p>}<button className="full-width" disabled={busy||resetCode.length!==6}>{busy?t('Please wait…'):t('Change my password')}</button>
          <button type="button" className="link" onClick={()=>{setForgot('email');setError('');}}>{t('Send a new code')}</button></form>}
        {forgot==='key'&&<form onSubmit={useKey}><p className="muted">{t('Enter the recovery key you saved when you created your account.')}</p><label htmlFor="rk-user">{t('Username')}</label><input id="rk-user" autoComplete="username" autoCapitalize="none" required value={username} onChange={e=>setUsername(e.target.value)} disabled={busy}/><label htmlFor="rk-code">{t('Recovery key')}</label><input id="rk-code" autoComplete="off" required minLength={20} maxLength={100} value={recoveryKey} onChange={e=>setRecoveryKey(e.target.value)} disabled={busy}/>{passwordField('rk-password',t('New password'),'new-password')}<PasswordStrength password={password} username={username}/>{error&&<p role="alert" className="error">{error}</p>}<button className="full-width" disabled={busy}>{busy?t('Please wait…'):t('Reset and sign in')}</button></form>}
        {forgot==='done'&&<><p className="success" role="status">{info}</p><button className="full-width" onClick={()=>go('login')}>{t('Go to sign in')}</button></>}
        {forgot!=='done'&&<button type="button" className="link recovery-link" disabled={busy} onClick={()=>go('login')}>{t('Back to sign in')}</button>}</>}
    </div><ul className="card-trust"><li><Icon name="check"/>{t('Free to start')}</li><li><Icon name="check"/>{t('No bank connection')}</li><li><Icon name="check"/>{t('Private by default')}</li></ul></section></main><Landing onStart={start}/></>;
}
