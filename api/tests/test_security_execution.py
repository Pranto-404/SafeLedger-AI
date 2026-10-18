from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import secrets
import sqlite3
import threading
import pytest
from fastapi.testclient import TestClient
from api.app import security as sec
from api.app.contracts import ApprovalRequest
from api.app.main import app
from api.app.services.intake import parse_json
from api.app.services.storage import store_dataset

FIXTURES=Path(__file__).resolve().parents[2]/'data/fixtures'
CLOCK=int(datetime(2026,10,17,6,0,tzinfo=timezone.utc).timestamp())

@dataclass
class Rig:
    path: Path
    client: TestClient
    tokens: dict

    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.execute('PRAGMA foreign_keys=ON');return db

    def request(self,role,method,url,**kwargs):
        return self.client.request(method,url,headers={'Authorization':'Bearer '+self.tokens[role]},**kwargs)

    def proposal(self,invoice='INV-105',role='owner'):
        result=self.request(role,'POST','/api/proposals',json={'invoice_id':invoice})
        assert result.status_code==201,result.text
        return result.json()

    def decision(self,proposal,role='approver',decision='approve',hash_value=None):
        return self.request(role,'POST',f"/api/proposals/{proposal['proposal_id']}/approve",json={'proposal_hash':hash_value or proposal['action_hash'],'decision':decision})

    def postings(self):
        with closing(self.db()) as db:return db.execute('SELECT count(*) FROM postings').fetchone()[0]

    def balance(self):
        result=self.request('viewer','GET','/api/dashboard');assert result.status_code==200,result.text
        return result.json()['balance_minor']


def seed(rig,variant='seed_2026.json',business='company-A'):
    with closing(rig.db()) as db:
        ds=parse_json((FIXTURES/variant).read_bytes())
        store_dataset(db,business,ds)
        with db:
            db.execute('INSERT INTO security_policies VALUES (?,?,?)',(business,1000000,10000000))
            db.executemany('INSERT INTO trusted_vendors VALUES (?,?,1)',[(business,v) for v in sorted({x.vendor_id for x in ds.invoices})])

@pytest.fixture
def rig(tmp_path,monkeypatch):
    monkeypatch.setenv('SAFELEDGER_DB',str(tmp_path/'test.sqlite3'))
    monkeypatch.setenv('SAFELEDGER_SIGNING_KEY',secrets.token_hex(32))
    monkeypatch.setattr(sec,'now',lambda:CLOCK)
    with TestClient(app) as client:
        result=Rig(tmp_path/'test.sqlite3',client,{})
        with closing(result.db()) as db:
            for role in ['owner','approver','viewer','agent']:
                result.tokens[role]=sec.provision_session(db,'A-'+role,'company-A',role)
            result.tokens['other']=sec.provision_session(db,'B-owner','company-B','owner')
            result.tokens['other-approver']=sec.provision_session(db,'B-approver','company-B','approver')
        seed(result)
        yield result


def test_auth01_happy_path_with_separate_human_and_audit(rig):
    assert rig.balance()==12000000
    proposal=rig.proposal()
    assert proposal['state']=='AWAITING_APPROVAL' and proposal['details']['amount_minor']==3500000
    assert proposal['preview']['after_payment_minor']==8500000
    assert rig.postings()==0
    response=rig.decision(proposal)
    assert response.status_code==200,response.text
    assert response.json()['state']=='EXECUTED' and response.json()['balance_minor']==8500000
    assert rig.balance()==8500000 and rig.postings()==1
    trace=rig.request('viewer','GET','/api/audit/'+proposal['proposal_id'])
    assert trace.status_code==200,trace.text
    assert trace.json()['chain_verified'] is True
    assert [x['kind'] for x in trace.json()['events']]==['PROPOSED','APPROVED','EXECUTED']
    assert trace.json()['events'][1]['actor_id']=='A-approver'
    with closing(rig.db()) as db:
        assert db.execute('SELECT sum(delta_minor) FROM ledger_entries').fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM ledger_entries WHERE account='cash'").fetchone()[0]==1

@pytest.mark.parametrize('role',['owner','viewer','agent'])
def test_auth01_non_human_approver_denied_without_posting(rig,role):
    p=rig.proposal();response=rig.decision(p,role=role)
    assert response.status_code==403,response.text
    assert rig.balance()==12000000 and rig.postings()==0
    trace=rig.request('viewer','GET','/api/audit/'+p['proposal_id']).json()
    assert trace['events'][-1]['kind']=='DENIED'


