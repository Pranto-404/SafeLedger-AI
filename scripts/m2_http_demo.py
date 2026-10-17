"""Live HTTP evidence: duplicate denial -> human approval -> concurrent retries -> audit.
Secrets stay in a temporary private directory; exported evidence contains synthetic data only.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import hashlib
import json
import os
import shlex
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('SAFELEDGER_EVIDENCE_DIR',str(ROOT/'evidence/m2')))
OUT.mkdir(parents=True,exist_ok=True)
steps=[]
with tempfile.TemporaryDirectory(prefix='safeledger-private-m2-') as temporary:
    private=Path(temporary)/'access'
    provision=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap_demo.py'),'--directory',str(private),'--fixture','duplicate_exact.json'],check=True,capture_output=True,text=True,cwd=ROOT)
    settings={}
    for line in (private/'demo.env').read_text().splitlines():
        name,value=shlex.split(line.removeprefix('export '))[0].split('=',1);settings[name]=value
    tokens=json.loads((private/'sessions.json').read_text())['bearer_tokens']
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env=dict(os.environ,**settings,SAFELEDGER_BUILD_COMMIT='M2-working-tree-see-verification-manifest')
    with (OUT/'live-server.log').open('w') as log:
        server=subprocess.Popen([sys.executable,'-m','uvicorn','api.app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=base,timeout=10,trust_env=False) as client:
                for _ in range(100):
                    if server.poll() is not None:raise RuntimeError('Local API exited; inspect live-server.log')
                    try:
                        if client.get('/api/ready').status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.05)
                else:raise RuntimeError('Local API not ready within five seconds')
                def call(role,method,path,expected=200,**kwargs):
                    response=client.request(method,path,headers={'Authorization':'Bearer '+tokens[role]},**kwargs)
                    steps.append({'role':role,'method':method,'path':path,'http_status':response.status_code,'expected_status':expected})
                    if response.status_code!=expected:raise RuntimeError(f'Unexpected HTTP status for {method} {path}: {response.status_code}')
                    return response.json()
                before=call('viewer','GET','/api/dashboard');assert before['balance_minor']==12000000
                denied=call('owner','POST','/api/proposals',409,json={'invoice_id':'INV-104'})
                assert denied['error']['code']=='DUPLICATE_INVOICE_BLOCKED'
                proposal=call('owner','POST','/api/proposals',201,json={'invoice_id':'INV-105'})
                path='/api/proposals/'+proposal['proposal_id']+'/approve'
                body={'proposal_hash':proposal['action_hash'],'decision':'approve'}
                assert call('viewer','POST',path,403,json=body)['error']['code']=='HUMAN_APPROVER_REQUIRED'
                assert call('approver','POST',path,409,json=dict(body,proposal_hash='0'*64))['error']['code']=='APPROVAL_HASH_MISMATCH'
                def approve(_):
                    response=httpx.post(base+path,headers={'Authorization':'Bearer '+tokens['approver']},json=body,timeout=15,trust_env=False)
                    if response.status_code!=200:raise RuntimeError('Concurrent HTTP approval failed: '+str(response.status_code))
                    return response.json()
                with ThreadPoolExecutor(max_workers=4) as pool:replies=list(pool.map(approve,range(4)))
                assert len({x['posting_id'] for x in replies})==1
                steps.append({'operation':'four_concurrent_human_approval_requests','http_statuses':[200]*4,'unique_postings':1})
                replay=call('approver','POST',path,json=body);assert replay['posting_id']==replies[0]['posting_id']
                after=call('viewer','GET','/api/dashboard');assert after['balance_minor']==8500000
                forecast=call('viewer','POST','/api/cashflow/scenarios',json={'as_of':after['as_of'],'horizon_days':30,'reserve_minor':1000000})
                assert forecast['closing_balance_minor']==-1875000
                # A real child-process restart retains DB, signatures, approval and idempotency.
                server.terminate();server.wait(timeout=10)
                server=subprocess.Popen([sys.executable,'-m','uvicorn','api.app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                with httpx.Client(base_url=base,timeout=10,trust_env=False) as restarted:
                    for _ in range(100):
                        if server.poll() is not None:raise RuntimeError('Restarted API exited')
                        try:
                            if restarted.get('/api/ready').status_code==200:break
                        except httpx.HTTPError:pass
                        time.sleep(.05)
                    else:raise RuntimeError('Restarted API not ready')
                    after_restart=restarted.post(path,headers={'Authorization':'Bearer '+tokens['approver']},json=body)
                    assert after_restart.status_code==200 and after_restart.json()['posting_id']==replay['posting_id']
                    steps.append({'operation':'real_api_process_restart_and_replay','http_status':200,'same_posting_id':True})
                    response=restarted.get('/api/audit',headers={'Authorization':'Bearer '+tokens['viewer']})
                    assert response.status_code==200
                    exported=response.json()
                previous='0'*64
                for event in exported['events']:
                    assert event['previous_hash']==previous
                    fields={k:v for k,v in event.items() if k not in {'event_id','event_hash'}}
                    previous=hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    assert previous==event['event_hash']
                assert previous==exported['tenant_chain_head']
                with closing(sqlite3.connect(settings['SAFELEDGER_DB'])) as db:
                    count=db.execute('SELECT count(*) FROM postings').fetchone()[0]
                    entries=db.execute('SELECT account,delta_minor FROM ledger_entries ORDER BY account').fetchall()
                    assert count==1 and entries==[('cash',-3500000),('payables',3500000)]
                evidence=dict(simulation_only=True,real_money_moved=False,llm_used=False,steps=steps,proposal=proposal,before=before,after=after,posting_id=replay['posting_id'],postings_count=count,ledger_entries=entries,forecast_30_closing_minor=forecast['closing_balance_minor'],audit=exported,offline_sha256_chain_verified=True)
                encoded=json.dumps(evidence,indent=2)+'\n'
                for secret in [settings['SAFELEDGER_SIGNING_KEY'],*tokens.values()]:
                    if secret in encoded:raise RuntimeError('Secret redaction check failed')
                (OUT/'http-execution-evidence.json').write_text(encoded)
                print('PASS: live HTTP, duplicate/viewer/tampered-hash denials, 4 concurrent approvals + retry, one posting, balanced ledger, cash12000000 ->8500000, forecast unchanged, actual process restart/replay, offline audit hashes verified. No real money or LLM used.')
        finally:
            server.terminate();server.wait(timeout=10)
