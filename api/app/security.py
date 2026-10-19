"""M2 security boundary. No LLM or public function can post directly to the ledger."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from api.app.ratelimit import limiter
from api.app.services.finance import analyze_duplicates, fingerprint, invoice_key, snapshot, validated
from api.app.services.storage import create_schema as financial_schema, load_dataset


def now():
    return int(time.time())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


class PolicyError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def fail(status, code):
    raise PolicyError(status, code)


def signature(kind, value):
    key = os.environ.get('SAFELEDGER_SIGNING_KEY', '')
    if len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
        fail(503, 'SIGNING_KEY_NOT_CONFIGURED')
    return hmac.new(bytes.fromhex(key), (kind + ':' + canonical(value)).encode(), hashlib.sha256).hexdigest()


def create_schema(db):
    financial_schema(db)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS security_users(
      user_id TEXT PRIMARY KEY, business_id TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('owner','approver','viewer','agent')),
      active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)));
    CREATE TABLE IF NOT EXISTS security_sessions(
      token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES security_users(user_id),
      expires_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS security_policies(
      business_id TEXT PRIMARY KEY, reserve_minor INTEGER NOT NULL CHECK(typeof(reserve_minor)='integer' AND reserve_minor>=0),
      payment_limit_minor INTEGER NOT NULL CHECK(typeof(payment_limit_minor)='integer' AND payment_limit_minor>0));
    CREATE TABLE IF NOT EXISTS trusted_vendors(
      business_id TEXT NOT NULL, vendor_id TEXT NOT NULL, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), PRIMARY KEY(business_id,vendor_id));
    CREATE TABLE IF NOT EXISTS proposals(
      proposal_id TEXT PRIMARY KEY, business_id TEXT NOT NULL, invoice_id TEXT NOT NULL,
      proposer_id TEXT NOT NULL REFERENCES security_users(user_id), payload TEXT NOT NULL,
      action_hash TEXT NOT NULL, signature TEXT NOT NULL,
      state TEXT NOT NULL CHECK(state IN ('AWAITING_APPROVAL','APPROVED','EXECUTED','REJECTED','EXPIRED')));
    CREATE UNIQUE INDEX IF NOT EXISTS one_pending_invoice ON proposals(business_id,invoice_id) WHERE state IN ('AWAITING_APPROVAL','APPROVED');
    CREATE TABLE IF NOT EXISTS approvals(
      proposal_id TEXT PRIMARY KEY REFERENCES proposals(proposal_id), approver_id TEXT NOT NULL REFERENCES security_users(user_id),
      decision TEXT NOT NULL CHECK(decision IN ('approve','reject')), action_hash TEXT NOT NULL, decision_at INTEGER NOT NULL, signature TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS postings(
      posting_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE REFERENCES proposals(proposal_id),
      business_id TEXT NOT NULL, invoice_id TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK(typeof(amount_minor)='integer' AND amount_minor>0),
      created_at INTEGER NOT NULL, signature TEXT NOT NULL, UNIQUE(business_id,invoice_id));
    CREATE TABLE IF NOT EXISTS ledger_entries(
      entry_id TEXT PRIMARY KEY, posting_id TEXT NOT NULL REFERENCES postings(posting_id),
      account TEXT NOT NULL CHECK(account IN ('cash','payables')),
      delta_minor INTEGER NOT NULL CHECK(typeof(delta_minor)='integer' AND delta_minor!=0), UNIQUE(posting_id,account));
    CREATE TABLE IF NOT EXISTS audit_events(
      event_id INTEGER PRIMARY KEY AUTOINCREMENT, business_id TEXT NOT NULL, trace_id TEXT NOT NULL,
      actor_id TEXT NOT NULL, kind TEXT NOT NULL, created_at INTEGER NOT NULL, payload TEXT NOT NULL,
      previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, signature TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS request_budgets(scope TEXT NOT NULL, window INTEGER NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(scope,window));
    CREATE TRIGGER IF NOT EXISTS immutable_proposal BEFORE UPDATE OF proposal_id,business_id,invoice_id,proposer_id,payload,action_hash,signature ON proposals BEGIN SELECT RAISE(ABORT,'immutable proposal'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_approval_update BEFORE UPDATE ON approvals BEGIN SELECT RAISE(ABORT,'immutable approval'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_approval_delete BEFORE DELETE ON approvals BEGIN SELECT RAISE(ABORT,'immutable approval'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_posting_update BEFORE UPDATE ON postings BEGIN SELECT RAISE(ABORT,'immutable posting'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_posting_delete BEFORE DELETE ON postings BEGIN SELECT RAISE(ABORT,'immutable posting'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_ledger_update BEFORE UPDATE ON ledger_entries BEGIN SELECT RAISE(ABORT,'immutable ledger'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_ledger_delete BEFORE DELETE ON ledger_entries BEGIN SELECT RAISE(ABORT,'immutable ledger'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_audit_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
    CREATE TRIGGER IF NOT EXISTS immutable_audit_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
    ''')


# One writer at a time inside this process. The production database has a single remote writer; queueing here
# (instead of racing BEGIN IMMEDIATE across many threads) avoids busy errors and lock convoys under bursts.
WRITE_LOCK = threading.RLock()


@contextmanager
def transaction(db):
    if db.in_transaction:
        raise RuntimeError('Financial operation requires its own transaction')
    if not WRITE_LOCK.acquire(timeout=30):
        fail(503,'SERVER_BUSY')
    try:
        db.execute('BEGIN IMMEDIATE')
        try:
            yield
            db.commit()
        except BaseException:
            db.rollback()
            raise
    finally:
        WRITE_LOCK.release()


@dataclass(frozen=True)
class Principal:
    user_id: str
    business_id: str
    role: str
    token_hash: str


def provision_session(db, user_id, business_id, role, ttl_seconds=3600):
    """Trusted local provisioning only; never exposed as an HTTP role-switch API."""
    if role not in {'owner','approver','viewer','agent'} or not 1 <= ttl_seconds <= 86400:
        raise ValueError('Invalid server provisioning settings')
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db:
        db.execute('INSERT INTO security_users(user_id,business_id,role) VALUES (?,?,?)', (user_id,business_id,role))
        db.execute('INSERT INTO security_sessions VALUES (?,?,?)', (token_hash,user_id,now()+ttl_seconds))
    return token


def resolve_hash(db, token_hash):
    row = db.execute('SELECT u.user_id,u.business_id,u.role FROM security_sessions s JOIN security_users u ON s.user_id=u.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1', (token_hash,now())).fetchone()
    if row is None:
        fail(401,'INVALID_OR_EXPIRED_SESSION')
    return Principal(*row,token_hash)


def authenticate(db, token):
    if not isinstance(token,str) or not 20 <= len(token) <= 200:
        fail(401,'AUTHENTICATION_REQUIRED')
    return resolve_hash(db,hashlib.sha256(token.encode()).hexdigest())


def recheck(db, principal):
    return resolve_hash(db,principal.token_hash)


def budgets(db, items):
    """Increment per-minute request budgets; 429 if any is over its limit.

    Counters are process-local (see ratelimit.py): hostile traffic must never cost a database write. `db` is kept
    so existing call sites do not change.
    """
    if limiter.hit(items):
        fail(429,'REQUEST_BUDGET_EXCEEDED')


def budget(db, scope, limit):
    budgets(db,[(scope,limit)])


def _address(value):
    value = (value or '').strip()[:64]
    return value or None


def client_keys(request):
    """Return (claimed, edge) hashed client identifiers for rate limits.

    The API sits behind Vercel and Render's Cloudflare edge. uvicorn trusts X-Forwarded-For and reports its
    LEFT-most entry, which a direct caller can set to anything. So:
      edge    = the connection address added by infrastructure (cf-connecting-ip, else the right-most
                X-Forwarded-For entry, else the socket peer). A caller cannot choose it; users behind Vercel
                share it, so its limits are generous and mainly stop single-origin floods.
      claimed = the best-effort end-user address (left-most entry) for fairness between normal users.
                It is spoofable, so no security decision depends on it alone.
    """
    headers = request.headers
    chain = [x for x in (_address(v) for v in headers.get('x-forwarded-for','').split(',')[:20]) if x]
    peer = _address(request.client.host if request.client else None)
    edge = _address(headers.get('cf-connecting-ip')) or _address(headers.get('true-client-ip')) or (chain[-1] if chain else None) or peer or 'unknown'
    claimed = (chain[0] if chain else None) or peer or edge
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()[:32]
    return digest(claimed), digest(edge)


def prune_expired_sessions(db):
    if db.in_transaction:
        db.execute('DELETE FROM security_sessions WHERE expires_at<?',(now(),))


def audit(db, principal, trace, kind, payload):
    if not db.in_transaction:
        raise RuntimeError('Audit must be in the same transaction as financial state')
    previous = db.execute('SELECT event_hash FROM audit_events WHERE business_id=? ORDER BY event_id DESC LIMIT 1',(principal.business_id,)).fetchone()
    previous = previous[0] if previous else '0'*64
    data = dict(business_id=principal.business_id,trace_id=trace,actor_id=principal.user_id,kind=kind,created_at=now(),payload=payload,previous_hash=previous)
    digest = hashlib.sha256(canonical(data).encode()).hexdigest()
    db.execute('INSERT INTO audit_events(business_id,trace_id,actor_id,kind,created_at,payload,previous_hash,event_hash,signature) VALUES (?,?,?,?,?,?,?,?,?)',
               (principal.business_id,trace,principal.user_id,kind,data['created_at'],canonical(payload),previous,digest,signature('audit',digest)))


def verified_audit(db, business_id):
    db.row_factory = sqlite3.Row
    rows = db.execute('SELECT * FROM audit_events WHERE business_id=? ORDER BY event_id',(business_id,)).fetchall()
    previous = '0'*64
    results = []
    for row in rows:
        try:
            event = {key:row[key] for key in ('business_id','trace_id','actor_id','kind','created_at','previous_hash')}
            event['payload'] = json.loads(row['payload'])
            digest = hashlib.sha256(canonical(event).encode()).hexdigest()
            if row['previous_hash'] != previous or digest != row['event_hash'] or not hmac.compare_digest(row['signature'],signature('audit',digest)):
                fail(409,'AUDIT_INTEGRITY_FAILURE')
        except (ValueError,TypeError):
            fail(409,'AUDIT_INTEGRITY_FAILURE')
        previous = digest
        results.append(dict(event,event_id=row['event_id'],event_hash=digest))
    return results


def deny_event(db, principal, trace, code):
    # This runs only after a rejected operation rolled back; no raw user text/token.
    try:
        with transaction(db):
            current = recheck(db,principal)
            audit(db,current,trace,'DENIED',{'reason':code})
    except PolicyError as exc:
        if exc.status == 401:
            return  # No authenticated tenant to sign an audit for.
        fail(503,"DENIAL_AUDIT_UNAVAILABLE")
    except sqlite3.Error:
        fail(503,"DENIAL_AUDIT_UNAVAILABLE")


def original_dataset(db, business_id):
    try:
        return load_dataset(db,business_id)
    except KeyError:
        fail(404,'DATASET_NOT_FOUND')
    except (ValueError,TypeError):
        fail(409,'DATA_INTEGRITY_FAILURE')


def get_proposal(db, principal, proposal_id):
    db.row_factory = sqlite3.Row
    row = db.execute('SELECT * FROM proposals WHERE business_id=? AND proposal_id=?',(principal.business_id,proposal_id)).fetchone()
    if row is None:
        fail(404,'PROPOSAL_NOT_FOUND')
    return row


def verify_proposal(db, row, dataset=None):
    try:
        payload = json.loads(row['payload'])
        digest = hashlib.sha256(canonical(payload).encode()).hexdigest()
        if digest != row['action_hash'] or not hmac.compare_digest(row['signature'],signature('proposal',digest)):
            fail(409,'PROPOSAL_INTEGRITY_FAILURE')
        ds = dataset or original_dataset(db,row['business_id'])
        if fingerprint(ds)!=payload['dataset_sha256']:
            version=db.execute('SELECT payload FROM dataset_versions WHERE business_id=? AND dataset_sha256=?',(row['business_id'],payload['dataset_sha256'])).fetchone()
            if version is None:fail(409,'SOURCE_CHANGED')
            historical=validated(json.loads(version[0]))
            if fingerprint(historical)!=payload['dataset_sha256']:fail(409,'SOURCE_CHANGED')
            old=next((x for x in historical.invoices if x.invoice_id==row['invoice_id']),None)
            current=next((x for x in ds.invoices if x.invoice_id==row['invoice_id']),None)
            if old is None or current is None or fingerprint(old)!=fingerprint(current):fail(409,'SOURCE_CHANGED')
            ds=historical
        invoice = next((x for x in ds.invoices if x.invoice_id==row['invoice_id']),None)
        if invoice is None:
            fail(409,'SOURCE_CHANGED')
        expected = dict(proposal_id=row['proposal_id'],business_id=row['business_id'],invoice_id=invoice.invoice_id,
                        proposer_id=row['proposer_id'],vendor_id=invoice.vendor_id,amount_minor=invoice.amount_minor,currency=invoice.currency,
                        source_id=invoice.source_record_id,source_sha256=fingerprint(invoice),dataset_sha256=fingerprint(ds),version=1,
                        created_at=payload['created_at'],expires_at=payload['expires_at'])
        if payload != expected or type(payload['created_at']) is not int or type(payload['expires_at']) is not int or payload['expires_at']-payload['created_at']!=900:
            fail(409,'SOURCE_CHANGED')
        return payload
    except (ValueError,KeyError,TypeError):
        fail(409,'PROPOSAL_INTEGRITY_FAILURE')


def approval_values(row):
    return {key:row[key] for key in ('proposal_id','approver_id','decision','action_hash','decision_at')}


def verify_approval(db, proposal, payload):
    row = db.execute('SELECT * FROM approvals WHERE proposal_id=?',(proposal['proposal_id'],)).fetchone()
    if row is None:
        fail(409,'APPROVAL_REQUIRED')
    values = approval_values(row)
    if row['decision'] != 'approve' or row['action_hash'] != proposal['action_hash'] or row['approver_id']==proposal['proposer_id'] or not payload['created_at'] <= row['decision_at'] < payload['expires_at'] or not hmac.compare_digest(row['signature'],signature('approval',values)):
        fail(409,'APPROVAL_INTEGRITY_FAILURE')
    return row


def posting_values(row):
    return {key:row[key] for key in ('posting_id','proposal_id','business_id','invoice_id','amount_minor','created_at')}


def verify_posting(db, row, dataset):
    db.row_factory = sqlite3.Row
    proposal = db.execute('SELECT * FROM proposals WHERE proposal_id=? AND business_id=?',(row['proposal_id'],row['business_id'])).fetchone()
    if proposal is None or proposal['state']!='EXECUTED':
        fail(409,'LEDGER_INTEGRITY_FAILURE')
    payload=verify_proposal(db,proposal,dataset)
    approval=verify_approval(db,proposal,payload)
    if row['invoice_id']!=payload['invoice_id'] or row['amount_minor']!=payload['amount_minor'] or not approval['decision_at'] <= row['created_at'] < payload['expires_at'] or not hmac.compare_digest(row['signature'],signature('posting',posting_values(row))):
        fail(409,'LEDGER_INTEGRITY_FAILURE')
    entries=db.execute('SELECT account,delta_minor FROM ledger_entries WHERE posting_id=? ORDER BY account',(row['posting_id'],)).fetchall()
    if [(x[0],x[1]) for x in entries] != [('cash',-row['amount_minor']),('payables',row['amount_minor'])]:
        fail(409,'LEDGER_INTEGRITY_FAILURE')
    return payload


def runtime_dataset(db, business_id):
    ds = original_dataset(db,business_id)
    db.row_factory=sqlite3.Row
    postings=db.execute('SELECT * FROM postings WHERE business_id=? ORDER BY created_at,posting_id',(business_id,)).fetchall()
    raw=ds.model_dump(mode='json')
    for posting in postings:
        payload=verify_posting(db,posting,ds)
        invoice=next(x for x in ds.invoices if x.invoice_id==posting['invoice_id'])
        key=invoice_key(invoice)
        targets={x.invoice_id for x in ds.invoices if invoice_key(x)==key}
        for inv in raw['invoices']:
            if inv['invoice_id'] in targets:inv['status']='paid'
        raw['events']=[x for x in raw['events'] if not (x.get('invoice_id') in targets and x['status']=='scheduled')]
        day=datetime.fromtimestamp(posting['created_at'],timezone(timedelta(hours=6))).date()
        raw['as_of']=max(ds.as_of,day).isoformat()
        identity='posted-'+posting['posting_id']
        raw['events'].append(dict(source_record_id=identity,event_id=identity,direction='outflow',status='cleared',effective_on=max(ds.as_of,day).isoformat(),amount_minor=payload['amount_minor'],currency=ds.currency,invoice_id=invoice.invoice_id))
    try:
        return validated(raw)
    except ValueError:
        fail(409,'RUNTIME_DATA_INTEGRITY_FAILURE')


def check_invoice_policy(db, principal, invoice_id):
    ds=original_dataset(db,principal.business_id)
    invoice=next((x for x in ds.invoices if x.invoice_id==invoice_id),None)
    if invoice is None:fail(404,'INVOICE_NOT_FOUND')
    if invoice.status!='open' or db.execute('SELECT 1 FROM postings WHERE business_id=? AND invoice_id=?',(principal.business_id,invoice_id)).fetchone():
        fail(409,'INVOICE_ALREADY_PAID')
    flags=analyze_duplicates(ds)
    if any(invoice_id in flag['invoice_ids'] for flag in flags):fail(409,'DUPLICATE_INVOICE_BLOCKED')
    vendor=db.execute('SELECT enabled FROM trusted_vendors WHERE business_id=? AND vendor_id=?',(principal.business_id,invoice.vendor_id)).fetchone()
    if vendor is None or vendor[0]!=1:fail(409,'PAYEE_NOT_ALLOWLISTED')
    policy=db.execute('SELECT reserve_minor,payment_limit_minor FROM security_policies WHERE business_id=?',(principal.business_id,)).fetchone()
    if policy is None:fail(409,'POLICY_NOT_CONFIGURED')
    if invoice.amount_minor>policy[1]:fail(409,'PAYMENT_LIMIT_EXCEEDED')
    runtime=runtime_dataset(db,principal.business_id)
    if len(runtime.events)>=2000 and not any(x.invoice_id==invoice_id and x.status=='scheduled' for x in runtime.events):
        fail(409,'RUNTIME_EVENT_CAPACITY_EXCEEDED')
    cash=snapshot(runtime)['balance_minor']
    if cash-invoice.amount_minor<policy[0]:fail(409,'INSUFFICIENT_AVAILABLE_CASH')
    return ds,invoice,dict(available_minor=cash,after_payment_minor=cash-invoice.amount_minor,reserve_minor=policy[0],payment_limit_minor=policy[1])


def proposal_view(row):
    return dict(proposal_id=row['proposal_id'],state=row['state'],action_hash=row['action_hash'],details=json.loads(row['payload']),simulation_only=True)


def propose(db, principal, invoice_id, *, expected_runtime_sha=None, on_result=None):
    trace=str(uuid.uuid4())
    try:
        with transaction(db):
            current=recheck(db,principal)
            if current.role not in {'owner','approver','agent'}:fail(403,'PROPOSAL_ROLE_REQUIRED')
            verified_audit(db,current.business_id)
            if expected_runtime_sha is not None and current!=principal:fail(409,'AI_IDENTITY_CONTEXT_CHANGED')
            if expected_runtime_sha is not None and fingerprint(runtime_dataset(db,current.business_id))!=expected_runtime_sha:fail(409,'AI_FACTS_STALE_REFRESH_REQUIRED')
            ds,invoice,preview=check_invoice_policy(db,current,invoice_id)
            db.row_factory=sqlite3.Row
            old=db.execute("SELECT * FROM proposals WHERE business_id=? AND invoice_id=? AND state IN ('AWAITING_APPROVAL','APPROVED')",(current.business_id,invoice_id)).fetchone()
            if old:
                payload=verify_proposal(db,old,ds)
                if now()<payload['expires_at']:
                    result=dict(proposal_view(old),preview=preview)
                    if on_result is not None:on_result(result)
                    return result
                db.execute("UPDATE proposals SET state='EXPIRED' WHERE proposal_id=?",(old['proposal_id'],))
                audit(db,current,old['proposal_id'],'EXPIRED',{'action_hash':old['action_hash']})
            timestamp=now()
            payload=dict(proposal_id=trace,business_id=current.business_id,invoice_id=invoice.invoice_id,proposer_id=current.user_id,
                         vendor_id=invoice.vendor_id,amount_minor=invoice.amount_minor,currency=invoice.currency,source_id=invoice.source_record_id,
                         source_sha256=fingerprint(invoice),dataset_sha256=fingerprint(ds),version=1,created_at=timestamp,expires_at=timestamp+900)
            digest=hashlib.sha256(canonical(payload).encode()).hexdigest()
            db.execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?,?)',(trace,current.business_id,invoice_id,current.user_id,canonical(payload),digest,signature('proposal',digest),'AWAITING_APPROVAL'))
            audit(db,current,trace,'PROPOSED',{'action_hash':digest,'source_id':invoice.source_record_id,'dataset_sha256':fingerprint(ds),'policy_preview':preview})
            result=dict(proposal_view(get_proposal(db,current,trace)),preview=preview)
            if on_result is not None:on_result(result)
            return result
    except PolicyError as exc:
        deny_event(db,principal,trace,exc.code)
        raise
    except sqlite3.Error:
        deny_event(db,principal,trace,"STORAGE_FAILURE")
        raise


def execute_approved(db, principal, row, payload):
    """Server-only. Must share approval's locked transaction, with verified human decision."""
    if not db.in_transaction:raise RuntimeError('Execution requires locked approval transaction')
    principal=recheck(db,principal)
    if principal.role!='approver' or principal.user_id==row['proposer_id']:fail(403,'INDEPENDENT_HUMAN_EXECUTOR_REQUIRED')
    authoritative=verify_proposal(db,row)
    if payload!=authoritative:fail(409,'PROPOSAL_INTEGRITY_FAILURE')
    if row['state']!='APPROVED':fail(409,'APPROVED_STATE_REQUIRED')
    if now()>=payload['expires_at']:fail(409,'PROPOSAL_EXPIRED')
    approval=verify_approval(db,row,payload)
    if approval['approver_id']!=principal.user_id:fail(403,'APPROVAL_ACTOR_MISMATCH')
    _,_,preview=check_invoice_policy(db,principal,row['invoice_id'])
    if now()>=payload['expires_at']:fail(409,'PROPOSAL_EXPIRED')
    principal=recheck(db,principal)
    if principal.role!='approver':fail(403,'HUMAN_APPROVER_REQUIRED')
    values=dict(posting_id=str(uuid.uuid4()),proposal_id=row['proposal_id'],business_id=principal.business_id,invoice_id=row['invoice_id'],amount_minor=payload['amount_minor'],created_at=now())
    db.execute('INSERT INTO postings VALUES (?,?,?,?,?,?,?)',(*values.values(),signature('posting',values)))
    for account,delta in [('cash',-payload['amount_minor']),('payables',payload['amount_minor'])]:
        db.execute('INSERT INTO ledger_entries VALUES (?,?,?,?)',(str(uuid.uuid4()),values['posting_id'],account,delta))
    db.execute("UPDATE proposals SET state='EXECUTED' WHERE proposal_id=?",(row['proposal_id'],))
    audit(db,principal,row['proposal_id'],'EXECUTED',dict(posting_id=values['posting_id'],action_hash=row['action_hash'],cash_delta_minor=-payload['amount_minor'],after_payment_minor=preview['after_payment_minor']))
    # Validate the overlay before commit; any inconsistency rolls approval/posting/audit back.
    observed=snapshot(runtime_dataset(db,principal.business_id))['balance_minor']
    if observed!=preview['after_payment_minor']:fail(409,'LEDGER_RECONCILIATION_FAILURE')
    return dict(proposal_id=row['proposal_id'],state='EXECUTED',posting_id=values['posting_id'],action_hash=row['action_hash'],balance_minor=observed,simulation_only=True)


