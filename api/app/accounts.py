"""Self-service private financial record workspaces. Passwords are scrypt hashes; sessions are HttpOnly.
No email delivery or external identity service is required for this zero-budget application.
"""
from contextlib import closing
from datetime import datetime, timezone, timedelta, date
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field, field_validator, model_validator
from api.app import security as sec
from api.app.contracts import Contract, Currency
from api.app.currencies import scale
from api.app.services.finance import fingerprint
from api.app.routes import db_connection, principal

router = APIRouter(prefix='/api')
COOKIE = 'safeledger_session'
TEMPLATE = 'public-demo-v3'
PUBLIC_TEMPLATES = {'public-demo-v2', TEMPLATE}
HASH_LOCK = threading.BoundedSemaphore(1)
ACCOUNT_CAP = 5000
DUMMY_SALT = '0'*32


def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS auth_recovery(account_id TEXT PRIMARY KEY REFERENCES auth_accounts(account_id), code_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS auth_accounts(account_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS account_members(account_id TEXT NOT NULL REFERENCES auth_accounts(account_id), business_id TEXT NOT NULL, user_id TEXT UNIQUE NOT NULL REFERENCES security_users(user_id), PRIMARY KEY(account_id,business_id));
    CREATE TABLE IF NOT EXISTS workspace_meta(business_id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('personal','demo')));
    CREATE TABLE IF NOT EXISTS workspace_input_requests(business_id TEXT NOT NULL, request_id TEXT NOT NULL, body_sha256 TEXT NOT NULL, PRIMARY KEY(business_id,request_id));
    CREATE TABLE IF NOT EXISTS workspace_invites(code_hash TEXT PRIMARY KEY, business_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('approver','viewer')), created_by TEXT NOT NULL, expires_at INTEGER NOT NULL, used_by TEXT);
    CREATE TABLE IF NOT EXISTS auth_failures(scope TEXT NOT NULL, window INTEGER NOT NULL, count INTEGER NOT NULL, PRIMARY KEY(scope,window));
    ''')


def archive_legacy_examples(db):
    """Retain historical evidence, but withdraw all old example/legacy access once."""
    db.execute('CREATE TABLE IF NOT EXISTS product_migrations(name TEXT PRIMARY KEY)')
    db.commit()
    with sec.transaction(db):
        if db.execute("SELECT 1 FROM product_migrations WHERE name='real-records-v1'").fetchone():return
        db.execute("UPDATE security_users SET active=0 WHERE business_id IN (SELECT business_id FROM workspace_meta WHERE kind='demo') OR business_id IN ('public-demo-v2','public-demo-v3') OR user_id NOT IN (SELECT user_id FROM account_members)")
        db.execute("INSERT INTO product_migrations VALUES ('real-records-v1')")


def browser_origin(request):
    origin = request.headers.get('origin','')
    allowed = {o.strip().rstrip('/') for o in os.environ.get('SAFELEDGER_CORS_ORIGINS','').split(',') if o.strip()}
    allowed.update({'https://safeledger-ai.vercel.app','https://safeledger-ai.onrender.com'})
    if not os.environ.get('RENDER') and not os.environ.get('VERCEL'):
        allowed.update({'http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:4173','http://127.0.0.1:8000','http://localhost:8000','http://testserver'})
    if origin not in allowed or request.headers.get('X-SafeLedger-Client') != 'web':
        sec.fail(403,'UNTRUSTED_BROWSER_ORIGIN')


def rate(request, db, kind, claimed_limit, edge_limit, global_limit):
    """Per-minute floods: best-effort end user, infrastructure-observed edge address, and a global ceiling."""
    claimed, edge = sec.client_keys(request)
    sec.budgets(db,[('account:'+kind+':'+claimed,claimed_limit),('account:'+kind+'-edge:'+edge,edge_limit),('account:'+kind+'-all',global_limit)])
    return edge


FAILURE_WINDOW_MINUTES = 15


def failure_scopes(kind, name, edge, per_pair, per_name, per_edge):
    digest = hashlib.sha256(name.encode()).hexdigest()[:32]
    return [(kind+'-name-edge:'+digest+':'+edge,per_pair),(kind+'-name:'+digest,per_name),(kind+'-edge:'+edge,per_edge)]


def locked_out(db, scopes):
    """Failed-attempt lockout over a rolling window. Cheap: it runs before any password hashing."""
    since = sec.now()//60 - FAILURE_WINDOW_MINUTES
    for scope, limit in scopes:
        total = db.execute('SELECT COALESCE(SUM(count),0) FROM auth_failures WHERE scope=? AND window>?',(scope,since)).fetchone()[0]
        if total >= limit:sec.fail(429,'TOO_MANY_FAILED_ATTEMPTS')


def record_failure(db, scopes):
    window = sec.now()//60
    with sec.transaction(db):
        db.execute('DELETE FROM auth_failures WHERE window<?',(window-60,))
        for scope, _ in scopes:
            db.execute('INSERT INTO auth_failures VALUES (?,?,1) ON CONFLICT(scope,window) DO UPDATE SET count=count+1',(scope,window))


COMMON_PASSWORDS = {
    'password','password1','password12','password123','password1234','passw0rd','p@ssw0rd','p@ssword','12345678','123456789','1234567890','12341234','123123123','87654321','987654321','11111111','00000000','12121212',
    'qwertyui','qwerty123','qwertyuiop','qwerty12','1q2w3e4r','1qaz2wsx','1q2w3e4r5t','abc12345','abcd1234','abcdefgh','abcdefg1','iloveyou','iloveyou1','letmein1','letmein123','welcome1','welcome123','admin123','administrator','changeme','changeme123',
    'football','baseball','monkey123','dragon123','superman','trustno1','sunshine','princess','starwars','whatever','master123','bangladesh','bangladesh1','dhaka1234','safeledger','safeledger1','safeledger123','capzoryx','business1','company123','test1234','testtest','testing123','default123','secret123','access123','login123','hello123','hellohello','zaq12wsx','asdfghjk','asdf1234','zxcvbnm1','passpass',
}


def reject_weak_password(password, username=''):
    folded = password.strip().lower()
    if folded in COMMON_PASSWORDS or folded == username.lower() or len(set(folded)) < 4:
        raise ValueError('Choose a less common password that is not your username')
    return password


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    if not HASH_LOCK.acquire(timeout=8):sec.fail(429,'PLEASE_TRY_AGAIN')
    try:
        digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=32768,r=8,p=3,maxmem=64*1024*1024,dklen=32).hex()
    finally:HASH_LOCK.release()
    return 'scrypt-v1$'+salt+'$'+digest


def issue(db, user_id):
    token=secrets.token_urlsafe(32)
    db.execute('INSERT INTO security_sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user_id,sec.now()+86400))
    return token


def set_cookie(response, token):
    secure = bool(os.environ.get('RENDER') or os.environ.get('VERCEL') or os.environ.get('SAFELEDGER_COOKIE_SECURE')=='1')
    response.set_cookie(COOKIE,token,max_age=86400,httponly=True,secure=secure,samesite='lax',path='/')


def identity(db, actor):
    row=db.execute("SELECT w.name,w.kind,a.username FROM (SELECT ? AS business_id,? AS user_id) p LEFT JOIN workspace_meta w ON w.business_id=p.business_id LEFT JOIN account_members m ON m.user_id=p.user_id LEFT JOIN auth_accounts a ON a.account_id=m.account_id",(actor.business_id,actor.user_id)).fetchone()
    return dict(workspace_name=row[0] if row[0] else ('Example workspace' if actor.business_id in PUBLIC_TEMPLATES else 'Existing workspace'), workspace_kind=row[1] or 'demo',user_id=actor.user_id,business_id=actor.business_id,role=actor.role,username=row[2],guest=actor.business_id in PUBLIC_TEMPLATES,simulation_only=True)


class Credentials(Contract):
    model_config = {"extra":"forbid", "str_strip_whitespace":False}
    username: str = Field(min_length=3,max_length=32)
    password: str = Field(min_length=8,max_length=128,strict=True)
    @field_validator('password',mode='before')
    @classmethod
    def preserve_password(cls,value):
        # Credentials are exact strings: never silently trim user passwords.
        if not isinstance(value,str):raise ValueError('Expected password text')
        return value

    @field_validator('username')
    @classmethod
    def normalize(cls,value):
        value=value.lower().strip()
        if not re.fullmatch(r'[a-z0-9_]{3,32}',value):raise ValueError('Use 3–32 letters, numbers or underscores')
        return value


class SignupCredentials(Credentials):
    currency: Currency = 'BDT'

    @model_validator(mode='after')
    def not_weak(self):
        reject_weak_password(self.password,self.username)
        return self


@router.post('/auth/signup',status_code=201)
def signup(body:SignupCredentials, request:Request, response:Response, db=Depends(db_connection)):
    browser_origin(request);rate(request,db,'signup',4,20,60)
    hashed=password_hash(body.password)
    account=uuid.uuid4().hex;business='workspace-'+uuid.uuid4().hex;user='user-'+uuid.uuid4().hex;code=secrets.token_urlsafe(24)
    try:
        with sec.transaction(db):
            if db.execute('SELECT count(*) FROM auth_accounts').fetchone()[0]>=ACCOUNT_CAP:sec.fail(503,'ACCOUNT_CAPACITY_REACHED')
            db.execute('INSERT INTO auth_accounts VALUES (?,?,?,?)',(account,body.username,hashed,sec.now()))
            db.execute("INSERT INTO security_users VALUES (?,?, 'owner',1)",(user,business))
            db.execute('INSERT INTO account_members VALUES (?,?,?)',(account,business,user))
            create_workspace_data(db,business,'personal','My workspace',body.currency)
            db.execute('INSERT INTO auth_recovery VALUES (?,?)',(account,hashlib.sha256(code.encode()).hexdigest()))
            token=issue(db,user)
            sec.audit(db,sec.authenticate(db,token),'account-'+account,'WORKSPACE_CREATED',{'sample_data':False})
    except sqlite3.IntegrityError:sec.fail(409,'USERNAME_UNAVAILABLE')
    set_cookie(response,token)
    return dict(identity(db,sec.authenticate(db,token)),recovery_code=code)


@router.post('/auth/login')
def login(body:Credentials,request:Request,response:Response,db=Depends(db_connection)):
    browser_origin(request);edge=rate(request,db,'login',12,120,300)
    scopes=failure_scopes('login',body.username,edge,8,40,40)
    locked_out(db,scopes)
    row=db.execute('SELECT account_id,password_hash FROM auth_accounts WHERE username=?',(body.username,)).fetchone()
    stored=row[1] if row else 'scrypt-v1$'+DUMMY_SALT+'$'+'0'*64
    computed=password_hash(body.password,stored.split('$')[1])
    if not row or not hmac.compare_digest(computed,stored):
        record_failure(db,scopes)
        sec.fail(401,'INVALID_USERNAME_OR_PASSWORD')
    with sec.transaction(db):
        sec.prune_expired_sessions(db)
        member=personal_member(db,row[0])
        token=issue(db,member)
        code=None
        if not db.execute('SELECT 1 FROM auth_recovery WHERE account_id=?',(row[0],)).fetchone():
            code=secrets.token_urlsafe(24)
            db.execute('INSERT INTO auth_recovery VALUES (?,?)',(row[0],hashlib.sha256(code.encode()).hexdigest()))
    set_cookie(response,token)
    result=identity(db,sec.authenticate(db,token))
    if code:result['recovery_code']=code
    return result


@router.post('/auth/guest')
def guest(request:Request):
    browser_origin(request)
    sec.fail(410,'EXAMPLE_ACCESS_RETIRED')


@router.post('/auth/logout')
def logout(request:Request,response:Response,db=Depends(db_connection)):
    browser_origin(request)
    token=request.cookies.get(COOKIE)
    if token:
        with db:db.execute('DELETE FROM security_sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie(COOKIE,path='/');return {'simulation_only':True}


@router.get('/account/workspaces')
def workspaces(actor=Depends(principal),db=Depends(db_connection)):
    member=db.execute('SELECT account_id FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone()
    rows=db.execute("SELECT m.business_id,u.role,COALESCE(w.name,'Existing workspace'),COALESCE(w.kind,'demo') FROM account_members m JOIN security_users u ON u.user_id=m.user_id LEFT JOIN workspace_meta w ON w.business_id=m.business_id WHERE m.account_id=? AND u.active=1 AND w.kind='personal'",(member[0],)).fetchall() if member else []
    return {'workspaces':[{'business_id':r[0],'role':r[1],'name':r[2],'kind':r[3]} for r in rows],'simulation_only':True}


class WorkspaceChoice(Contract):
    business_id:str=Field(min_length=1,max_length=80)


@router.post('/account/switch')
def switch(body:WorkspaceChoice,response:Response,actor=Depends(principal),db=Depends(db_connection)):
    member=db.execute('SELECT account_id FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone()
    if not member:sec.fail(403,'ACCOUNT_REQUIRED')
    user=db.execute('SELECT m.user_id FROM account_members m JOIN security_users u ON u.user_id=m.user_id WHERE m.account_id=? AND m.business_id=? AND u.active=1 AND EXISTS (SELECT 1 FROM workspace_meta w WHERE w.business_id=m.business_id AND w.kind="personal")',(member[0],body.business_id)).fetchone()
    if not user:sec.fail(403,'WORKSPACE_ACCESS_DENIED')
    with db:token=issue(db,user[0])
    set_cookie(response,token);return identity(db,sec.authenticate(db,token))


class InviteRequest(Contract):
    role:str=Field(pattern='^(approver|viewer)$',default='approver')


@router.post('/account/invitations',status_code=201)
def invite(body:InviteRequest,actor=Depends(principal),db=Depends(db_connection)):
    if actor.role!='owner' or not db.execute('SELECT 1 FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone():sec.fail(403,'WORKSPACE_OWNER_REQUIRED')
    sec.budget(db,'invite:'+actor.user_id,5)
    code=secrets.token_urlsafe(24)
    with db:
        db.execute('INSERT INTO workspace_invites VALUES (?,?,?,?,?,NULL)',(hashlib.sha256(code.encode()).hexdigest(),actor.business_id,body.role,actor.user_id,sec.now()+3600))
        sec.audit(db,actor,'invite-'+uuid.uuid4().hex,'INVITATION_CREATED',{'role':body.role,'expires_in_seconds':3600})
    return {'code':code,'role':body.role,'expires_in_seconds':3600,'simulation_only':True}


class AcceptRequest(Contract):
    code:str=Field(min_length=20,max_length=100)


@router.post('/account/join')
def join(body:AcceptRequest,response:Response,actor=Depends(principal),db=Depends(db_connection)):
    member=db.execute('SELECT account_id FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone()
    if not member:sec.fail(403,'ACCOUNT_REQUIRED')
    sec.budget(db,'join:'+actor.user_id,10)
    with sec.transaction(db):
        invitation=db.execute('SELECT business_id,role,created_by FROM workspace_invites WHERE code_hash=? AND expires_at>? AND used_by IS NULL',(hashlib.sha256(body.code.encode()).hexdigest(),sec.now())).fetchone()
        if not invitation or not db.execute("SELECT 1 FROM workspace_meta WHERE business_id=? AND kind='personal'",(invitation[0],)).fetchone():sec.fail(409,'INVITATION_INVALID_OR_EXPIRED')
        if db.execute('SELECT 1 FROM account_members WHERE account_id=? AND business_id=?',(member[0],invitation[0])).fetchone():sec.fail(409,'ALREADY_A_WORKSPACE_MEMBER')
        creator=db.execute('SELECT role,active FROM security_users WHERE user_id=?',(invitation[2],)).fetchone()
        if not creator or tuple(creator)!=('owner',1):sec.fail(409,'INVITATION_INVALID_OR_EXPIRED')
        user='user-'+uuid.uuid4().hex
        db.execute('INSERT INTO security_users VALUES (?,?,?,1)',(user,invitation[0],invitation[1]))
        db.execute('INSERT INTO account_members VALUES (?,?,?)',(member[0],invitation[0],user))
        db.execute('UPDATE workspace_invites SET used_by=? WHERE code_hash=?',(member[0],hashlib.sha256(body.code.encode()).hexdigest()))
        token=issue(db,user)
        sec.audit(db,sec.authenticate(db,token),'join-'+uuid.uuid4().hex,'WORKSPACE_JOINED',{'role':invitation[1],'invited_by':invitation[2]})
    set_cookie(response,token);return identity(db,sec.authenticate(db,token))


def today_bd():
    return datetime.now(timezone(timedelta(hours=6))).date()


def create_workspace_data(db,business,kind,name,currency="BDT"):
    from api.app.services.finance import Dataset
    if kind!='personal':sec.fail(422,'PERSONAL_WORKSPACE_REQUIRED')
    ds=Dataset(opening_source_id='opening-zero',opening_on=date(1970,1,1),as_of=today_bd(),opening_balance_minor=0,currency=currency,invoices=[],events=[])
    db.execute('INSERT INTO financial_datasets VALUES (?,?,?)',(business,fingerprint(ds),ds.model_dump_json()))
    db.execute('INSERT INTO security_policies VALUES (?,?,?)',(business,0,100000 * scale(currency)))
    db.execute('INSERT INTO workspace_meta VALUES (?,?,?)',(business,name,'personal'))


def personal_member(db,account):
    row=db.execute("SELECT m.user_id FROM account_members m JOIN security_users u ON u.user_id=m.user_id JOIN workspace_meta w ON w.business_id=m.business_id WHERE m.account_id=? AND u.active=1 AND w.kind='personal' ORDER BY CASE u.role WHEN 'owner' THEN 0 ELSE 1 END,m.rowid LIMIT 1",(account,)).fetchone()
    if row:return row[0]
    business='workspace-'+uuid.uuid4().hex;user='user-'+uuid.uuid4().hex
    db.execute("INSERT INTO security_users VALUES (?,?,'owner',1)",(user,business))
    db.execute('INSERT INTO account_members VALUES (?,?,?)',(account,business,user))
    create_workspace_data(db,business,'personal','My workspace')
    token=issue(db,user)
    sec.audit(db,sec.authenticate(db,token),'workspace-'+business,'WORKSPACE_CREATED',{'sample_data':False,'reason':'personal_records'})
    return user


class NewWorkspace(Contract):
    currency: Currency = 'BDT'
    kind: str = Field(pattern='^personal$',default='personal')
    name: str = Field(min_length=1,max_length=60)


@router.post('/account/workspaces',status_code=201)
def new_workspace(body:NewWorkspace,response:Response,actor=Depends(principal),db=Depends(db_connection)):
    member=db.execute('SELECT account_id FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone()
    if not member:sec.fail(403,'ACCOUNT_REQUIRED')
    sec.budget(db,'new-workspace:'+member[0],3)
    with sec.transaction(db):
        if db.execute('SELECT count(*) FROM account_members WHERE account_id=?',(member[0],)).fetchone()[0]>=20:sec.fail(409,'WORKSPACE_LIMIT_REACHED')
        business='workspace-'+uuid.uuid4().hex;user='user-'+uuid.uuid4().hex
        db.execute("INSERT INTO security_users VALUES (?,?,'owner',1)",(user,business))
        db.execute('INSERT INTO account_members VALUES (?,?,?)',(member[0],business,user))
        create_workspace_data(db,business,body.kind,body.name,body.currency)
        token=issue(db,user)
        sec.audit(db,sec.authenticate(db,token),'workspace-'+business,'WORKSPACE_CREATED',{'sample_data':False})
    set_cookie(response,token)
    return identity(db,sec.authenticate(db,token))


class RecoveryRequest(Credentials):
    recovery_code: str = Field(min_length=20,max_length=100)

    @model_validator(mode='after')
    def not_weak(self):
        reject_weak_password(self.password,self.username)
        return self


@router.post('/auth/recover')
def recover(body:RecoveryRequest,request:Request,response:Response,db=Depends(db_connection)):
    browser_origin(request);edge=rate(request,db,'recover',4,20,40)
    scopes=failure_scopes('recover',body.username,edge,5,20,30)
    locked_out(db,scopes)
    row=db.execute('SELECT a.account_id,r.code_hash FROM auth_accounts a JOIN auth_recovery r ON r.account_id=a.account_id WHERE a.username=?',(body.username,)).fetchone()
    supplied=hashlib.sha256(body.recovery_code.encode()).hexdigest()
    if row is None or not hmac.compare_digest(supplied,row[1]):
        record_failure(db,scopes)
        sec.fail(401,'INVALID_RECOVERY_DETAILS')
    hashed=password_hash(body.password);code=secrets.token_urlsafe(24)
    with sec.transaction(db):
        current=db.execute('SELECT code_hash FROM auth_recovery WHERE account_id=?',(row[0],)).fetchone()
        if not current or not hmac.compare_digest(supplied,current[0]):sec.fail(401,'INVALID_RECOVERY_DETAILS')
        db.execute('UPDATE auth_accounts SET password_hash=? WHERE account_id=?',(hashed,row[0]))
        db.execute('UPDATE auth_recovery SET code_hash=? WHERE account_id=?',(hashlib.sha256(code.encode()).hexdigest(),row[0]))
        db.execute('DELETE FROM security_sessions WHERE user_id IN (SELECT user_id FROM account_members WHERE account_id=?)',(row[0],))
        user=personal_member(db,row[0]);token=issue(db,user)
        actor=sec.authenticate(db,token);sec.verified_audit(db,actor.business_id)
        sec.audit(db,actor,'recovery-'+uuid.uuid4().hex,'ACCOUNT_RECOVERED',{'sessions_revoked':True})
    set_cookie(response,token)
    return dict(identity(db,sec.authenticate(db,token)),recovery_code=code)
