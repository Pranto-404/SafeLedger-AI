"""Financing-option matching. Read-only over the ledger; records a signed analysis event."""
import uuid
from fastapi import APIRouter, Depends
from api.app import security as sec
from api.app.routes import db_connection, principal
from api.app.services.financing import FinancingMatchRequest, match_financing

router=APIRouter(prefix='/api')


@router.post('/financing/match')
def financing_match(body:FinancingMatchRequest,actor=Depends(principal),db=Depends(db_connection)):
    if actor.role not in {'owner','approver'}:sec.fail(403,'OWNER_OR_APPROVER_REQUIRED')
    sec.budget(db,'financing:'+actor.business_id,30)
    sec.verified_audit(db,actor.business_id)
    ds=sec.runtime_dataset(db,actor.business_id)
    if body.as_of!=ds.as_of:sec.fail(409,'SNAPSHOT_DATE_CHANGED_REFRESH_REQUIRED')
    policy=db.execute('SELECT reserve_minor FROM security_policies WHERE business_id=?',(actor.business_id,)).fetchone()
    if policy is None:sec.fail(409,'POLICY_NOT_CONFIGURED')
    if any(q.currency!=ds.currency for q in body.quotes):sec.fail(422,'QUOTE_CURRENCY_MISMATCH')
    if any(q.quoted_on>ds.as_of for q in body.quotes):sec.fail(422,'QUOTE_DATE_AFTER_SNAPSHOT')
    try:result=match_financing(ds,policy[0],body)
    except ValueError:sec.fail(422,'QUOTE_TERMS_INVALID')
    trace='financing-'+str(uuid.uuid4())
    with sec.transaction(db):
        current=sec.recheck(db,actor)
        sec.audit(db,current,trace,'FINANCING_ANALYZED',dict(analysis_sha256=result['analysis_sha256'],quote_count=len(body.quotes),funding_need_minor=result['funding_need_minor'],best_match_quote_id=result['best_match_quote_id'],dataset_sha256=sec.fingerprint(ds)))
    return dict(result,trace_id=trace,simulation_only=True)