def test_auth03_approver_cannot_self_approve(rig):
    p=rig.proposal(role='approver')
    assert rig.decision(p).status_code==403
    assert rig.postings()==0


def test_auth02_tenant_idor_on_read_approve_audit(rig):
    p=rig.proposal()
    for route in ['/api/proposals/'+p['proposal_id'],'/api/audit/'+p['proposal_id']]:
        assert rig.request('other','GET',route).status_code==404
    assert rig.decision(p,role='other-approver').status_code==404
    assert rig.request('other','GET','/api/proposals').json()['proposals']==[]
    assert rig.request('other','GET','/api/dashboard').status_code==404
    assert rig.postings()==0


def test_auth02_client_role_and_tenant_headers_have_no_authority(rig):
    p=rig.proposal()
    result=rig.client.post('/api/proposals/'+p['proposal_id']+'/approve',headers={'Authorization':'Bearer '+rig.tokens['viewer'],'X-Role':'approver','X-Business-ID':'company-A'},json={'proposal_hash':p['action_hash'],'decision':'approve'})
    assert result.status_code==403
    assert rig.postings()==0

@pytest.mark.parametrize('route',['/api/dashboard','/api/invoices','/api/proposals','/api/session','/api/audit/unknown'])
def test_auth01_no_ambient_cookie_or_missing_token(rig,route):
    assert rig.client.get(route,headers={'Cookie':'role=owner; token='+rig.tokens['owner']}).status_code==401


def test_revoked_and_expired_tokens_denied(rig,monkeypatch):
    with closing(rig.db()) as db:
        with db:db.execute("UPDATE security_users SET active=0 WHERE user_id='A-viewer'")
    assert rig.request('viewer','GET','/api/dashboard').status_code==401
    monkeypatch.setattr(sec,'now',lambda:CLOCK+3600)
    assert rig.request('owner','GET','/api/dashboard').status_code==401
    assert rig.postings()==0


def test_session_stores_hash_not_raw_token(rig):
    with closing(rig.db()) as db:
        hashes=[x[0] for x in db.execute('SELECT token_hash FROM security_sessions')]
    assert all(len(x)==64 for x in hashes)
    assert not any(token in hashes for token in rig.tokens.values())


def test_auth04_body_cannot_override_amount_payee_or_role(rig):
    response=rig.request('owner','POST','/api/proposals',json={'invoice_id':'INV-105','amount_minor':1,'vendor_id':'evil','role':'approver','business_id':'company-B'})
    assert response.status_code==422
    assert 'evil' not in response.text and rig.postings()==0
    p=rig.proposal()
    response=rig.request('approver','POST','/api/proposals/'+p['proposal_id']+'/approve',json={'proposal_hash':p['action_hash'],'decision':'approve','amount_minor':1})
    assert response.status_code==422 and rig.postings()==0


def test_auth04_wrong_approval_hash_denied(rig):
    p=rig.proposal()
    response=rig.decision(p,hash_value='0'*64)
    assert response.status_code==409 and response.json()['error']['code']=='APPROVAL_HASH_MISMATCH'
    assert rig.postings()==0


def test_auth05_expiry_boundary_and_new_proposal(rig,monkeypatch):
    p=rig.proposal();monkeypatch.setattr(sec,'now',lambda:CLOCK+900)
    response=rig.decision(p)
    assert response.status_code==409 and response.json()['error']['code']=='PROPOSAL_EXPIRED'
    assert rig.postings()==0
    fresh=rig.proposal()
    assert fresh['proposal_id']!=p['proposal_id']
    assert rig.decision(fresh).status_code==200


def test_tx01_retry_returns_same_posting(rig):
    p=rig.proposal();first=rig.decision(p)
    for _ in range(5):
        retry=rig.decision(p)
        assert retry.status_code==200 and retry.json()['posting_id']==first.json()['posting_id']
    assert rig.postings()==1 and rig.balance()==8500000


def test_pending_proposal_retry_returns_same_immutable_details(rig):
    p=rig.proposal();second=rig.proposal()
    assert p==second and rig.postings()==0


