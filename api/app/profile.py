"""Account settings: profile and photo, password change, email verification, two-factor sign-in and email password reset."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import uuid
from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field, StrictBool
from api.app import mailer, mfa, security as sec
from api.app.accounts import (browser_origin, complete_login, failure_scopes, locked_out, normalize_email, password_hash, rate,
                              record_failure, reject_weak_password)
from api.app.contracts import Contract
from api.app.ratelimit import limiter
from api.app.routes import db_connection, principal

router = APIRouter(prefix='/api')
PHOTO = re.compile(r'^data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/]+={0,2})$')
CODE_MINUTES = 10


def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS account_profiles(account_id TEXT PRIMARY KEY, display_name TEXT NOT NULL DEFAULT '', photo TEXT, smart_assist INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS account_emails(account_id TEXT PRIMARY KEY, email TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0);
    CREATE UNIQUE INDEX IF NOT EXISTS account_emails_verified ON account_emails(email) WHERE verified=1;
    CREATE TABLE IF NOT EXISTS email_codes(code_id TEXT PRIMARY KEY, purpose TEXT NOT NULL, subject TEXT NOT NULL, code_hash TEXT NOT NULL, expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, used INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS account_mfa(account_id TEXT PRIMARY KEY, secret_blob TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 0, last_step INTEGER NOT NULL DEFAULT 0, backup_hashes TEXT NOT NULL DEFAULT '[]');
    CREATE TABLE IF NOT EXISTS mfa_challenges(token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, expires_at INTEGER NOT NULL);
    ''')
    have = {r[1] for r in db.execute('PRAGMA table_info(account_profiles)').fetchall()}
    if 'display_currency' not in have:db.execute("ALTER TABLE account_profiles ADD COLUMN display_currency TEXT NOT NULL DEFAULT 'USD'")
    if 'language' not in have:db.execute("ALTER TABLE account_profiles ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")


class Exact(Contract):
    model_config = {'extra': 'forbid', 'str_strip_whitespace': False}


def account_of(db, actor):
    row = db.execute('SELECT account_id FROM account_members WHERE user_id=?', (actor.user_id,)).fetchone()
    if not row:sec.fail(403, 'ACCOUNT_REQUIRED')
    return row[0]


def username_of(db, account):
    return db.execute('SELECT username FROM auth_accounts WHERE account_id=?', (account,)).fetchone()[0]


def check_password(db, account, password):
    scope = 'confirm-password:' + account
    if limiter.failure_total(scope) >= 5:sec.fail(429, 'TOO_MANY_FAILED_ATTEMPTS')
    row = db.execute('SELECT password_hash FROM auth_accounts WHERE account_id=?', (account,)).fetchone()
    stored = row[0]
    computed = password_hash(password, stored.split('$')[1])
    if not hmac.compare_digest(computed, stored):
        limiter.add_failure([scope])
        sec.fail(401, 'CURRENT_PASSWORD_INCORRECT')


# ---------- email codes ----------
def _code_hash(purpose, subject, code):
    key = bytes.fromhex(os.environ.get('SAFELEDGER_SIGNING_KEY', '0' * 64))
    return hmac.new(key, f'{purpose}:{subject}:{code}'.encode(), hashlib.sha256).hexdigest()


def issue_code(db, purpose, subject):
    code = '%06d' % secrets.randbelow(10**6)
    with sec.transaction(db):
        db.execute('DELETE FROM email_codes WHERE purpose=? AND subject=?', (purpose, subject))
        db.execute('DELETE FROM email_codes WHERE expires_at<?', (sec.now() - 3600,))
        db.execute('INSERT INTO email_codes VALUES (?,?,?,?,?,0,0,?)', (uuid.uuid4().hex, purpose, subject, _code_hash(purpose, subject, code), sec.now() + CODE_MINUTES * 60, sec.now()))
    return code


def check_code(db, purpose, subject, code):
    code = ''.join(ch for ch in str(code) if ch.isdigit())
    if len(code) != 6:return False
    with sec.transaction(db):
        row = db.execute('SELECT code_id,code_hash,expires_at,attempts FROM email_codes WHERE purpose=? AND subject=? AND used=0 ORDER BY created_at DESC LIMIT 1', (purpose, subject)).fetchone()
        if not row or row[2] < sec.now() or row[3] >= 5:return False
        ok = hmac.compare_digest(row[1], _code_hash(purpose, subject, code))
        db.execute('UPDATE email_codes SET used=1 WHERE code_id=?' if ok else 'UPDATE email_codes SET attempts=attempts+1 WHERE code_id=?', (row[0],))
    return ok


# ---------- profile ----------
@router.get('/auth/capabilities')
def capabilities():
    return dict(email_codes=mailer.configured(), cloud_assist=bool(os.environ.get('SAFELEDGER_LLM_API_KEY')), simulation_only=True)


@router.get('/account/profile')
def get_profile(actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    row = db.execute("SELECT a.username,COALESCE(p.display_name,''),p.photo,COALESCE(p.smart_assist,1),COALESCE(p.display_currency,'USD'),COALESCE(p.language,'en') FROM auth_accounts a LEFT JOIN account_profiles p ON p.account_id=a.account_id WHERE a.account_id=?", (account,)).fetchone()
    email = db.execute('SELECT email,verified FROM account_emails WHERE account_id=?', (account,)).fetchone()
    enabled = db.execute('SELECT enabled FROM account_mfa WHERE account_id=?', (account,)).fetchone()
    return dict(username=row[0], display_name=row[1], photo=row[2], smart_assist=bool(row[3]), display_currency=row[4], language=row[5], email=email[0] if email else None,
                email_verified=bool(email and email[1]), two_factor=bool(enabled and enabled[0]), email_service=mailer.configured(), simulation_only=True)


class ProfileUpdate(Contract):
    display_name: str | None = Field(default=None, max_length=60)
    smart_assist: StrictBool | None = None
    display_currency: str | None = Field(default=None, pattern='^[A-Z]{3}$')
    language: str | None = Field(default=None, max_length=8)


@router.post('/account/profile')
def update_profile(body: ProfileUpdate, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    with sec.transaction(db):
        db.execute('INSERT OR IGNORE INTO account_profiles(account_id) VALUES (?)', (account,))
        if body.display_name is not None:
            name = ' '.join(body.display_name.split())
            if any(ord(ch) < 32 for ch in name):sec.fail(422, 'INVALID_NAME')
            db.execute('UPDATE account_profiles SET display_name=? WHERE account_id=?', (name, account))
        if body.smart_assist is not None:
            db.execute('UPDATE account_profiles SET smart_assist=? WHERE account_id=?', (int(body.smart_assist), account))
        if body.display_currency is not None:
            db.execute('UPDATE account_profiles SET display_currency=? WHERE account_id=?', (body.display_currency, account))
        if body.language is not None:
            from api.app.i18n import LANGUAGES
            if body.language not in LANGUAGES:sec.fail(422, 'LANGUAGE_NOT_SUPPORTED')
            db.execute('UPDATE account_profiles SET language=? WHERE account_id=?', (body.language, account))
    return dict(simulation_only=True)


class PhotoUpload(Exact):
    image: str = Field(min_length=40, max_length=240000)


@router.post('/account/photo')
def set_photo(body: PhotoUpload, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    match = PHOTO.fullmatch(body.image)
    if not match:sec.fail(422, 'PHOTO_FORMAT_UNSUPPORTED')
    try:raw = base64.b64decode(match.group(2), validate=True)
    except ValueError:sec.fail(422, 'PHOTO_FORMAT_UNSUPPORTED')
    magic_ok = (match.group(1) == 'jpeg' and raw[:3] == b'\xff\xd8\xff') or (match.group(1) == 'png' and raw[:8] == b'\x89PNG\r\n\x1a\n') or (match.group(1) == 'webp' and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP')
    if not magic_ok or len(raw) > 160_000:sec.fail(422, 'PHOTO_FORMAT_UNSUPPORTED')
    with sec.transaction(db):
        db.execute('INSERT OR IGNORE INTO account_profiles(account_id) VALUES (?)', (account,))
        db.execute('UPDATE account_profiles SET photo=? WHERE account_id=?', (f'data:image/{match.group(1)};base64,' + base64.b64encode(raw).decode(), account))
    return dict(simulation_only=True)


@router.post('/account/photo/remove')
def remove_photo(actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    with sec.transaction(db):
        db.execute('UPDATE account_profiles SET photo=NULL WHERE account_id=?', (account,))
    return dict(simulation_only=True)


# ---------- password ----------
class PasswordChange(Exact):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.post('/account/password')
def change_password(body: PasswordChange, request: Request, actor=Depends(principal), db=Depends(db_connection)):
    browser_origin(request)
    account = account_of(db, actor)
    sec.budget(db, 'password-change:' + account, 6)
    check_password(db, account, body.current_password)
    try:reject_weak_password(body.new_password, username_of(db, account))
    except ValueError:sec.fail(422, 'PASSWORD_TOO_WEAK')
    if body.new_password == body.current_password:sec.fail(422, 'PASSWORD_UNCHANGED')
    hashed = password_hash(body.new_password)
    with sec.transaction(db):
        db.execute('UPDATE auth_accounts SET password_hash=? WHERE account_id=?', (hashed, account))
        db.execute('DELETE FROM security_sessions WHERE token_hash<>? AND user_id IN (SELECT user_id FROM account_members WHERE account_id=?)', (actor.token_hash, account))
    return dict(other_sessions_signed_out=True, simulation_only=True)


# ---------- email ----------
class EmailSet(Exact):
    email: str = Field(min_length=3, max_length=254)


@router.post('/account/email')
def set_email(body: EmailSet, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    try:email = normalize_email(body.email)
    except ValueError:sec.fail(422, 'INVALID_EMAIL')
    sec.budget(db, 'email-set:' + account, 5)
    with sec.transaction(db):
        current = db.execute('SELECT email,verified FROM account_emails WHERE account_id=?', (account,)).fetchone()
        if current and current[0] == email and current[1]:return dict(already_verified=True, email_service=mailer.configured(), simulation_only=True)
        db.execute('INSERT INTO account_emails VALUES (?,?,0) ON CONFLICT(account_id) DO UPDATE SET email=excluded.email, verified=0', (account, email))
    sent = False
    if mailer.configured():
        code = issue_code(db, 'verify', account + ':' + email)
        sent = mailer.send(email, *mailer.code_message('verify', code))
    return dict(sent=sent, email_service=mailer.configured(), simulation_only=True)


class CodeBody(Exact):
    code: str = Field(min_length=4, max_length=12)


@router.post('/account/email/verify')
def verify_email(body: CodeBody, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    scope = 'verify-email:' + account
    if limiter.failure_total(scope) >= 10:sec.fail(429, 'TOO_MANY_FAILED_ATTEMPTS')
    row = db.execute('SELECT email,verified FROM account_emails WHERE account_id=?', (account,)).fetchone()
    if not row:sec.fail(409, 'EMAIL_NOT_SET')
    if row[1]:return dict(simulation_only=True)
    if not check_code(db, 'verify', account + ':' + row[0], body.code):
        limiter.add_failure([scope])
        sec.fail(401, 'INVALID_CODE')
    try:
        with sec.transaction(db):
            db.execute('UPDATE account_emails SET verified=1 WHERE account_id=?', (account,))
    except sqlite3.IntegrityError:
        sec.fail(409, 'EMAIL_ALREADY_USED')
    return dict(simulation_only=True)


# ---------- two-factor ----------
def mfa_enabled(db, account):
    row = db.execute('SELECT enabled FROM account_mfa WHERE account_id=?', (account,)).fetchone()
    return bool(row and row[0])


def check_second_factor(db, account, code):
    """Accept a current authenticator code or an unused backup code. Consumes whatever matched."""
    scope = 'second-factor:' + account
    if limiter.failure_total(scope) >= 10:sec.fail(429, 'TOO_MANY_FAILED_ATTEMPTS')
    with sec.transaction(db):
        row = db.execute('SELECT secret_blob,last_step,backup_hashes FROM account_mfa WHERE account_id=? AND enabled=1', (account,)).fetchone()
        if row:
            step = mfa.verify(mfa.unseal(row[0]), code, row[1])
            if step is not None:
                db.execute('UPDATE account_mfa SET last_step=? WHERE account_id=?', (step, account))
                return True
            digest, backups = mfa.hash_backup(code), json.loads(row[2])
            if digest in backups:
                backups.remove(digest)
                db.execute('UPDATE account_mfa SET backup_hashes=? WHERE account_id=?', (json.dumps(backups), account))
                return True
    limiter.add_failure([scope])
    return False


class PasswordOnly(Exact):
    password: str = Field(min_length=1, max_length=128)


@router.post('/account/2fa/setup')
def two_factor_setup(body: PasswordOnly, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    check_password(db, account, body.password)
    if mfa_enabled(db, account):sec.fail(409, 'TWO_FACTOR_ALREADY_ON')
    secret = mfa.new_secret()
    with sec.transaction(db):
        db.execute('INSERT INTO account_mfa VALUES (?,?,0,0,\'[]\') ON CONFLICT(account_id) DO UPDATE SET secret_blob=excluded.secret_blob, enabled=0, last_step=0, backup_hashes=\'[]\'', (account, mfa.seal(secret)))
    return dict(secret=secret, uri=mfa.provisioning_uri(secret, username_of(db, account)), simulation_only=True)


@router.post('/account/2fa/enable')
def two_factor_enable(body: CodeBody, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    scope = 'second-factor:' + account
    if limiter.failure_total(scope) >= 10:sec.fail(429, 'TOO_MANY_FAILED_ATTEMPTS')
    row = db.execute('SELECT secret_blob,enabled FROM account_mfa WHERE account_id=?', (account,)).fetchone()
    if not row or row[1]:sec.fail(409, 'TWO_FACTOR_SETUP_REQUIRED')
    step = mfa.verify(mfa.unseal(row[0]), body.code, 0)
    if step is None:
        limiter.add_failure([scope])
        sec.fail(401, 'INVALID_CODE')
    codes = mfa.new_backup_codes()
    with sec.transaction(db):
        db.execute('UPDATE account_mfa SET enabled=1,last_step=?,backup_hashes=? WHERE account_id=?', (step, json.dumps([mfa.hash_backup(c) for c in codes]), account))
    return dict(backup_codes=codes, simulation_only=True)


class MfaDisable(Exact):
    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=4, max_length=12)


@router.post('/account/2fa/disable')
def two_factor_disable(body: MfaDisable, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    check_password(db, account, body.password)
    if not mfa_enabled(db, account):return dict(simulation_only=True)
    if not check_second_factor(db, account, body.code):sec.fail(401, 'INVALID_CODE')
    with sec.transaction(db):
        db.execute('DELETE FROM account_mfa WHERE account_id=?', (account,))
    return dict(simulation_only=True)


def begin_challenge(db, account):
    token = secrets.token_urlsafe(24)
    with sec.transaction(db):
        db.execute('DELETE FROM mfa_challenges WHERE expires_at<?', (sec.now(),))
        db.execute('INSERT INTO mfa_challenges VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), account, sec.now() + 300))
    return dict(mfa_required=True, challenge=token, simulation_only=True)


class Challenge(Exact):
    challenge: str = Field(min_length=20, max_length=100)
    code: str = Field(min_length=4, max_length=12)
    remember: bool = False


@router.post('/auth/login/2fa')
def login_second_factor(body: Challenge, request: Request, response: Response, db=Depends(db_connection)):
    browser_origin(request)
    rate(request, db, 'login2fa', 12, 120, 300)
    digest = hashlib.sha256(body.challenge.encode()).hexdigest()
    attempts_scope = 'challenge:' + digest
    row = db.execute('SELECT account_id,expires_at FROM mfa_challenges WHERE token_hash=?', (digest,)).fetchone()
    if not row or row[1] < sec.now() or limiter.failure_total(attempts_scope) >= 5:sec.fail(401, 'CHALLENGE_EXPIRED')
    if not check_second_factor(db, row[0], body.code):
        limiter.add_failure([attempts_scope])
        sec.fail(401, 'INVALID_CODE')
    with sec.transaction(db):
        db.execute('DELETE FROM mfa_challenges WHERE token_hash=?', (digest,))
    return complete_login(db, response, row[0], body.remember)


# ---------- password reset by email ----------
class ResetRequest(Exact):
    email: str = Field(min_length=3, max_length=254)


@router.post('/auth/reset/request')
def reset_request(body: ResetRequest, request: Request, db=Depends(db_connection)):
    browser_origin(request)
    rate(request, db, 'reset', 5, 20, 30)
    if not mailer.configured():sec.fail(503, 'EMAIL_NOT_CONFIGURED')
    try:email = normalize_email(body.email)
    except ValueError:sec.fail(422, 'INVALID_EMAIL')
    scope = 'reset-email:' + hashlib.sha256(email.encode()).hexdigest()[:32]
    answer = dict(sent=True, simulation_only=True)  # identical whether or not the address is registered
    if limiter.failure_total(scope) >= 3:return answer
    limiter.add_failure([scope])
    if db.execute('SELECT 1 FROM account_emails WHERE email=? AND verified=1', (email,)).fetchone():
        mailer.send(email, *mailer.code_message('reset', issue_code(db, 'reset', email)))
    return answer


class ResetConfirm(Exact):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)
    second_factor: str | None = Field(default=None, max_length=12)


@router.post('/auth/reset/confirm')
def reset_confirm(body: ResetConfirm, request: Request, db=Depends(db_connection)):
    browser_origin(request)
    edge = rate(request, db, 'resetconfirm', 5, 20, 30)
    try:email = normalize_email(body.email)
    except ValueError:sec.fail(422, 'INVALID_EMAIL')
    scopes = failure_scopes('reset-confirm', email, edge, 5, 15, 30)
    locked_out(db, scopes)
    row = db.execute('SELECT a.account_id,a.username FROM account_emails e JOIN auth_accounts a ON a.account_id=e.account_id WHERE e.email=? AND e.verified=1', (email,)).fetchone()
    if not row:
        record_failure(db, scopes)
        sec.fail(401, 'INVALID_RESET_CODE')
    account, username = row
    try:reject_weak_password(body.new_password, username)
    except ValueError:sec.fail(422, 'PASSWORD_TOO_WEAK')
    if mfa_enabled(db, account) and not body.second_factor:sec.fail(401, 'SECOND_FACTOR_REQUIRED')
    if not check_code(db, 'reset', email, body.code):
        record_failure(db, scopes)
        sec.fail(401, 'INVALID_RESET_CODE')
    if mfa_enabled(db, account) and not check_second_factor(db, account, body.second_factor):
        record_failure(db, scopes)
        sec.fail(401, 'INVALID_CODE')
    hashed = password_hash(body.new_password)
    with sec.transaction(db):
        db.execute('UPDATE auth_accounts SET password_hash=? WHERE account_id=?', (hashed, account))
        db.execute('DELETE FROM security_sessions WHERE user_id IN (SELECT user_id FROM account_members WHERE account_id=?)', (account,))
    return dict(simulation_only=True)
