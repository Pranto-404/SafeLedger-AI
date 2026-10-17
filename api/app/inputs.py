"""Owner-entered sandbox records. Append only, versioned, atomic and idempotent."""
import hashlib
import json
import uuid
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field
from api.app import security as sec
from api.app.accounts import today_bd
from api.app.contracts import Contract, PositiveMinor, ISODate, RecordId
from api.app.routes import db_connection, principal
from api.app.services.finance import validated, fingerprint, snapshot

router=APIRouter(prefix='/api')


class InputRecord(Contract):
    request_id: str = Field(pattern=r'^[a-f0-9-]{36}$')
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    kind: Literal['invoice','cash']
    amount_minor: PositiveMinor
    effective_on: ISODate
    direction: Literal['inflow','outflow'] = 'inflow'
    status: Literal['cleared','scheduled'] = 'cleared'
    vendor_id: RecordId | None = None
    invoice_number: str | None = Field(default=None,min_length=1,max_length=80)
    due_on: ISODate | None = None
    memo: str = Field(default='',max_length=2000)
    trust_vendor: bool = Field(default=False,strict=True)


@router.post('/workspace/records',status_code=201)
def add_record(body:InputRecord,actor=Depends(principal),db=Depends(db_connection)):
    if actor.role!='owner':sec.fail(403,'OWNER_REQUIRED')
    if not db.execute('SELECT 1 FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone():sec.fail(403,'ACCOUNT_REQUIRED')
    digest=hashlib.sha256(sec.canonical(body.model_dump(mode='json')).encode()).hexdigest()
    with sec.transaction(db):
        current=sec.recheck(db,actor)
        if current.role!='owner':sec.fail(403,'OWNER_REQUIRED')
        sec.verified_audit(db,current.business_id)
        prior=db.execute('SELECT body_sha256 FROM workspace_input_requests WHERE business_id=? AND request_id=?',(current.business_id,body.request_id)).fetchone()
        if prior:
            if prior[0]!=digest:sec.fail(409,'INPUT_REQUEST_CONFLICT')
            return dict(replayed=True,simulation_only=True)
        ds=sec.original_dataset(db,current.business_id)
        if fingerprint(ds)!=body.expected_revision:sec.fail(409,'DATA_CHANGED_REFRESH_REQUIRED')
        raw=ds.model_dump(mode='json');record_id='manual-'+body.request_id
        if body.effective_on<ds.opening_on:sec.fail(422,'DATE_BEFORE_OPENING')
        if body.kind=='invoice':
            if not body.vendor_id or not body.invoice_number or not body.due_on:sec.fail(422,'INVOICE_FIELDS_REQUIRED')
            if body.effective_on>today_bd() or body.due_on<body.effective_on:sec.fail(422,'INVALID_INVOICE_DATES')
            if body.direction!='inflow' or body.status!='cleared':sec.fail(422,'UNEXPECTED_INVOICE_CASH_FIELDS')
            record=dict(source_record_id=record_id,invoice_id=record_id,vendor_id=body.vendor_id,invoice_number=body.invoice_number,issued_on=body.effective_on.isoformat(),due_on=body.due_on.isoformat(),amount_minor=body.amount_minor,currency='BDT',status='open',memo=body.memo)
            raw['invoices'].append(record);kind='invoice'
        else:
            if body.vendor_id or body.invoice_number or body.due_on or body.trust_vendor or body.memo:sec.fail(422,'UNEXPECTED_CASH_INVOICE_FIELDS')
            if body.status=='cleared' and body.effective_on>today_bd():sec.fail(422,'CLEARED_DATE_IN_FUTURE')
            record=dict(source_record_id=record_id,event_id=record_id,direction=body.direction,status=body.status,effective_on=body.effective_on.isoformat(),amount_minor=body.amount_minor,currency='BDT',invoice_id=None)
            raw['events'].append(record);kind='event'
        raw['as_of']=max(ds.as_of,today_bd()).isoformat()
        try:new=validated(raw)
        except ValueError:sec.fail(422,'INVALID_FINANCIAL_RECORD')
        # Save immutable old economics before the head revision advances.
        db.execute('INSERT OR IGNORE INTO dataset_versions VALUES (?,?,?)',(current.business_id,fingerprint(ds),ds.model_dump_json()))
        db.execute('UPDATE financial_datasets SET dataset_sha256=?,payload=? WHERE business_id=?',(fingerprint(new),new.model_dump_json(),current.business_id))
        typed=new.invoices[-1] if kind=='invoice' else new.events[-1]
        db.execute('INSERT INTO source_records VALUES (?,?,?,?,?,?)',(current.business_id,record_id,kind,record_id,fingerprint(typed),typed.model_dump_json()))
        if body.kind=='invoice' and body.trust_vendor:
            db.execute('INSERT INTO trusted_vendors VALUES (?,?,1) ON CONFLICT(business_id,vendor_id) DO UPDATE SET enabled=1',(current.business_id,body.vendor_id))
        # Validate all existing signed postings against the extended source before commit.
        runtime=sec.runtime_dataset(db,current.business_id)
        if len(runtime.events)>2000:sec.fail(409,'RUNTIME_EVENT_CAPACITY_EXCEEDED')
        db.execute('INSERT INTO workspace_input_requests VALUES (?,?,?)',(current.business_id,body.request_id,digest))
        sec.audit(db,current,'input-'+body.request_id,'RECORD_ADDED',dict(source_id=record_id,kind=kind,previous_revision=fingerprint(ds),dataset_sha256=fingerprint(new),record_sha256=fingerprint(typed),payee_allowed=body.trust_vendor))
    return dict(source_id=record_id,replayed=False,simulation_only=True)


from api.app.services.finance import Dataset

@router.post('/workspace/import',status_code=201)
def import_initial(body:Dataset,actor=Depends(principal),db=Depends(db_connection)):
    """Replace only a completely untouched zero workspace, never existing finances."""
    if actor.role!='owner':sec.fail(403,'OWNER_REQUIRED')
    with sec.transaction(db):
        current=sec.recheck(db,actor)
        if current.role!='owner':sec.fail(403,'OWNER_REQUIRED')
        sec.verified_audit(db,current.business_id)
        previous=sec.original_dataset(db,current.business_id)
        if previous.invoices or previous.events or previous.opening_balance_minor or db.execute('SELECT 1 FROM proposals WHERE business_id=?',(current.business_id,)).fetchone():sec.fail(409,'WORKSPACE_NOT_EMPTY')
        new=validated(body)
        db.execute('INSERT OR IGNORE INTO dataset_versions VALUES (?,?,?)',(current.business_id,fingerprint(previous),previous.model_dump_json()))
        db.execute('UPDATE financial_datasets SET dataset_sha256=?,payload=? WHERE business_id=?',(fingerprint(new),new.model_dump_json(),current.business_id))
        for kind,record_id,record in [('invoice',i.invoice_id,i) for i in new.invoices]+[('event',e.event_id,e) for e in new.events]:
            db.execute('INSERT INTO source_records VALUES (?,?,?,?,?,?)',(current.business_id,record.source_record_id,kind,record_id,fingerprint(record),record.model_dump_json()))
        sec.audit(db,current,'import-'+uuid.uuid4().hex,'IMPORTED',dict(dataset_sha256=fingerprint(new),invoice_count=len(new.invoices),event_count=len(new.events),payees_allowlisted=False))
    return dict(dataset_sha256=fingerprint(new),simulation_only=True)


class VendorPermission(Contract):
    vendor_id: RecordId
    enabled: bool = Field(strict=True)

@router.post('/workspace/vendor-permission')
def vendor_permission(body:VendorPermission,actor=Depends(principal),db=Depends(db_connection)):
    if actor.role!='owner':sec.fail(403,'OWNER_REQUIRED')
    with sec.transaction(db):
        current=sec.recheck(db,actor)
        if current.role!='owner':sec.fail(403,'OWNER_REQUIRED')
        sec.verified_audit(db,current.business_id)
        ds=sec.original_dataset(db,current.business_id)
        if not any(i.vendor_id==body.vendor_id for i in ds.invoices):sec.fail(404,'VENDOR_NOT_FOUND')
        db.execute('INSERT INTO trusted_vendors VALUES (?,?,?) ON CONFLICT(business_id,vendor_id) DO UPDATE SET enabled=excluded.enabled',(current.business_id,body.vendor_id,int(body.enabled)))
        sec.audit(db,current,'payee-'+uuid.uuid4().hex,'PAYEE_PERMISSION_CHANGED',{'vendor_id':body.vendor_id,'enabled':body.enabled})
    return {'simulation_only':True}
