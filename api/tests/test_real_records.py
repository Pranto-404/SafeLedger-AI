"""Real-record product boundaries: no shipped examples, explicit AI consent and recovery."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from api.tests.test_accounts import world, signup, PASSWORD
from api.tests.test_manual_inputs import record
from api.tests.test_agent import MockProvider
from api.app import accounts
from api.app.accounts import COOKIE
from api.app.agents import runner


def test_no_examples_fictional_endpoints_or_initial_provider(world,monkeypatch):
    c,path=world
    with sqlite3.connect(path) as db:assert db.execute('SELECT count(*) FROM financial_datasets').fetchone()[0]==0
    signup(c,'real_owner')
    monkeypatch.setattr(runner,'get_provider',lambda:(_ for _ in ()).throw(AssertionError('Unexpected model call')))
    for route in ['/api/session','/api/workspace','/api/workspace/export','/api/agent/status']:
        response=c.get(route);assert response.status_code==200,response.text
    data=c.get('/api/workspace').json();assert data['events']==data['invoices']==[] and data['snapshot']['balance_minor']==0
    assert 'financing' not in data and data['policy']['reserve_minor']==0
    assert c.post('/api/auth/guest',json={}).status_code==410
    assert c.post('/api/account/workspaces',json={'kind':'demo','name':'No'}).status_code==422
    assert c.post('/api/finance/compare',json={'principal_minor':5000000}).status_code==410
    assert c.post('/api/agent/tasks',json={'task':'Balance?'}).json()['error']['code']=='EXTERNAL_AI_CONSENT_REQUIRED'


def test_ai_consent_uses_only_entered_facts_and_no_execution(world,monkeypatch):
    c,_=world;signup(c,'facts_owner');assert record(c,amount_minor=1234567)[0].status_code==201
    provider=MockProvider();monkeypatch.setattr(runner,'get_provider',lambda:provider)
    assert c.post('/api/agent/tasks',json={'task':'Balance?','external_ai_consent':False}).status_code==403
    assert provider.count==0
    answer=c.post('/api/agent/tasks',json={'task':'Balance?','external_ai_consent':True})
    assert answer.status_code==200,answer.text
    assert answer.json()['facts'][0]['value_minor']==1234567 and answer.json()['proposal'] is None
    assert provider.count==2


def test_recovery_code_rotates_and_revokes_every_session(world):
    c,path=world
    first=signup(c,'recover_owner');code=first['recovery_code'];original_cookie=c.cookies.get(COOKIE)
    assert record(c,amount_minor=5500)[0].status_code==201
    assert 'recovery_code' not in c.get('/api/session').json()
    with sqlite3.connect(path) as db:
        stored=db.execute('SELECT code_hash FROM auth_recovery').fetchone()[0]
        assert stored==hashlib.sha256(code.encode()).hexdigest() and stored!=code
    assert c.post('/api/auth/recover',json={'username':'recover_owner','password':'Newpass8!','recovery_code':'x'*32}).status_code==401
    recovered=c.post('/api/auth/recover',json={'username':'recover_owner','password':'Newpass8!','recovery_code':code})
    assert recovered.status_code==200,recovered.text
    assert recovered.json()['recovery_code']!=code
    assert c.get('/api/session',headers={'Authorization':'Bearer '+original_cookie}).status_code==401
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==5500
    assert c.post('/api/auth/recover',json={'username':'recover_owner','password':'Otherpass8!','recovery_code':code}).status_code==401
    c.post('/api/auth/logout',json={})
    assert c.post('/api/auth/login',json={'username':'recover_owner','password':PASSWORD}).status_code==401
    assert c.post('/api/auth/login',json={'username':'recover_owner','password':'Newpass8!'}).status_code==200


def test_legacy_examples_are_archived_without_destroying_personal_data(world):
    c,path=world;identity=signup(c,'keep_records');assert record(c,amount_minor=998877)[0].status_code==201
    with sqlite3.connect(path) as db:
        db.execute("UPDATE workspace_meta SET kind='demo' WHERE business_id=?",(identity['business_id'],))
    assert c.get('/api/workspace').status_code==403
    logged=c.post('/api/auth/login',json={'username':'keep_records','password':PASSWORD})
    assert logged.status_code==200 and logged.json()['business_id']!=identity['business_id']
    assert c.get('/api/workspace').json()['snapshot']['balance_minor']==0
    spaces=c.get('/api/account/workspaces').json()['workspaces'];assert len(spaces)==1 and spaces[0]['kind']=='personal'
    assert c.post('/api/account/switch',json={'business_id':identity['business_id']}).status_code==403
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT payload FROM financial_datasets WHERE business_id=?',(identity['business_id'],)).fetchone()
        assert db.execute('SELECT count(*) FROM financial_datasets').fetchone()[0]==2


def test_export_contains_own_records_notes_and_no_authentication_secrets(world):
    c,path=world;identity=signup(c,'export_owner')
    note='<script>alert("untrusted text")</script>'
    response,_=record(c,amount_minor=20255,memo=note);assert response.status_code==201
    bundle=c.get('/api/workspace').json();assert bundle['events'][0]['note']==note
    exported=c.get('/api/workspace/export');assert exported.status_code==200
    body=exported.json();assert body['current_dataset']['events'][0]['amount_minor']==20255
    assert body['workspace_id']==identity['business_id'] and body['audit_events']
    for secret in [PASSWORD,identity['recovery_code'],c.cookies.get(COOKIE)]:assert secret not in exported.text
    assert all(key not in exported.text for key in ['password_hash','code_hash','token_hash'])


def test_application_import_does_not_load_ai_provider():
    result=subprocess.run([sys.executable,'-c',"import sys;from api.app.main import app;assert 'api.app.agents.runner' not in sys.modules;assert 'api.app.agents.provider' not in sys.modules;print('provider deferred')"],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
