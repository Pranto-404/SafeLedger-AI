"""Real remote-storage smoke for public accounts and separate approval. No AI calls."""
import json
import os
from pathlib import Path
import secrets
import sys
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from api.app.main import app
from api.app.database import connect
H={'Origin':'http://testserver','X-SafeLedger-Client':'web'}

def run():
    suffix=secrets.token_hex(6);password=secrets.token_urlsafe(24)
    with TestClient(app,headers=H) as c:
        r=c.post('/api/auth/guest',json={});assert r.status_code==201,r.text
        assert c.get('/api/workspace').json()['snapshot']['balance_minor']==12000000
        assert c.post('/api/proposals',json={'invoice_id':'INV-105'}).status_code==403
        c.post('/api/auth/logout',json={})
        r=c.post('/api/auth/signup',json={'username':'cloud_owner_'+suffix,'password':password});assert r.status_code==201,r.text
        business=r.json()['business_id']
        p=c.post('/api/proposals',json={'invoice_id':'INV-105'}).json()
        code=c.post('/api/account/invitations',json={'role':'approver'}).json()['code']
        assert c.post('/api/auth/signup',json={'username':'cloud_reviewer_'+suffix,'password':password}).status_code==201
        assert c.get('/api/proposals/'+p['proposal_id']).status_code==404
        assert c.post('/api/account/join',json={'code':code}).json()['role']=='approver'
        route='/api/proposals/'+p['proposal_id']+'/approve';body={'proposal_hash':p['action_hash'],'decision':'approve'}
        assert c.post(route,json=body).status_code==200
        assert c.post(route,json=body).status_code==200
        assert c.get('/api/workspace').json()['snapshot']['balance_minor']==8500000
        audit=c.get('/api/audit/'+p['proposal_id']).json();assert audit['chain_verified'] and sum(x['kind']=='EXECUTED' for x in audit['events'])==1
        assert c.post('/api/auth/login',json={'username':'cloud_owner_'+suffix,'password':password}).status_code==200
        assert c.get('/api/workspace').json()['snapshot']['balance_minor']==8500000
    with closing(connect()) as db:
        assert db.execute('SELECT count(*) FROM postings WHERE business_id=?',(business,)).fetchone()[0]==1
    return {'status':'passed','target':'local API with actual persistent Turso','guest_read_only':True,'signup_and_login':True,'workspace_isolation':True,'independent_invitation_approval':True,'posting_count':1,'balance_minor':8500000,'audit_verified':True,'separate_connection_persistence':True,'provider_calls':0,'simulation_only':True}
if __name__=='__main__':print(json.dumps(run(),indent=2))
