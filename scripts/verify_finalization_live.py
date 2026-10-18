"""Finite public synthetic acceptance. Credentials stay in ignored .private only."""
import argparse
import json
from pathlib import Path
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from verify_live_public import Client
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/finalization';PRIVATE=ROOT/'.private/finalization'

def run(ai=False):
    checks=[];timings={}
    def check(name,value):
        if not value:raise AssertionError(name)
        checks.append(name);print('PASS',name,flush=True)
    c=Client();status,health,_=c.call('health');check('deployed health',status==200)
    status,ready,_=c.call('ready');check('persistent database',status==200 and ready['database']=='libsql')
    # Explicitly preserve the previously released synthetic ledger/account.
    old=json.loads((ROOT/'.private/release/account.json').read_text())
    status,_,_=c.call('auth/login',{'username':old['username'],'password':old['password']});check('existing account preserved',status==200)
    status,data,_=c.call('workspace');check('existing ledger and audit preserved',status==200 and data['snapshot']['balance_minor']==old['expected_balance_minor'] and data['audit']['chain_verified'])
    c.call('auth/logout',{})
    suffix=secrets.token_hex(4);password='A7!'+secrets.token_hex(3)[:5];name='final_owner_'+suffix
    status,session,headers=c.call('auth/signup',{'username':name,'password':password});check('8-character signup',status==201 and session['workspace_kind']=='personal')
    check('secure cookie',all(x in headers.get('Set-Cookie','') for x in ['HttpOnly','Secure','SameSite=lax']))
    personal=session['business_id'];status,data,_=c.call('workspace');check('zero initial account with no fake invoices',status==200 and data['snapshot']['balance_minor']==0 and not data['invoices'])
    account={'username':name,'password':password,'business_id':personal};PRIVATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    (PRIVATE/'account.json').write_text(json.dumps(account));(PRIVATE/'account.json').chmod(0o600)
    today=datetime.now(timezone(timedelta(hours=6))).date().isoformat()
    body={'request_id':str(uuid.uuid4()),'expected_revision':data['dataset_revision'],'kind':'cash','amount_minor':10000025,'effective_on':today}
    status,_,_=c.call('workspace/records',body);check('own exact-cent cash input',status==201)
    status,replay,_=c.call('workspace/records',body);check('input retry idempotent',status==201 and replay['replayed'])
    status,_,_=c.call('workspace/records',{**body,'amount_minor':5});check('request payload reuse rejected',status==409)
    status,data,_=c.call('workspace');check('exact cash balance',status==200 and data['snapshot']['balance_minor']==10000025)
    inv={'request_id':str(uuid.uuid4()),'expected_revision':data['dataset_revision'],'kind':'invoice','amount_minor':2500025,'effective_on':today,'due_on':today,'vendor_id':'test_supplier','invoice_number':'FINAL-01','trust_vendor':True,'memo':'Synthetic verification only'}
    status,record,_=c.call('workspace/records',inv);check('manual supplier invoice',status==201)
    status,data,_=c.call('workspace');check('unpaid invoice not deducted from cleared cash',status==200 and data['snapshot']['balance_minor']==10000025 and data['month']['closing_balance_minor']==7500000)
    status,p,_=c.call('proposals',{'invoice_id':record['source_id']});check('manual invoice proposal',status==201)
    route='proposals/'+p['proposal_id']+'/approve';decision={'proposal_hash':p['action_hash'],'decision':'approve'}
    status,_,_=c.call(route,decision);check('self approval denied',status==403)
    status,invite,_=c.call('account/invitations',{'role':'approver'});check('separate approver invitation',status==201)
    other=Client();status,_,_=other.call('auth/signup',{'username':'final_reviewer_'+suffix,'password':password});check('separate account',status==201)
    status,_,_=other.call('proposals/'+p['proposal_id']);check('tenant leakage denied',status==404)
    status,_,_=other.call('account/join',{'code':invite['code']});check('invited join',status==200)
    status,_,_=other.call(route,decision);check('independent approval executes',status==200)
    status,_,_=other.call(route,decision);check('execution retry one posting',status==200)
    status,data,_=c.call('workspace');check('balance 75000 after exact-cent payment',status==200 and data['snapshot']['balance_minor']==7500000)
    status,_,_=c.call('workspace/records',{'request_id':str(uuid.uuid4()),'expected_revision':data['dataset_revision'],'kind':'cash','amount_minor':1000000,'effective_on':today});check('new input after signed posting',status==201)
    status,data,_=c.call('workspace');check('historical proof and balance remain valid',status==200 and data['snapshot']['balance_minor']==8500000 and data['audit']['chain_verified'])
    status,audit,_=c.call('audit/'+p['proposal_id']);check('exactly one audited execution',status==200 and sum(x['kind']=='EXECUTED' for x in audit['events'])==1)
    status,_,_=c.call('workspace/records',body,origin='https://evil.example');check('input CSRF denied',status==403)
    status,demo,_=c.call('account/workspaces',{'kind':'demo','name':'Acceptance practice'});check('optional separate demo',status==201 and demo['business_id']!=personal)
    status,data,_=c.call('workspace');check('sample balance only in demo',status==200 and data['snapshot']['balance_minor']==12000000)
    status,_,_=c.call('account/switch',{'business_id':personal});check('switch to own inputs',status==200)
    status,data,_=c.call('workspace');check('personal data unchanged by demo',status==200 and data['snapshot']['balance_minor']==8500000)
    ai_result={'attempted':False}
    if ai:
        status,answer,_=c.call('agent/tasks',{'task':'What is my current available balance? Use verified evidence only.','allow_proposal':False,'invoice_id':None})
        ai_result={'attempted':True,'status_code':status,'mode':answer.get('ai_mode'),'error_code':answer.get('error',{}).get('code')}
        if status==200:check('live AI grounded in manual data',any(f['value_minor']==8500000 and f['source_ids'] for f in answer.get('facts',[])) and answer.get('proposal') is None)
    c.call('auth/logout',{});status,_,_=c.call('session');check('logout revoked',status==401)
    status,_,_=c.call('auth/login',{'username':name,'password':password});check('8-character password login',status==200)
    status,data,_=c.call('workspace');check('own records restored on login',status==200 and data['snapshot']['balance_minor']==8500000)
    account.update(proposal_id=p['proposal_id'],expected_balance_minor=8500000)
    (PRIVATE/'account.json').write_text(json.dumps(account));(PRIVATE/'account.json').chmod(0o600)
    result={'status':'passed','build_commit':health['build_commit'],'checks':checks,'ai':ai_result,'simulation_only':True}
    (OUT/'live.json').write_text(json.dumps(result,indent=2)+'\n');return result
def after_redeploy():
    account=json.loads((PRIVATE/'account.json').read_text());c=Client()
    status,_,_=c.call('auth/login',{'username':account['username'],'password':account['password']});assert status==200
    status,data,_=c.call('workspace');assert status==200 and data['snapshot']['balance_minor']==account['expected_balance_minor'] and data['audit']['chain_verified']
    status,audit,_=c.call('audit/'+account['proposal_id']);assert status==200 and sum(e['kind']=='EXECUTED' for e in audit['events'])==1
    status,health,_=c.call('health');assert status==200
    result={'status':'passed','account_and_manual_inputs_survived_redeploy':True,'balance_minor':data['snapshot']['balance_minor'],'audited_posting_count':1,'audit_verified':True,'build_commit':health['build_commit'],'simulation_only':True}
    (OUT/'persistence.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--ai',action='store_true');parser.add_argument('--after-redeploy',action='store_true');args=parser.parse_args()
    print(json.dumps(after_redeploy() if args.after_redeploy else run(args.ai),indent=2))