def test_rejection_and_opposite_decision_replay_denied(rig):
    p=rig.proposal();response=rig.decision(p,decision='reject')
    assert response.status_code==200 and response.json()['state']=='REJECTED'
    assert rig.decision(p).status_code==409
    assert rig.postings()==0


def test_tx02_parallel_same_action_one_posting(rig):
    p=rig.proposal()
    barrier=threading.Barrier(8)
    def run(_):
        with closing(rig.db()) as db:
            actor=sec.authenticate(db,rig.tokens['approver'])
            barrier.wait(timeout=10)
            return sec.decide(db,actor,p['proposal_id'],ApprovalRequest(proposal_hash=p['action_hash'],decision='approve'))
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(run,range(8)))
    assert len({x['posting_id'] for x in results})==1
    assert rig.postings()==1 and rig.balance()==8500000


def test_tx04_two_actions_racing_cannot_overdraw(rig):
    with closing(rig.db()) as db:
        raw=json.loads((FIXTURES/'seed_2026.json').read_text())
        raw['invoices']=[];raw['events']=[];raw['opening_balance_minor']=12000000
        for i in range(2):raw['invoices'].append(dict(source_record_id=f'src-{i}',invoice_id=f'RACE-{i}',vendor_id=f'RACE-V-{i}',invoice_number=f'R-{i}',issued_on='2026-10-01',due_on='2026-10-20',amount_minor=7000000,currency='BDT'))
        store_dataset(db,'company-RACE',raw)
        with db:
            db.execute('INSERT INTO security_policies VALUES (?,?,?)',('company-RACE',1000000,10000000))
            db.executemany('INSERT INTO trusted_vendors VALUES (?,?,1)',[('company-RACE',f'RACE-V-{i}') for i in range(2)])
        owner=sec.provision_session(db,'race-owner','company-RACE','owner')
        approver=sec.provision_session(db,'race-approver','company-RACE','approver')
        actor=sec.authenticate(db,owner)
        proposals=[sec.propose(db,actor,f'RACE-{i}') for i in range(2)]
    barrier=threading.Barrier(2)
    def run(p):
        with closing(rig.db()) as db:
            actor=sec.authenticate(db,approver);barrier.wait(timeout=10)
            try:return sec.decide(db,actor,p['proposal_id'],ApprovalRequest(proposal_hash=p['action_hash'],decision='approve'))['state']
            except sec.PolicyError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,proposals))
    assert sorted(results)==['EXECUTED','INSUFFICIENT_AVAILABLE_CASH']
    with closing(rig.db()) as db:
        assert sec.snapshot(sec.runtime_dataset(db,'company-RACE'))['balance_minor']==5000000
        assert db.execute("SELECT count(*) FROM postings WHERE business_id='company-RACE'").fetchone()[0]==1


