import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest
from api.app.main import app
from api.app import security as sec
from api.app.accounts import COOKIE, TEMPLATE

HEADERS={'Origin':'http://testserver','X-SafeLedger-Client':'web'}
PASSWORD='A long unique demo passphrase 2026!'

@pytest.fixture
def world(tmp_path,monkeypatch):
    monkeypatch.setenv('SAFELEDGER_DB',str(tmp_path/'accounts.sqlite3'))
    monkeypatch.setenv('SAFELEDGER_SIGNING_KEY','b'*64)
    monkeypatch.delenv('RENDER',raising=False);monkeypatch.delenv('VERCEL',raising=False)
    monkeypatch.delenv('TURSO_DATABASE_URL',raising=False);monkeypatch.delenv('TURSO_AUTH_TOKEN',raising=False)
    with TestClient(app,headers=HEADERS) as client:yield client,tmp_path/'accounts.sqlite3'


def signup(c,name):
    r=c.post('/api/auth/signup',json={'username':name,'password':PASSWORD})
    assert r.status_code==201,r.text
    return r.json()


def test_signup_cookie_restore_logout_hashing_and_isolation(world):
    c,path=world
    first=signup(c,'first_person')
    assert first['role']=='owner' and first['username']=='first_person' and not first['guest']
    cookie=c.cookies.get(COOKIE)
    assert 'HttpOnly' in c.get('/api/session').request.headers.get('Cookie','') or cookie
    assert c.get('/api/session').json()['business_id']==first['business_id']
    data=c.get('/api/workspace').json();assert data['snapshot']['balance_minor']==0
    with sqlite3.connect(path) as db:
        hashed=db.execute('SELECT password_hash FROM auth_accounts').fetchone()[0]
        assert hashed.startswith('scrypt-v1$') and PASSWORD not in hashed
    assert c.post('/api/auth/logout',json={}).status_code==200
    assert c.get('/api/session').status_code==401
    assert c.get('/api/session',headers={'Authorization':'Bearer '+cookie}).status_code==401
    second=signup(c,'second_person');assert second['business_id']!=first['business_id']
    assert c.post('/api/account/switch',json={'business_id':first['business_id']}).status_code==403
    assert c.post('/api/auth/login',json={'username':'first_person','password':PASSWORD}).json()['business_id']==first['business_id']


def test_csrf_origin_and_overposting_rejected(world):
    c,_=world
    for headers in [{'Origin':'https://evil.test','X-SafeLedger-Client':'web'},{'Origin':'http://testserver','X-SafeLedger-Client':'other'}]:
        assert c.post('/api/auth/signup',json={'username':'test_person','password':PASSWORD},headers=headers).status_code==403
    assert c.post('/api/auth/signup',json={'username':'test_person','password':PASSWORD,'role':'approver'}).status_code==422
    signup(c,'test_person')
    assert c.post('/api/proposals',json={'invoice_id':'INV-105'},headers={'Origin':'https://evil.test'}).status_code==403
    assert c.post('/api/account/invitations',json={'role':'owner'}).status_code==422


def test_guest_read_only_financial_exploration_and_no_ai(world):
    c,_=world
    r=c.post('/api/auth/guest',json={});assert r.status_code==201 and r.json()['guest']
    data=c.get('/api/workspace');assert data.status_code==200 and data.json()['snapshot']['balance_minor']==12000000
    assert c.post('/api/proposals',json={'invoice_id':'INV-105'}).status_code==403
    assert c.post('/api/account/invitations',json={'role':'approver'}).status_code==403
    assert c.post('/api/agent/tasks',json={'task':'What is my balance?','allow_proposal':False}).status_code==403
    assert c.get('/api/audit').json()['events']==[]
    assert c.get('/api/workspace').status_code==200


def test_separate_registered_approver_single_posting_and_invite_replay(world):
    c,path=world
    signup(c,'owner_person')
    owner=c.post('/api/account/workspaces',json={'kind':'demo','name':'Practice demo'}).json();owner_cookie=c.cookies.get(COOKIE)
    proposal=c.post('/api/proposals',json={'invoice_id':'INV-105'});assert proposal.status_code==201
    p=proposal.json();body={'proposal_hash':p['action_hash'],'decision':'approve'}
    route='/api/proposals/'+p['proposal_id']+'/approve'
    assert c.post(route,json=body).status_code==403
    code=c.post('/api/account/invitations',json={'role':'approver'}).json()['code']
    signup(c,'approver_person')
    assert c.get('/api/proposals/'+p['proposal_id']).status_code==404
    joined=c.post('/api/account/join',json={'code':code});assert joined.status_code==200
    assert joined.json()['role']=='approver' and joined.json()['business_id']==owner['business_id']
    approver_cookie=c.cookies.get(COOKIE)
    def decide(_):
        with TestClient(app,headers={**HEADERS,'Cookie':COOKIE+'='+approver_cookie}) as other:
            return other.post(route,json=body).status_code
    with ThreadPoolExecutor(max_workers=4) as pool:assert list(pool.map(decide,range(4)))==[200]*4
    audit=c.get('/api/audit/'+p['proposal_id']).json();assert audit['chain_verified'] and sum(x['kind']=='EXECUTED' for x in audit['events'])==1
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==8500000
    signup(c,'third_person')
    assert c.post('/api/account/join',json={'code':code}).status_code==409
    assert c.post('/api/auth/login',json={'username':'owner_person','password':PASSWORD}).status_code==200
    assert c.post('/api/account/switch',json={'business_id':owner['business_id']}).status_code==200
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==8500000
    c.cookies.clear();c.cookies.set(COOKIE,owner_cookie)
    assert c.get('/api/session').json()['role']=='owner'


def test_cookie_flags_expiry_and_wrong_password(world,monkeypatch):
    c,path=world
    r=c.post('/api/auth/signup',json={'username':'cookie_person','password':PASSWORD})
    header=r.headers['set-cookie'];assert 'HttpOnly' in header and 'SameSite=lax' in header and 'Max-Age=86400' in header
    assert c.post('/api/auth/login',json={'username':'cookie_person','password':'wrong but sufficiently long password'}).status_code==401
    assert c.post('/api/auth/login',json={'username':'unknown_person','password':PASSWORD}).status_code==401
    with sqlite3.connect(path) as db:db.execute('UPDATE security_sessions SET expires_at=0')
    assert c.get('/api/session').status_code==401
    monkeypatch.setenv('SAFELEDGER_COOKIE_SECURE','1')
    r=c.post('/api/auth/login',json={'username':'cookie_person','password':PASSWORD})
    assert 'Secure' in r.headers['set-cookie']


def test_signup_rollback_and_username_case(world):
    c,path=world
    signup(c,'Case_User')
    r=c.post('/api/auth/signup',json={'username':'case_user','password':PASSWORD});assert r.status_code==409
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM auth_accounts').fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM financial_datasets WHERE business_id!=?",(TEMPLATE,)).fetchone()[0]==1
