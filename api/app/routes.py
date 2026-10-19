"""Authenticated financial routes. No public execute/session-provisioning endpoint."""
from contextlib import closing
import hashlib
import json
import sqlite3
from typing import Annotated
from fastapi import APIRouter, Depends, Path as ApiPath, Request
from api.app import security as sec
from api.app.contracts import ApprovalRequest, Contract, PositiveMinor, ProposalRequest, ScenarioRequest
from api.app.services.finance import Dataset, FinancingRequest, compare_financing, project_cashflow, snapshot
from api.app.services.storage import store_dataset

ProposalPath=Annotated[str,ApiPath(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')]
TracePath=Annotated[str,ApiPath(pattern=r'^[A-Za-z0-9-]{1,80}$')]
router=APIRouter(prefix='/api')


def db_connection():
    from api.app.main import connect
    with closing(connect()) as db:
        yield db


def principal(request: Request, db=Depends(db_connection)):
    authorization=request.headers.get('Authorization','')
    try:
        parts=authorization.split()
        if authorization:
            if len(parts)!=2 or parts[0].lower()!='bearer':sec.fail(401,'AUTHENTICATION_REQUIRED')
            token=parts[1]
        else:
            from api.app.accounts import COOKIE,browser_origin
            token=request.cookies.get(COOKIE,'')
            if token and request.method not in {'GET','HEAD','OPTIONS'}:browser_origin(request)
        actor=sec.authenticate(db,token)
    except sec.PolicyError:
        peer=request.client.host if request.client else 'unknown'
        sec.budget(db,'auth-failure:'+hashlib.sha256(peer.encode()).hexdigest(),20)
        raise
    sec.budget(db,'session:'+actor.token_hash,240 if request.method=='GET' else 60)
    from api.app.accounts import PUBLIC_TEMPLATES
    meta=db.execute('SELECT kind FROM workspace_meta WHERE business_id=?',(actor.business_id,)).fetchone()
    if actor.business_id in PUBLIC_TEMPLATES or (meta and meta[0]=='demo'):
        sec.fail(403,'ARCHIVED_EXAMPLE_WORKSPACE')
    return actor


@router.get('/session')
def session(actor=Depends(principal),db=Depends(db_connection)):
    from api.app.accounts import identity
    return identity(db,actor)


@router.post('/invoices/import',status_code=201)
def import_dataset(body: Dataset,actor=Depends(principal),db=Depends(db_connection)):
    def authorize():
        current=sec.recheck(db,actor)
        if current.role!='owner':sec.fail(403,'OWNER_REQUIRED')
        sec.verified_audit(db,current.business_id)
    def evidence(ds,checksum):
        sec.audit(db,actor,'import','IMPORTED',dict(dataset_sha256=checksum,invoice_count=len(ds.invoices),event_count=len(ds.events)))
    try:
        result=store_dataset(db,actor.business_id,body,before_write=authorize,after_write=evidence)
    except sec.PolicyError as exc:
        sec.deny_event(db,actor,'import',exc.code)
        raise
    except sqlite3.IntegrityError:
        sec.deny_event(db,actor,'import','DATASET_ALREADY_IMPORTED')
        sec.fail(409,'DATASET_ALREADY_IMPORTED')
    return dict(result,simulation_only=True)


@router.get('/dashboard')
def dashboard(actor=Depends(principal),db=Depends(db_connection)):
    sec.verified_audit(db,actor.business_id)
    ds=sec.runtime_dataset(db,actor.business_id)
    return dict(snapshot(ds),simulation_only=True)


@router.get('/invoices')
def invoices(actor=Depends(principal),db=Depends(db_connection)):
    ds=sec.runtime_dataset(db,actor.business_id)
    return dict(invoices=[x.model_dump(mode='json') for x in ds.invoices],simulation_only=True)


@router.post('/cashflow/scenarios')
def cashflow(body: ScenarioRequest,actor=Depends(principal),db=Depends(db_connection)):
    ds=sec.runtime_dataset(db,actor.business_id)
    if body.as_of!=ds.as_of:sec.fail(409,'SNAPSHOT_DATE_CHANGED_REFRESH_REQUIRED')
    return dict(project_cashflow(ds,body),simulation_only=True)


class CompareRequest(Contract):
    principal_minor: PositiveMinor


@router.post('/finance/compare')
def financing(body:CompareRequest,actor=Depends(principal)):
    sec.fail(410,'FICTIONAL_FINANCING_RETIRED')


@router.post('/proposals',status_code=201)
def proposal(body: ProposalRequest,actor=Depends(principal),db=Depends(db_connection)):
    return sec.propose(db,actor,body.invoice_id)


@router.get('/proposals')
def list_proposals(actor=Depends(principal),db=Depends(db_connection)):
    db.row_factory=sqlite3.Row
    rows=db.execute('SELECT * FROM proposals WHERE business_id=? ORDER BY rowid DESC LIMIT 200',(actor.business_id,)).fetchall()
    for row in rows:sec.verify_proposal(db,row)
    return {'proposals':[sec.proposal_view(row) for row in rows],'simulation_only':True}


@router.get('/proposals/{proposal_id}')
def get_proposal(proposal_id: ProposalPath,actor=Depends(principal),db=Depends(db_connection)):
    row=sec.get_proposal(db,actor,proposal_id)
    sec.verify_proposal(db,row)
    return sec.proposal_view(row)


@router.post('/proposals/{proposal_id}/approve')
def decide(proposal_id: ProposalPath,body: ApprovalRequest,actor=Depends(principal),db=Depends(db_connection)):
    return sec.decide(db,actor,proposal_id,body)


@router.get('/audit/{trace_id}')
def trace(trace_id: TracePath,actor=Depends(principal),db=Depends(db_connection)):
    all_events=sec.verified_audit(db,actor.business_id)
    events=[x for x in all_events if x['trace_id']==trace_id]
    if not events:sec.fail(404,'TRACE_NOT_FOUND')
    return dict(trace_id=trace_id,events=events,chain_verified=True,tenant_chain_head=all_events[-1]['event_hash'],simulation_only=True)


@router.get('/audit')
def export_audit(actor=Depends(principal),db=Depends(db_connection)):
    events=sec.verified_audit(db,actor.business_id)
    return dict(events=events,chain_verified=True,tenant_chain_head=events[-1]['event_hash'] if events else '0'*64,simulation_only=True)


from api.app.agents.models import TaskRequest

@router.post('/agent/tasks')
def agent_task(body: TaskRequest,actor=Depends(principal),db=Depends(db_connection)):
    from api.app.accounts import PUBLIC_TEMPLATES
    if actor.business_id in PUBLIC_TEMPLATES:sec.fail(403,'CREATE_ACCOUNT_FOR_ASSISTANT')
    if not body.external_ai_consent:sec.fail(403,'EXTERNAL_AI_CONSENT_REQUIRED')
    if db.execute('SELECT 1 FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone():
        sec.budget(db,'public-ai-global',8)
    from api.app.agents import runner
    return runner.run_task(db,actor,body)

@router.get('/workspace')
def workspace_bundle(actor=Depends(principal),db=Depends(db_connection)):
    """One consistent read snapshot avoids seven repeated remote database loads."""
    from pathlib import Path
    db.execute('BEGIN')
    with db:
        events=sec.verified_audit(db,actor.business_id)
        ds=sec.runtime_dataset(db,actor.business_id)
        rows=db.execute('SELECT * FROM proposals WHERE business_id=? ORDER BY rowid DESC LIMIT 200',(actor.business_id,)).fetchall()
        for row in rows:sec.verify_proposal(db,row)
        policy=db.execute('SELECT reserve_minor,payment_limit_minor FROM security_policies WHERE business_id=?',(actor.business_id,)).fetchone()
        if policy is None:sec.fail(409,'POLICY_NOT_CONFIGURED')
        week=project_cashflow(ds,ScenarioRequest(as_of=ds.as_of,horizon_days=7,reserve_minor=policy[0],delay_inflows_days=0))
        month=project_cashflow(ds,ScenarioRequest(as_of=ds.as_of,horizon_days=30,reserve_minor=policy[0],delay_inflows_days=0))
        notes={a['payload']['source_id']:a['payload'].get('note','') for a in events if a['kind']=='RECORD_ADDED'}
        return dict(dataset_revision=sec.fingerprint(sec.original_dataset(db,actor.business_id)),snapshot=snapshot(ds),invoices=[i.model_dump(mode='json') for i in ds.invoices],events=[dict(e.model_dump(mode='json'),note=notes.get(e.source_record_id,'')) for e in ds.events],proposals=[sec.proposal_view(row) for row in rows],audit=dict(events=events,chain_verified=True,tenant_chain_head=events[-1]['event_hash'] if events else '0'*64),week=week,month=month,policy=dict(reserve_minor=policy[0],payment_limit_minor=policy[1]),simulation_only=True)


@router.get('/workspace/export')
def export_workspace(actor=Depends(principal),db=Depends(db_connection)):
    db.execute('BEGIN')
    with db:
        events=sec.verified_audit(db,actor.business_id)
        original=sec.original_dataset(db,actor.business_id)
        current=sec.runtime_dataset(db,actor.business_id)
        return dict(format_version=1,workspace_id=actor.business_id,original_dataset=original.model_dump(mode='json'),current_dataset=current.model_dump(mode='json'),audit_events=events,recordkeeping_only=True,simulation_only=True)


@router.get('/agent/status')
def agent_status(actor=Depends(principal)):
    import os
    from api.app.agents.provider import ChatProvider,ProviderError
    from api.app.agents.fallback import configured_secondary
    profile=os.environ.get('SAFELEDGER_LLM_PROFILE','gemini_free')
    reason=None
    try:ChatProvider();configured=True
    except ProviderError as exc:configured=False;reason=exc.code
    return dict(provider_name='Google Gemini' if profile=='gemini_free' else 'Configured external provider',configured=configured,configuration_error=reason,availability_checked=False,fallback_provider='OpenAI',fallback_configured=configured_secondary(),free_only=os.environ.get('SAFELEDGER_ALLOW_PAID_AI')!='1',simulation_only=True)


from pydantic import StrictBool

class SyntheticDiagnostic(Contract):
    confirm_synthetic_test: StrictBool = False

@router.post('/agent/diagnostic')
def agent_diagnostic(body:SyntheticDiagnostic,actor=Depends(principal),db=Depends(db_connection)):
    if actor.role!='owner':sec.fail(403,'OWNER_REQUIRED')
    if not body.confirm_synthetic_test:sec.fail(403,'SYNTHETIC_TEST_CONFIRMATION_REQUIRED')
    sec.budget(db,'provider-diagnostic:'+actor.business_id,2)
    sec.budget(db,'public-ai-global',8)
    from api.app.agents.diagnostic import synthetic_check
    # This function has no dataset access. No account identifiers or records are sent.
    return synthetic_check()