def test_tx03_ledger_failure_rolls_back_approval_posting_and_execution_audit(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        db.execute("CREATE TRIGGER fail_second_entry BEFORE INSERT ON ledger_entries WHEN NEW.account='payables' BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    response=rig.decision(p)
    assert response.status_code==503,response.text
    assert rig.postings()==0 and rig.balance()==12000000
    with closing(rig.db()) as db:
        assert db.execute('SELECT count(*) FROM approvals').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM ledger_entries').fetchone()[0]==0
        assert db.execute("SELECT state FROM proposals WHERE proposal_id=?",(p['proposal_id'],)).fetchone()[0]=='AWAITING_APPROVAL'
    trace=rig.request('viewer','GET','/api/audit/'+p['proposal_id']).json()
    assert [x['kind'] for x in trace['events']]==['PROPOSED','DENIED']
    assert trace['events'][-1]['payload']['reason']=='STORAGE_FAILURE'
    with closing(rig.db()) as db:db.execute('DROP TRIGGER fail_second_entry')
    assert rig.decision(p).status_code==200


def test_tx05_restart_preserves_exactly_once(rig):
    p=rig.proposal();first=rig.decision(p).json()
    with TestClient(app) as restarted:
        response=restarted.post('/api/proposals/'+p['proposal_id']+'/approve',headers={'Authorization':'Bearer '+rig.tokens['approver']},json={'proposal_hash':p['action_hash'],'decision':'approve'})
        assert response.status_code==200 and response.json()['posting_id']==first['posting_id']
    assert rig.postings()==1


def test_money_forecast_after_post_has_no_second_invoice_deduction(rig):
    p=rig.proposal();assert rig.decision(p).status_code==200
    result=rig.request('viewer','POST','/api/cashflow/scenarios',json={'as_of':'2026-10-17','horizon_days':30,'reserve_minor':1000000})
    assert result.status_code==200,result.text
    assert result.json()['opening_balance_minor']==8500000
    assert result.json()['closing_balance_minor']==-1875000
    assert result.json()['days'][1]['outflow_minor']==0

@pytest.mark.parametrize('change,code',[('payee','PAYEE_NOT_ALLOWLISTED'),('limit','PAYMENT_LIMIT_EXCEEDED'),('reserve','INSUFFICIENT_AVAILABLE_CASH')])
def test_execution_rechecks_policy_after_proposal(rig,change,code):
    p=rig.proposal()
    with closing(rig.db()) as db:
        with db:
            if change=='payee':db.execute("UPDATE trusted_vendors SET enabled=0 WHERE vendor_id='VEND-105'")
            elif change=='limit':db.execute('UPDATE security_policies SET payment_limit_minor=1')
            else:db.execute('UPDATE security_policies SET reserve_minor=12000000')
    response=rig.decision(p)
    assert response.status_code==409 and response.json()['error']['code']==code
    assert rig.postings()==0


def test_source_corruption_cannot_approve(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        with db:db.execute("UPDATE source_records SET payload='{}' WHERE record_id='INV-105'")
    response=rig.decision(p)
    assert response.status_code==409 and rig.postings()==0


def test_state_forgery_does_not_replace_approval(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        with db:db.execute("UPDATE proposals SET state='APPROVED' WHERE proposal_id=?",(p['proposal_id'],))
        actor=sec.authenticate(db,rig.tokens['approver'])
        with pytest.raises(sec.PolicyError,match='APPROVAL_REQUIRED'):
            with sec.transaction(db):
                row=sec.get_proposal(db,actor,p['proposal_id']);sec.execute_approved(db,actor,row,sec.verify_proposal(db,row))
    assert rig.postings()==0


def test_forged_approval_signature_denied(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        with db:
            db.execute("UPDATE proposals SET state='APPROVED' WHERE proposal_id=?",(p['proposal_id'],))
            db.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?)',(p['proposal_id'],'A-approver','approve',p['action_hash'],CLOCK,'0'*64))
        actor=sec.authenticate(db,rig.tokens['approver'])
        with pytest.raises(sec.PolicyError,match='APPROVAL_INTEGRITY_FAILURE'):
            with sec.transaction(db):
                row=sec.get_proposal(db,actor,p['proposal_id']);sec.execute_approved(db,actor,row,sec.verify_proposal(db,row))
    assert rig.postings()==0

@pytest.mark.parametrize('table,operation',[('proposals',"UPDATE proposals SET payload='{}'"),('approvals',"UPDATE approvals SET decision='reject'"),('approvals','DELETE FROM approvals'),('postings','DELETE FROM postings'),('ledger_entries','UPDATE ledger_entries SET delta_minor=1'),('audit_events','DELETE FROM audit_events')])
def test_immutable_db_records_deny_updates_and_deletes(rig,table,operation):
    p=rig.proposal();assert rig.decision(p).status_code==200
    with closing(rig.db()) as db:
        with pytest.raises(sqlite3.IntegrityError):
            with db:db.execute(operation)
    assert rig.balance()==8500000


def test_audit_tamper_detected_even_if_trigger_is_removed(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        with db:
            db.execute('DROP TRIGGER immutable_audit_update')
            db.execute("UPDATE audit_events SET payload='{}'")
    trace=rig.request('viewer','GET','/api/audit/'+p['proposal_id'])
    assert trace.status_code==409 and trace.json()['error']['code']=='AUDIT_INTEGRITY_FAILURE'
    assert rig.decision(p).status_code==409 and rig.postings()==0


def test_proposal_tamper_fails_mac_if_immutable_trigger_removed(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        with db:
            db.execute('DROP TRIGGER immutable_proposal')
            db.execute("UPDATE proposals SET action_hash=? WHERE proposal_id=?",('0'*64,p['proposal_id']))
    assert rig.decision(p,hash_value='0'*64).status_code==409 and rig.postings()==0


def test_signing_key_outage_is_fail_closed(rig,monkeypatch):
    p=rig.proposal();monkeypatch.delenv('SAFELEDGER_SIGNING_KEY')
    response=rig.decision(p)
    assert response.status_code==503 and rig.postings()==0


def test_agent_internal_executor_cannot_inherit_human_privilege(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        actor=sec.authenticate(db,rig.tokens['agent'])
        with pytest.raises(sec.PolicyError,match='INDEPENDENT_HUMAN_EXECUTOR_REQUIRED'):
            with sec.transaction(db):
                row=sec.get_proposal(db,actor,p['proposal_id']);sec.execute_approved(db,actor,row,sec.verify_proposal(db,row))
    assert rig.postings()==0


def test_json_type_size_and_validation_errors_do_not_leak_inputs(rig):
    assert rig.client.post('/api/proposals',content=b'x',headers={'Content-Type':'text/plain'}).status_code==415
    assert rig.client.post('/api/proposals',content=b'x'*(1024*1024+1),headers={'Content-Type':'application/json'}).status_code==413
    assert rig.postings()==0


def test_request_budget_rejects_mutation_burst(rig):
    for _ in range(60):assert rig.request('owner','POST','/api/proposals',json={'invoice_id':'INV-105'}).status_code==201
    assert rig.request('owner','POST','/api/proposals',json={'invoice_id':'INV-105'}).status_code==429
    assert rig.postings()==0


def test_invalid_auth_attempts_are_rate_limited(rig):
    for _ in range(20):assert rig.client.get('/api/session',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert rig.client.get('/api/session').status_code==429


def test_fictional_financing_retired_and_session_has_server_identity(rig):
    session=rig.request('viewer','GET','/api/session').json();assert session['role']=='viewer' and session['business_id']=='company-A'
    result=rig.request('viewer','POST','/api/finance/compare',json={'principal_minor':5000000})
    assert result.status_code==410 and result.json()['error']['code']=='FICTIONAL_FINANCING_RETIRED'


@pytest.mark.parametrize('variant',['duplicate_exact.json','duplicate_possible.json'])
def test_duplicate_invoice_cannot_be_proposed_or_posted(rig,variant):
    business='duplicate-business'
    seed(rig,variant,business)
    with closing(rig.db()) as db:
        token=sec.provision_session(db,'duplicate-owner',business,'owner')
        actor=sec.authenticate(db,token)
        with pytest.raises(sec.PolicyError,match='DUPLICATE_INVOICE_BLOCKED'):
            sec.propose(db,actor,'INV-104')
    assert rig.postings()==0


def test_memo_prompt_injection_cannot_gain_authority(rig):
    business='injection-business';seed(rig,'untrusted_memo.json',business)
    with closing(rig.db()) as db:
        agent=sec.provision_session(db,'injection-agent',business,'agent')
        actor=sec.authenticate(db,agent)
        p=sec.propose(db,actor,'INV-105')
        assert p['details']['amount_minor']==3500000
        assert 'SYSTEM OVERRIDE' not in json.dumps(p)
        with pytest.raises(sec.PolicyError,match='HUMAN_APPROVER_REQUIRED'):
            sec.decide(db,actor,p['proposal_id'],ApprovalRequest(proposal_hash=p['action_hash'],decision='approve'))
        assert db.execute('SELECT count(*) FROM postings').fetchone()[0]==0
        assert 'Reveal secrets' not in json.dumps(sec.verified_audit(db,business))


def test_import_requires_owner_and_is_audited_atomically(rig):
    body=json.loads((FIXTURES/'seed_2026.json').read_text())
    assert rig.request('viewer','POST','/api/invoices/import',json=body).status_code==403
    assert rig.request('agent','POST','/api/invoices/import',json=body).status_code==403
    response=rig.request('other','POST','/api/invoices/import',json=body)
    assert response.status_code==201,response.text
    assert rig.request('other','GET','/api/dashboard').json()['balance_minor']==12000000
    assert rig.request('other','GET','/api/audit/import').json()['events'][0]['kind']=='IMPORTED'
    assert rig.request('other','POST','/api/invoices/import',json=body).status_code==409
    assert rig.request('other','GET','/api/dashboard').json()['balance_minor']==12000000
    # Import grants no payee authority; trusted allowlist/policy still requires local admin.
    assert rig.request('other','POST','/api/proposals',json={'invoice_id':'INV-105'}).status_code==409


def test_failed_import_audit_rolls_back_dataset(rig,monkeypatch):
    body=json.loads((FIXTURES/'seed_2026.json').read_text())
    monkeypatch.delenv('SAFELEDGER_SIGNING_KEY')
    assert rig.request('other','POST','/api/invoices/import',json=body).status_code==503
    with closing(rig.db()) as db:assert db.execute("SELECT count(*) FROM financial_datasets WHERE business_id='company-B'").fetchone()[0]==0


def test_second_boundaries_do_not_invalidate_signed_timestamps(rig,monkeypatch):
    import itertools
    ticks=itertools.count(CLOCK)
    monkeypatch.setattr(sec,'now',lambda:next(ticks))
    p=rig.proposal();response=rig.decision(p)
    assert response.status_code==200,response.text
    assert rig.balance()==8500000


def test_forged_approval_actor_and_expired_decision_cannot_execute(rig):
    p=rig.proposal()
    with closing(rig.db()) as db:
        # A syntactically valid approval row is insufficient without the server MAC.
        with db:
            db.execute("UPDATE proposals SET state='APPROVED' WHERE proposal_id=?",(p['proposal_id'],))
            db.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?)',(p['proposal_id'],'A-owner','approve',p['action_hash'],CLOCK+900,'0'*64))
        actor=sec.authenticate(db,rig.tokens['approver'])
        with pytest.raises(sec.PolicyError,match='APPROVAL_INTEGRITY_FAILURE'):
            with sec.transaction(db):
                row=sec.get_proposal(db,actor,p['proposal_id']);sec.execute_approved(db,actor,row,sec.verify_proposal(db,row))
    assert rig.postings()==0


@pytest.mark.parametrize('body',[b'{"invoice_id":"INV-105","invoice_id":"INV-104"}',b'{"invoice_id":NaN}',b'{broken'])
def test_duplicate_keys_and_invalid_json_are_refused(rig,body):
    response=rig.client.post('/api/proposals',headers={'Content-Type':'application/json','Authorization':'Bearer '+rig.tokens['owner']},content=body)
    assert response.status_code==422 and response.json()['error']['code']=='INVALID_JSON'
    assert rig.postings()==0


def test_full_audit_export_offline_hash_chain_recomputes(rig):
    p=rig.proposal();assert rig.decision(p).status_code==200
    result=rig.request('viewer','GET','/api/audit').json()
    previous='0'*64
    import hashlib
    for event in result['events']:
        assert event['previous_hash']==previous
        body={key:value for key,value in event.items() if key not in {'event_id','event_hash'}}
        previous=hashlib.sha256(sec.canonical(body).encode()).hexdigest()
        assert previous==event['event_hash']
    assert previous==result['tenant_chain_head']


def test_http_parallel_approvals_survive_fastapi_worker_handoff(rig):
    p=rig.proposal()
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses=list(pool.map(lambda _:rig.decision(p),range(8)))
    assert [x.status_code for x in responses]==[200]*8
    assert len({x.json()['posting_id'] for x in responses})==1
    assert rig.postings()==1 and rig.balance()==8500000


def test_private_bootstrap_permissions_and_no_overwrite(tmp_path):
    import subprocess,sys,os
    root=Path(__file__).resolve().parents[2]
    destination=tmp_path/'private-demo'
    command=[sys.executable,'scripts/bootstrap_demo.py','--directory',str(destination)]
    result=subprocess.run(command,cwd=root,check=True,capture_output=True,text=True)
    secrets_file=destination/'sessions.json';env_file=destination/'demo.env'
    before=env_file.read_bytes()
    tokens=json.loads(secrets_file.read_text())['bearer_tokens']
    assert set(tokens)=={'owner','approver','viewer','agent'}
    for token in tokens.values():assert token not in result.stdout+result.stderr
    assert 'SAFELEDGER_SIGNING_KEY=' not in result.stdout+result.stderr
    if os.name!='nt':
        assert secrets_file.stat().st_mode & 0o777==0o600
        assert env_file.stat().st_mode & 0o777==0o600
    rejected=subprocess.run(command,cwd=root,capture_output=True,text=True)
    assert rejected.returncode!=0 and env_file.read_bytes()==before
