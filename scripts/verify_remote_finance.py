"""Actual persistent-cloud security/finance smoke; synthetic isolated tenant, no LLM."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
from api.app.main import app
from api.app.database import connect
from api.app import security as sec
from api.app.services.intake import parse_json
from api.app.services.storage import store_dataset


def run(base_url=None):
    business='cloud-qa-'+uuid.uuid4().hex
    tokens={}
    with closing(connect()) as db:
        sec.create_schema(db)
        ds=parse_json((Path(__file__).resolve().parents[1]/'data/fixtures/duplicate_exact.json').read_bytes())
        store_dataset(db,business,ds)
        with db:
            db.execute('INSERT INTO security_policies VALUES (?,?,?)',(business,1000000,10000000))
            db.executemany('INSERT INTO trusted_vendors VALUES (?,?,1)',[(business,v) for v in sorted({x.vendor_id for x in ds.invoices})])
        for role in ['owner','approver','viewer']:
            tokens[role]=sec.provision_session(db,business+'-'+role,business,role,ttl_seconds=3600)
        tokens['other']=sec.provision_session(db,business+'-other',business+'-other','owner',ttl_seconds=3600)
    if base_url and base_url!='https://safeledger-ai.vercel.app':raise ValueError('Only the authorized public target is supported')
    client=httpx.Client(base_url=base_url,timeout=30,follow_redirects=False) if base_url else TestClient(app)
    with client:
        def request(role,method,path,**kwargs):
            return client.request(method,path,headers={'Authorization':'Bearer '+tokens[role]},**kwargs)
        assert client.get('/api/ready').status_code==200
        assert client.get('/api/dashboard').status_code==401
        assert request('owner','GET','/api/dashboard').json()['balance_minor']==12000000
        assert request('owner','POST','/api/proposals',json={'invoice_id':'INV-104'}).status_code==409
        response=request('owner','POST','/api/proposals',json={'invoice_id':'INV-105'});assert response.status_code==201,response.text
        proposal=response.json();path='/api/proposals/'+proposal['proposal_id']
        assert request('other','GET',path).status_code==404
        body={'proposal_hash':proposal['action_hash'],'decision':'approve'}
        assert request('owner','POST',path+'/approve',json=body).status_code==403
        assert request('viewer','POST',path+'/approve',json=body).status_code==403
        assert request('approver','POST',path+'/approve',json={**body,'proposal_hash':'0'*64}).status_code==409
        assert request('owner','GET','/api/dashboard').json()['balance_minor']==12000000
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:request('approver','POST',path+'/approve',json=body),range(4)))
        assert all(x.status_code==200 for x in results),[x.status_code for x in results]
        assert request('approver','POST',path+'/approve',json=body).status_code==200
        assert request('viewer','GET','/api/dashboard').json()['balance_minor']==8500000
        audit=request('viewer','GET','/api/audit/'+proposal['proposal_id']).json()
        assert audit['chain_verified'] and sum(e['kind']=='EXECUTED' for e in audit['events'])==1
    with closing(connect()) as db:
        assert db.execute('SELECT count(*) FROM postings WHERE business_id=?',(business,)).fetchone()[0]==1
        assert db.execute('SELECT sum(delta_minor) FROM ledger_entries WHERE posting_id IN (SELECT posting_id FROM postings WHERE business_id=?)',(business,)).fetchone()[0]==0
    return {'status':'passed','target':base_url or 'local FastAPI with real remote Turso','business_id':business,'concurrent_approvals':4,'posting_count':1,'before_minor':12000000,'after_minor':8500000,'balanced_ledger':True,'audit_verified':True,'unauthorized_and_forged_denied':True,'separate_connection_persistence':True,'simulation_only':True,'live_ai_used':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url');args=p.parse_args()
    print(json.dumps(run(args.base_url),indent=2))
