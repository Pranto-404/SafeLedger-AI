import {LazyBoundary} from './LazyBoundary';
import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import {accountRequest} from './api';
import type {Session} from './types';
import {Auth} from './Auth';
const loadWorkspace=()=>import('./Workspace');
const Workspace=lazy(loadWorkspace);
const JOIN_KEY='safeledger-join-code';

function takeJoinCode():string{
  try{
    const url=new URL(window.location.href);const fromUrl=url.searchParams.get('join');
    if(fromUrl&&/^[A-Za-z0-9_-]{20,100}$/.test(fromUrl)){sessionStorage.setItem(JOIN_KEY,fromUrl);url.searchParams.delete('join');window.history.replaceState(null,'',url.pathname+(url.search||'')+url.hash);}
    return sessionStorage.getItem(JOIN_KEY)||'';
  }catch{return '';}
}

export default function App() {
  const [auth,setAuth]=useState<{session:Session}|null>(null);
  const [recoveryCode,setRecoveryCode]=useState('');
  const [error,setError]=useState('');const [notice,setNotice]=useState('');
  const [restoring,setRestoring]=useState(true);
  const [joinCode,setJoinCode]=useState(takeJoinCode);
  const restoreRequest=useRef<AbortController|null>(null);
  useEffect(()=>{const c=new AbortController();restoreRequest.current=c;void fetch('/api/session',{credentials:'same-origin',signal:AbortSignal.any([c.signal,AbortSignal.timeout(90000)])}).then(async r=>{if(r.ok){const session=await r.json() as Session;if(!c.signal.aborted&&!session.guest&&session.workspace_kind!=='demo')setAuth({session});}}).catch(()=>{}).finally(()=>{if(!c.signal.aborted)setRestoring(false);});return()=>c.abort();},[]);
  // An invitation link joins the shared workspace as soon as the person is signed in.
  useEffect(()=>{
    if(!auth||!joinCode)return;
    const code=joinCode;setJoinCode('');try{sessionStorage.removeItem(JOIN_KEY);}catch{/* optional */}
    void accountRequest<Session>('/account/join',{code}).then(session=>{setAuth({session});setNotice(`You joined ${session.workspace_name||'the workspace'} as ${session.role}.`);}).catch(e=>setError(e instanceof Error?e.message:'The invitation could not be used.'));
  },[auth,joinCode]);
  function enter(session:Session){restoreRequest.current?.abort();setRestoring(false);void loadWorkspace();setRecoveryCode(session.recovery_code||'');setError('');setAuth({session:{...session,recovery_code:undefined}});}
  async function signout(){try{await accountRequest('/auth/logout',{});}catch{setError('Could not sign out. Please retry.');return;}try{Object.keys(sessionStorage).filter(k=>k.startsWith('safeledger-financing-quotes-v1:')).forEach(k=>sessionStorage.removeItem(k));}catch{/* Storage may be unavailable. */}setAuth(null);setError('');setNotice('');setRecoveryCode('');}
  function expired(){setAuth(null);setError('Your session ended. Sign in again to continue.');}
  if(restoring&&!auth)return <main className="workspace-loading" role="status"><span className="loading-ring"/>Opening SafeLedger…</main>;
  return <>
    {auth&&error&&<p className="error banner" role="alert">{error} <button className="link" onClick={()=>setError('')}>Dismiss</button></p>}
    {auth&&notice&&<p className="success banner" role="status">{notice} <button className="link" onClick={()=>setNotice('')}>Dismiss</button></p>}
    {auth&&recoveryCode&&<RecoveryNotice code={recoveryCode} done={()=>setRecoveryCode('')}/>}
    {auth?<LazyBoundary><Suspense fallback={<main className="workspace-loading" role="status"><span className="loading-ring"/>Opening your workspace…</main>}><Workspace key={auth.session.business_id+auth.session.user_id} token="" session={auth.session} logout={()=>void signout()} expired={expired} changeSession={session=>setAuth({session})}/></Suspense></LazyBoundary>
      :<Auth onSession={enter} joinPending={!!joinCode} notice={error||''}/>}
  </>;
}

function RecoveryNotice({code,done}:{code:string;done:()=>void}) {
 const [copied,setCopied]=useState(false);
 return <section className="recovery-notice panel" role="region" aria-label="Save your backup recovery key"><span className="badge">SHOWN ONCE · KEEP PRIVATE</span><h2>Save your backup recovery key</h2><p>If you ever lose your password and cannot get an email code, this key gets you back in. Keep it somewhere safe, such as a password manager.</p><label htmlFor="new-recovery-code">Recovery key</label><input id="new-recovery-code" value={code} readOnly autoComplete="off"/><div className="actions"><button className="secondary" onClick={()=>void navigator.clipboard.writeText(code).then(()=>setCopied(true)).catch(()=>setCopied(false))}>{copied?'Copied':'Copy key'}</button><button onClick={done}>I saved it</button></div></section>;
}