def decide(db, principal, proposal_id, request):
    try:
        with transaction(db):
            current=recheck(db,principal)
            if current.role!='approver':fail(403,'HUMAN_APPROVER_REQUIRED')
            row=get_proposal(db,current,proposal_id)
            payload=verify_proposal(db,row)
            if current.user_id==row['proposer_id']:fail(403,'INDEPENDENT_APPROVER_REQUIRED')
            if not hmac.compare_digest(request.proposal_hash,row['action_hash']):fail(409,'APPROVAL_HASH_MISMATCH')
            verified_audit(db,current.business_id)
            if row['state']=='EXECUTED':
                if request.decision!='approve':fail(409,'DECISION_ALREADY_FINAL')
                posting=db.execute('SELECT * FROM postings WHERE proposal_id=?',(proposal_id,)).fetchone()
                if posting is None:fail(409,'LEDGER_INTEGRITY_FAILURE')
                verify_posting(db,posting,original_dataset(db,current.business_id))
                audit(db,current,proposal_id,'IDEMPOTENT_REPLAY',{'posting_id':posting['posting_id'],'action_hash':row['action_hash']})
                return dict(proposal_id=proposal_id,state='EXECUTED',posting_id=posting['posting_id'],action_hash=row['action_hash'],balance_minor=snapshot(runtime_dataset(db,current.business_id))['balance_minor'],simulation_only=True)
            if row['state']!='AWAITING_APPROVAL':fail(409,'DECISION_ALREADY_FINAL')
            if now()>=payload['expires_at']:fail(409,'PROPOSAL_EXPIRED')
            values=dict(proposal_id=proposal_id,approver_id=current.user_id,decision=request.decision,action_hash=row['action_hash'],decision_at=now())
            db.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?)',(*values.values(),signature('approval',values)))
            new_state='APPROVED' if request.decision=='approve' else 'REJECTED'
            db.execute('UPDATE proposals SET state=? WHERE proposal_id=?',(new_state,proposal_id))
            audit(db,current,proposal_id,new_state,{'action_hash':row['action_hash'],'decision':request.decision})
            if new_state=='REJECTED':return proposal_view(get_proposal(db,current,proposal_id))
            return execute_approved(db,current,get_proposal(db,current,proposal_id),payload)
    except PolicyError as exc:
        deny_event(db,principal,proposal_id,exc.code)
        raise
    except sqlite3.Error:
        deny_event(db,principal,proposal_id,"STORAGE_FAILURE")
        raise
