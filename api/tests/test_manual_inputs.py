"""Adversarial tests of user-owned data and historical signed financial state."""
import json
import sqlite3
import uuid
from datetime import timedelta
from api.tests.test_accounts import world, signup, HEADERS, PASSWORD
from api.app.accounts import today_bd, COOKIE
from api.app import security as sec


def record(c,**changes):
    body=dict(request_id=str(uuid.uuid4()),expected_revision=c.get('/api/workspace').json()['dataset_revision'],kind='cash',amount_minor=10000000,effective_on=today_bd().isoformat(),direction='inflow',status='cleared')
    body.update(changes)
    return c.post('/api/workspace/records',json=body),body


def test_empty_account_eight_chars_and_exact_whitespace_password(world):
    c,_=world
    assert c.post('/api/auth/signup',json={'username':'short_user','password':'abcdefg'}).status_code==422
    assert c.post('/api/auth/signup',json={'username':'new_user','password':' abcd123 '}).status_code==201
    b=c.get('/api/workspace').json();assert b['snapshot']['balance_minor']==0 and b['invoices']==[]
    c.post('/api/auth/logout',json={})
    assert c.post('/api/auth/login',json={'username':'new_user','password':'abcd123 '}).status_code==401
    assert c.post('/api/auth/login',json={'username':'new_user','password':' abcd123 '}).status_code==200


def test_demo_opt_in_and_personal_isolation(world):
    c,_=world;personal=signup(c,'personal_user')
    demo=c.post('/api/account/workspaces',json={'kind':'demo','name':'My practice'});assert demo.status_code==201
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==12000000
    assert demo.json()['business_id']!=personal['business_id']
    c.post('/api/account/switch',json={'business_id':personal['business_id']})
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==0
    assert len(c.get('/api/account/workspaces').json()['workspaces'])==2


def test_exact_cash_scheduled_and_idempotency(world):
    c,_=world;signup(c,'cash_user')
    r,body=record(c,amount_minor=12345);assert r.status_code==201,r.text
    assert c.post('/api/workspace/records',json=body).json()['replayed']
    assert c.post('/api/workspace/records',json={**body,'amount_minor':12346}).status_code==409
    assert record(c,expected_revision=body['expected_revision'])[0].status_code==409
    r,_=record(c,amount_minor=2345,direction='outflow');assert r.status_code==201
    future=(today_bd()+timedelta(days=2)).isoformat()
    assert record(c,amount_minor=5000,status='scheduled',effective_on=future)[0].status_code==201
    b=c.get('/api/workspace').json();assert b['snapshot']['balance_minor']==10000 and b['month']['closing_balance_minor']==15000
    assert b['audit']['chain_verified'] and sum(e['kind']=='RECORD_ADDED' for e in b['audit']['events'])==3


def test_strict_validation_and_no_partial_write(world):
    c,_=world;signup(c,'validation_user')
    initial=c.get('/api/workspace').json()['dataset_revision']
    for value in [0,-1,True,1.5,'100',10**12+1]:assert record(c,amount_minor=value)[0].status_code==422
    assert record(c,effective_on=(today_bd()+timedelta(days=1)).isoformat())[0].status_code==422
    assert record(c,vendor_id='other')[0].status_code==422
    assert record(c,kind='invoice',vendor_id='supplier',invoice_number='ABC',due_on='2000-01-01')[0].status_code==422
    b=c.get('/api/workspace').json();assert b['dataset_revision']==initial and b['snapshot']['balance_minor']==0


def test_prior_approval_and_posting_survive_new_evidence(world):
    c,path=world;owner=signup(c,'finance_owner');owner_cookie=c.cookies.get(COOKIE)
    assert record(c)[0].status_code==201
    r,body=record(c,kind='invoice',vendor_id='supplier',invoice_number='BILL-101',due_on=today_bd().isoformat(),amount_minor=2500000,trust_vendor=True)
    assert r.status_code==201,r.text
    invoice=r.json()['source_id']
    p=c.post('/api/proposals',json={'invoice_id':invoice});assert p.status_code==201,p.text
    p=p.json();assert record(c,amount_minor=1000000)[0].status_code==201
    code=c.post('/api/account/invitations',json={'role':'approver'}).json()['code']
    signup(c,'finance_reviewer');assert c.post('/api/account/join',json={'code':code}).status_code==200
    route='/api/proposals/'+p['proposal_id']+'/approve';decision={'proposal_hash':p['action_hash'],'decision':'approve'}
    assert c.post('/api/workspace/records',json=body).status_code==403
    result=c.post(route,json=decision);assert result.status_code==200,result.text
    assert result.json()['balance_minor']==8500000
    c.cookies.clear();c.cookies.set(COOKIE,owner_cookie)
    assert record(c,amount_minor=1500000)[0].status_code==201
    b=c.get('/api/workspace');assert b.status_code==200,b.text
    assert b.json()['snapshot']['balance_minor']==10000000 and b.json()['audit']['chain_verified']
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM postings').fetchone()[0]==1
        assert db.execute('SELECT sum(delta_minor) FROM ledger_entries').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM dataset_versions').fetchone()[0]==4
    assert c.get('/api/proposals/'+p['proposal_id']).status_code==200


