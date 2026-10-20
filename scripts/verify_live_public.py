"""Finite live synthetic release checks on the authorized public Vercel target."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.request

BASE='https://capzoryx-copilot.vercel.app'
ROOT=Path(__file__).resolve().parents[1]
class Client:
 def __init__(self):
  self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
 def call(self,path,body=None,*,origin=BASE):
  headers={'Origin':origin,'X-SafeLedger-Client':'web'}
  if body is not None:headers['Content-Type']='application/json'
  request=urllib.request.Request(BASE+'/api/'+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
  try:r=self.opener.open(request,timeout=90)
  except urllib.error.HTTPError as e:r=e
  return r.status,json.loads(r.read()),r.headers


def run(include_ai=False):
 private=ROOT/'.private/release';private.mkdir(parents=True,exist_ok=True,mode=0o700)
 out=ROOT/'evidence/public-release';out.mkdir(parents=True,exist_ok=True)
 result={'target':BASE,'simulation_only':True,'checks':[],'ai':{'attempted':False}}
 def check(name,condition):
  if not condition:raise AssertionError(name)
  result['checks'].append(name);print('PASS',name,flush=True)
 c=Client();status,health,_=c.call('health');check('health',status==200);result['build_commit']=health['build_commit']
 status,ready,_=c.call('ready');check('persistent database',status==200 and ready['database']=='libsql')
 status,_,_=c.call('workspace');check('unauthenticated workspace denied',status==401)
 status,guest,_=c.call('auth/guest',{});check('guest session',status==201 and guest['guest'])
 status,workspace,_=c.call('workspace');check('guest overview',status==200 and workspace['snapshot']['balance_minor']==12000000)
 status,_,_=c.call('proposals',{'invoice_id':'INV-105'});check('guest cannot propose',status==403)
 c.call('auth/logout',{})
 suffix=secrets.token_hex(5);password=secrets.token_urlsafe(24);owner='release_owner_'+suffix;reviewer='release_reviewer_'+suffix
 status,session,headers=c.call('auth/signup',{'username':owner,'password':password});check('self-service owner account',status==201 and session['role']=='owner')
 cookie=headers.get('Set-Cookie','');check('secure HttpOnly cookie',all(x in cookie for x in ['HttpOnly','Secure','SameSite=lax']))
 status,session,_=c.call('account/workspaces',{'kind':'demo','name':'Release smoke demo'});check('explicit practice demo',status==201)
 account={'username':owner,'password':password,'business_id':session['business_id']}
 (private/'account.json').write_text(json.dumps(account));(private/'account.json').chmod(0o600)
 if include_ai:
  status,answer,_=c.call('agent/tasks',{'task':'What is my current available balance? Use verified source evidence only.','allow_proposal':False,'invoice_id':None})
  result['ai']={'attempted':True,'status_code':status,'ai_mode':answer.get('ai_mode'),'error_code':answer.get('error',{}).get('code')}
  if status==200:
   check('live assistant grounded balance',any(f.get('value_minor')==12000000 and f.get('source_ids') for f in answer.get('facts',[])) and answer.get('proposal') is None)
  else:print('AI unavailable:',result['ai']['error_code'],flush=True)
 status,p,_=c.call('proposals',{'invoice_id':'INV-105'});check('owner proposal',status==201)
 route='proposals/'+p['proposal_id']+'/approve';body={'proposal_hash':p['action_hash'],'decision':'approve'}
 status,_,_=c.call(route,body);check('self approval denied',status==403)
 status,invite,_=c.call('account/invitations',{'role':'approver'});check('one-time invitation created',status==201)
 other=Client();status,_,_=other.call('auth/signup',{'username':reviewer,'password':password});check('separate reviewer account',status==201)
 status,_,_=other.call('proposals/'+p['proposal_id']);check('cross-workspace access denied',status==404)
 status,joined,_=other.call('account/join',{'code':invite['code']});check('invited approver joins',status==200 and joined['role']=='approver')
 status,_,_=other.call(route,body);check('independent approval executes',status==200)
 status,_,_=other.call(route,body);check('approval replay idempotent',status==200)
 status,audit,_=other.call('audit/'+p['proposal_id']);check('one audited execution',status==200 and audit['chain_verified'] and sum(e['kind']=='EXECUTED' for e in audit['events'])==1)
 status,data,_=c.call('workspace');check('owner balance reconciled',status==200 and data['snapshot']['balance_minor']==8500000)
 status,_,_=c.call('account/invitations',{'role':'approver'},origin='https://untrusted.example');check('cookie CSRF denied',status==403)
 c.call('auth/logout',{});status,_,_=c.call('session');check('logout revokes session',status==401)
 status,_,_=c.call('auth/login',{'username':owner,'password':password});check('password login',status==200)
 c.call('account/switch',{'business_id':account['business_id']})
 status,data,_=c.call('workspace');check('login restores persisted ledger',status==200 and data['snapshot']['balance_minor']==8500000)
 account.update(proposal_id=p['proposal_id'],expected_balance_minor=8500000)
 (private/'account.json').write_text(json.dumps(account));(private/'account.json').chmod(0o600)
 result['status']='passed';result['posting_count']=1;result['balance_minor']=8500000
 (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
 return result


def after_redeploy():
 account=json.loads((ROOT/'.private/release/account.json').read_text());c=Client()
 status,_,_=c.call('auth/login',{'username':account['username'],'password':account['password']});assert status==200
 c.call('account/switch',{'business_id':account['business_id']})
 status,data,_=c.call('workspace');assert status==200 and data['snapshot']['balance_minor']==account['expected_balance_minor']
 status,audit,_=c.call('audit/'+account['proposal_id']);assert status==200 and audit['chain_verified'] and sum(e['kind']=='EXECUTED' for e in audit['events'])==1
 status,health,_=c.call('health');assert status==200
 result={'status':'passed','account_survived_redeploy':True,'balance_minor':data['snapshot']['balance_minor'],'posting_count':1,'audit_verified':True,'build_commit':health['build_commit'],'simulation_only':True}
 (ROOT/'evidence/public-release/persistence.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--ai',action='store_true');parser.add_argument('--after-redeploy',action='store_true');args=parser.parse_args()
 try:print(json.dumps(after_redeploy() if args.after_redeploy else run(args.ai),indent=2))
 except Exception as e:
  print(type(e).__name__,str(e),flush=True);raise SystemExit(1)
