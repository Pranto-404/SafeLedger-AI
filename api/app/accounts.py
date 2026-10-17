"""Self-service synthetic workspaces. Passwords are scrypt hashes; sessions are HttpOnly.
No email delivery or external identity service is required for this zero-budget demo.
"""
from contextlib import closing
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
from pydantic import Field, field_validator
from api.app import security as sec
from api.app.contracts import Contract
from api.app.services.intake import parse_json
from api.app.services.storage import store_dataset
from api.app.services.finance import fingerprint
from api.app.routes import db_connection, principal

router = APIRouter(prefix='/api')
COOKIE = 'safeledger_session'
TEMPLATE = 'public-demo-v3'
PUBLIC_TEMPLATES = {'public-demo-v2', TEMPLATE}
HASH_LOCK = threading.BoundedSemaphore(1)
DUMMY_SALT = '0'*32


def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS auth_accounts(account_id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS account_members(account_id TEXT NOT NULL REFERENCES auth_accounts(account_id), business_id TEXT NOT NULL, user_id TEXT UNIQUE NOT NULL REFERENCES security_users(user_id), PRIMARY KEY(account_id,business_id));
    CREATE TABLE IF NOT EXISTS workspace_invites(code_hash TEXT PRIMARY KEY, business_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('approver','viewer')), created_by TEXT NOT NULL, expires_at INTEGER NOT NULL, used_by TEXT);
    ''')


def prepare_template(db):
    if not db.execute('SELECT 1 FROM financial_datasets WHERE business_id=?', (TEMPLATE,)).fetchone():
        ds = parse_json((Path(__file__).resolve().parents[2]/'data/fixtures/duplicate_exact.json').read_bytes())
        previous=db.execute('SELECT dataset_sha256 FROM financial_datasets WHERE business_id=?',('public-demo-v2',)).fetchone()
        if previous and previous[0]==fingerprint(ds):
            with db:
                db.execute('INSERT OR IGNORE INTO financial_datasets SELECT ?,dataset_sha256,payload FROM financial_datasets WHERE business_id=?',(TEMPLATE,'public-demo-v2'))
                db.execute('INSERT OR IGNORE INTO source_records SELECT ?,source_record_id,kind,record_id,record_sha256,payload FROM source_records WHERE business_id=?',(TEMPLATE,'public-demo-v2'))
        else:
            try:store_dataset(db, TEMPLATE, ds)
            except sqlite3.IntegrityError:pass  # Concurrent startup may have created this immutable template.
    with db:
        db.execute('INSERT OR IGNORE INTO security_policies VALUES (?,?,?)', (TEMPLATE,1000000,10000000))
        db.execute("INSERT OR IGNORE INTO trusted_vendors SELECT ?,json_extract(payload,'$.vendor_id'),1 FROM source_records WHERE business_id=? AND kind='invoice'", (TEMPLATE,TEMPLATE))
        db.execute("INSERT OR IGNORE INTO security_users VALUES ('public-visitor-v3',?,'viewer',1)", (TEMPLATE,))


def browser_origin(request):
    origin = request.headers.get('origin','')
    allowed = {o.strip().rstrip('/') for o in os.environ.get('SAFELEDGER_CORS_ORIGINS','').split(',') if o.strip()}
    allowed.update({'https://safeledger-ai.vercel.app','https://safeledger-ai.onrender.com'})
    if not os.environ.get('RENDER') and not os.environ.get('VERCEL'):
        allowed.update({'http://127.0.0.1:5173','http://localhost:5173','http://127.0.0.1:4173','http://127.0.0.1:8000','http://localhost:8000','http://testserver'})
    if origin not in allowed or request.headers.get('X-SafeLedger-Client') != 'web':
        sec.fail(403,'UNTRUSTED_BROWSER_ORIGIN')


def rate(request, db, kind, limit):
    # Use the transport peer, not a client-supplied forwarding header.
    peer = request.client.host if request.client else 'unknown'
    sec.budget(db, 'account:'+kind+':'+hashlib.sha256(peer.encode()).hexdigest(), limit)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    if not HASH_LOCK.acquire(timeout=2):sec.fail(429,'PLEASE_TRY_AGAIN')
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
    row=db.execute('SELECT a.username FROM auth_accounts a JOIN account_members m ON m.account_id=a.account_id WHERE m.user_id=?',(actor.user_id,)).fetchone()
    return dict(user_id=actor.user_id,business_id=actor.business_id,role=actor.role,username=row[0] if row else None,guest=actor.business_id in PUBLIC_TEMPLATES,simulation_only=True)


class Credentials(Contract):
    username: str = Field(min_length=3,max_length=32)
    password: str = Field(min_length=15,max_length=128)
    @field_validator('username')
    @classmethod
    def normalize(cls,value):
        value=value.lower().strip()
        if not re.fullmatch(r'[a-z0-9_]{3,32}',value):raise ValueError('Use 3–32 letters, numbers or underscores')
        return value


@router.post('/auth/signup',status_code=201)
def signup(body:Credentials, request:Request, response:Response, db=Depends(db_connection)):
    browser_origin(request);rate(request,db,'signup',4)
    if db.execute('SELECT count(*) FROM auth_accounts').fetchone()[0]>=1000:sec.fail(503,'DEMO_ACCOUNT_CAPACITY_REACHED')
    hashed=password_hash(body.password)
    account=uuid.uuid4().hex;business='workspace-'+uuid.uuid4().hex;user='user-'+uuid.uuid4().hex
    try:
        with sec.transaction(db):
            db.execute('INSERT INTO auth_accounts VALUES (?,?,?,?)',(account,body.username,hashed,sec.now()))
            db.execute("INSERT INTO security_users VALUES (?,?, 'owner',1)",(user,business))
            db.execute('INSERT INTO account_members VALUES (?,?,?)',(account,business,user))
            db.execute('INSERT INTO financial_datasets SELECT ?,dataset_sha256,payload FROM financial_datasets WHERE business_id=?',(business,TEMPLATE))
            db.execute('INSERT INTO source_records SELECT ?,source_record_id,kind,record_id,record_sha256,payload FROM source_records WHERE business_id=?',(business,TEMPLATE))
            db.execute('INSERT INTO security_policies SELECT ?,reserve_minor,payment_limit_minor FROM security_policies WHERE business_id=?',(business,TEMPLATE))
            db.execute('INSERT INTO trusted_vendors SELECT ?,vendor_id,enabled FROM trusted_vendors WHERE business_id=?',(business,TEMPLATE))
            token=issue(db,user)
            sec.audit(db,sec.authenticate(db,token),'account-'+account,'WORKSPACE_CREATED',{'sample_data':True})
    except sqlite3.IntegrityError:sec.fail(409,'USERNAME_UNAVAILABLE')
    set_cookie(response,token)
    return identity(db,sec.authenticate(db,token))


@router.post('/auth/login')
def login(body:Credentials,request:Request,response:Response,db=Depends(db_connection)):
    browser_origin(request);rate(request,db,'login',8)
    sec.budget(db,'login-name:'+hashlib.sha256(body.username.encode()).hexdigest(),8)
    row=db.execute('SELECT account_id,password_hash FROM auth_accounts WHERE username=?',(body.username,)).fetchone()
    stored=row[1] if row else 'scrypt-v1$'+DUMMY_SALT+'$'+'0'*64
    computed=password_hash(body.password,stored.split('$')[1])
    if not row or not hmac.compare_digest(computed,stored):sec.fail(401,'INVALID_USERNAME_OR_PASSWORD')
    member=db.execute("SELECT m.user_id FROM account_members m JOIN security_users u ON m.user_id=u.user_id WHERE m.account_id=? AND u.active=1 ORDER BY CASE u.role WHEN 'owner' THEN 0 ELSE 1 END,m.rowid LIMIT 1",(row[0],)).fetchone()
    if not member:sec.fail(403,'ACCOUNT_UNAVAILABLE')
    with db:token=issue(db,member[0])
    set_cookie(response,token);return identity(db,sec.authenticate(db,token))


@router.post('/auth/guest',status_code=201)
def guest(request:Request,response:Response,db=Depends(db_connection)):
    browser_origin(request);rate(request,db,'guest',20)
    with db:
        db.execute('DELETE FROM security_sessions WHERE user_id=? AND expires_at<?',('public-visitor-v3',sec.now()))
        token=issue(db,'public-visitor-v3')
    set_cookie(response,token);return identity(db,sec.authenticate(db,token))


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
    rows=db.execute('SELECT m.business_id,u.role FROM account_members m JOIN security_users u ON u.user_id=m.user_id WHERE m.account_id=? AND u.active=1',(member[0],)).fetchall() if member else []
    return {'workspaces':[{'business_id':r[0],'role':r[1]} for r in rows],'simulation_only':True}


class WorkspaceChoice(Contract):
    business_id:str=Field(min_length=1,max_length=80)


@router.post('/account/switch')
def switch(body:WorkspaceChoice,response:Response,actor=Depends(principal),db=Depends(db_connection)):
    member=db.execute('SELECT account_id FROM account_members WHERE user_id=?',(actor.user_id,)).fetchone()
    if not member:sec.fail(403,'ACCOUNT_REQUIRED')
    user=db.execute('SELECT m.user_id FROM account_members m JOIN security_users u ON u.user_id=m.user_id WHERE m.account_id=? AND m.business_id=? AND u.active=1',(member[0],body.business_id)).fetchone()
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
        if not invitation:sec.fail(409,'INVITATION_INVALID_OR_EXPIRED')
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
