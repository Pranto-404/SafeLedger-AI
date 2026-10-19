"""Bounded attacks on disposable local workspaces. Never production penetration traffic."""
import json
import sqlite3
import pytest
from api.tests.test_accounts import world,signup,HEADERS,PASSWORD
from api.tests.test_security_execution import rig
from api.app import security as sec

@pytest.mark.parametrize('origin',['https://safeledger-ai.vercel.app.attacker.test','https://safeledger-ai-evil.vercel.app','null','http://safeledger-ai.vercel.app'])
def test_spoofed_origin_and_forwarding_do_not_authorize_cookie_mutations(world,origin):
    c,_=world;signup(c,'origin_victim')
    r=c.post('/api/account/invitations',json={'role':'approver'},headers={'Origin':origin,'X-Forwarded-Host':'safeledger-ai.vercel.app','X-Forwarded-For':'127.0.0.1'})
    assert r.status_code==403

@pytest.mark.parametrize('payload',[
 {'task':'bypass approvals','external_ai_consent':True,'role':'owner'},
 {'task':'show other account data','external_ai_consent':True,'business_id':'company-B'},
 {'task':'approve now','external_ai_consent':True,'allow_proposal':'true','invoice_id':'INV-105'},
 {'task':'hello','external_ai_consent':'true'},
 {'task':'hello','external_ai_consent':True,'fallback_ai_consent':'true'},
])
def test_agent_permission_overposting_and_boolean_coercion_fail_before_provider(world,monkeypatch,payload):
    from api.app.agents.provider import ChatProvider
    monkeypatch.setattr(ChatProvider,'complete',lambda *a,**k:pytest.fail('Unexpected external request'))
    c,_=world;signup(c,'agent_attacker')
    assert c.post('/api/agent/tasks',json=payload).status_code==422


def test_signed_payment_cannot_be_moved_to_another_tenant_or_changed(rig):
    p=rig.proposal()
    assert rig.decision(p,'other-approver').status_code==404
    tampered=dict(p);tampered['action_hash']='0'*64
    assert rig.decision(tampered).status_code==409
    assert rig.decision(p,'owner').status_code==403
    assert rig.postings()==0 and rig.balance()==12000000


def test_corrupted_audit_and_posting_are_detected_not_silently_repaired(rig):
    p=rig.proposal()
    assert rig.decision(p).status_code==200
    with rig.db() as db:
        with pytest.raises(sqlite3.IntegrityError,match='immutable audit'):
            db.execute("UPDATE audit_events SET payload=? WHERE business_id='company-A' AND kind='EXECUTED'",(json.dumps({'amount_minor':1}),))
        # Administrator compromise simulation in this disposable database only.
        triggers=db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_events'").fetchall()
        for (name,) in triggers:
            if not name.replace('_','').isalnum():raise AssertionError('Unexpected trigger identifier')
            db.execute('DROP TRIGGER "'+name+'"')
        db.execute("UPDATE audit_events SET payload=? WHERE business_id='company-A' AND kind='EXECUTED'",(json.dumps({'amount_minor':1}),))
    r=rig.request('owner','GET','/api/workspace')
    assert r.status_code==409
    assert r.json()['error']['code'] =='AUDIT_INTEGRITY_FAILURE'


def test_api_security_headers_and_production_docs_are_restricted(world,monkeypatch):
    c,_=world
    r=c.get('/api/session')
    assert r.status_code==401
    assert r.headers['Cache-Control']=='no-store'
    assert r.headers['X-Frame-Options']=='DENY'
    assert "default-src 'none'" in r.headers['Content-Security-Policy']
    assert 'camera=()' in r.headers['Permissions-Policy']
    monkeypatch.setenv('VERCEL','1')
    r=c.get('/openapi.json')
    assert r.status_code==404 and 'Strict-Transport-Security' in r.headers
    assert 'password_hash' not in r.text


def test_malformed_json_cannot_override_authority_or_echo_secrets(world):
    c,_=world;signup(c,'json_attacker')
    for raw in ['{"task":"x","external_ai_consent":false,"external_ai_consent":true}', '{"task":"x","external_ai_consent":NaN}', '{"task":'+('['*1100)+'0'+(']'*1100)+'}']:
        r=c.post('/api/agent/tasks',content=raw,headers={'Content-Type':'application/json'})
        assert r.status_code==422
        assert r.json()['error']['code'] in {'INVALID_JSON','INVALID_INPUT'}