def test_guest_csrf_tenant_no_trust_and_import_overwrite(world):
    c,_=world;c.post('/api/auth/guest',json={})
    assert record(c)[0].status_code==403
    assert c.post('/api/account/workspaces',json={'kind':'demo','name':'No'}).status_code==403
    personal=signup(c,'input_owner')
    b=c.get('/api/workspace').json();r,body=record(c,amount_minor=123)
    assert c.post('/api/workspace/records',json={**body,'request_id':str(uuid.uuid4())},headers={'Origin':'https://evil.test'}).status_code==403
    signup(c,'other_owner')
    assert c.post('/api/workspace/records',json=body).status_code==201  # Same blank revision authorizes only this user's own input.
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==123
    assert c.post('/api/account/switch',json={'business_id':personal['business_id']}).status_code==403
    r,_=record(c,kind='invoice',vendor_id='supplier',invoice_number='TEST',due_on=today_bd().isoformat(),amount_minor=100)
    assert r.status_code==201
    assert c.post('/api/proposals',json={'invoice_id':r.json()['source_id']}).json()['error']['code']=='PAYEE_NOT_ALLOWLISTED'
    from pathlib import Path
    fixture=json.loads(Path('data/fixtures/base.json').read_text()) if Path('data/fixtures/base.json').exists() else json.loads(Path('data/fixtures/duplicate_exact.json').read_text())
    assert c.post('/api/workspace/import',json=fixture).status_code==409


def test_import_is_atomic_and_vendor_permission_explicit(world):
    from pathlib import Path
    c,_=world;signup(c,'import_user')
    fixture=json.loads(Path('data/fixtures/duplicate_exact.json').read_text())
    r=c.post('/api/workspace/import',json=fixture);assert r.status_code==201,r.text
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==12000000
    assert c.post('/api/proposals',json={'invoice_id':'INV-105'}).json()['error']['code']=='PAYEE_NOT_ALLOWLISTED'
    vendor=next(i['vendor_id'] for i in fixture['invoices'] if i['invoice_id']=='INV-105')
    assert c.post('/api/workspace/vendor-permission',json={'vendor_id':vendor,'enabled':True}).status_code==200
    assert c.post('/api/proposals',json={'invoice_id':'INV-105'}).status_code==201
    assert c.post('/api/workspace/import',json=fixture).status_code==409
    assert c.post('/api/workspace/vendor-permission',json={'vendor_id':vendor,'enabled':False}).status_code==200
    assert c.get('/api/audit').json()['chain_verified']


def test_concurrent_input_replay_single_record(world):
    from concurrent.futures import ThreadPoolExecutor
    from fastapi.testclient import TestClient
    from api.app.main import app
    c,path=world;signup(c,'concurrent_user');token=c.cookies.get(COOKIE)
    body=dict(request_id=str(uuid.uuid4()),expected_revision=c.get('/api/workspace').json()['dataset_revision'],kind='cash',amount_minor=10001,effective_on=today_bd().isoformat())
    def save(_):
        with TestClient(app,headers={**HEADERS,'Cookie':COOKIE+'='+token}) as other:return other.post('/api/workspace/records',json=body).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(save,range(4)))==[201]*4
    b=c.get('/api/workspace').json();assert b['snapshot']['balance_minor']==10001
    assert sum(e['kind']=='RECORD_ADDED' for e in b['audit']['events'])==1
    with sqlite3.connect(path) as db:assert db.execute('SELECT count(*) FROM workspace_input_requests').fetchone()[0]==1
