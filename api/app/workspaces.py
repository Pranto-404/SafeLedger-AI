"""Workspace switching, sharing and clear/restore. Every route re-derives authority from the signed-in account."""
import hashlib
import json
import secrets
import uuid
from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from api.app import mailer, security as sec
from api.app.accounts import (browser_origin, create_workspace_data, identity, issue, personal_member, set_cookie)
from api.app.contracts import Contract
from api.app.profile import Exact, account_of
from api.app.routes import db_connection, principal

router = APIRouter(prefix='/api')
RESTORE_DAYS = 30


def _currency_of(db, business):
    row = db.execute("SELECT json_extract(payload,'$.currency') FROM financial_datasets WHERE business_id=?", (business,)).fetchone()
    return row[0] if row and row[0] else None


@router.get('/account/workspaces')
def workspaces(actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    rows = db.execute("SELECT m.business_id,u.role,COALESCE(w.name,'My workspace'),w.archived_at FROM account_members m JOIN security_users u ON u.user_id=m.user_id JOIN workspace_meta w ON w.business_id=m.business_id WHERE m.account_id=? AND u.active=1 AND w.kind='personal' ORDER BY m.rowid", (account,)).fetchall()
    active, archived = [], []
    for business, role, name, archived_at in rows:
        entry = dict(business_id=business, role=role, name=name, kind='personal', currency=_currency_of(db, business))
        if archived_at is None:active.append(dict(entry, current=business == actor.business_id))
        elif role == 'owner' and sec.now() - archived_at <= RESTORE_DAYS * 86400:archived.append(dict(entry, restorable_until=archived_at + RESTORE_DAYS * 86400))
    return dict(workspaces=active, cleared=archived, simulation_only=True)


class Rename(Exact):
    name: str = Field(min_length=1, max_length=60)


@router.post('/account/workspaces/rename')
def rename(body: Rename, actor=Depends(principal), db=Depends(db_connection)):
    if actor.role != 'owner':sec.fail(403, 'OWNER_REQUIRED')
    name = ' '.join(body.name.split())
    if not name or any(ord(ch) < 32 for ch in name):sec.fail(422, 'INVALID_NAME')
    with sec.transaction(db):
        db.execute('UPDATE workspace_meta SET name=? WHERE business_id=?', (name, actor.business_id))
    return dict(simulation_only=True)


# ---------- sharing ----------
@router.get('/account/members')
def members(actor=Depends(principal), db=Depends(db_connection)):
    account_of(db, actor)
    rows = db.execute("SELECT u.user_id,u.role,a.username,COALESCE(p.display_name,'') FROM security_users u JOIN account_members m ON m.user_id=u.user_id JOIN auth_accounts a ON a.account_id=m.account_id LEFT JOIN account_profiles p ON p.account_id=a.account_id WHERE u.business_id=? AND u.active=1 ORDER BY CASE u.role WHEN 'owner' THEN 0 ELSE 1 END,a.username", (actor.business_id,)).fetchall()
    people = [dict(member_id=r[0], role=r[1], username=r[2], display_name=r[3], you=r[0] == actor.user_id) for r in rows]
    invites = []
    if actor.role == 'owner':
        invites = [dict(invite_id=r[0][:16], role=r[1], expires_at=r[2]) for r in db.execute('SELECT code_hash,role,expires_at FROM workspace_invites WHERE business_id=? AND used_by IS NULL AND expires_at>? ORDER BY expires_at', (actor.business_id, sec.now())).fetchall()]
    return dict(members=people, invitations=invites, your_role=actor.role, simulation_only=True)


class InviteRequest(Exact):
    role: str = Field(pattern='^(approver|viewer)$', default='approver')
    hours: int = Field(default=72, ge=1, le=168, strict=True)
    email: str | None = Field(default=None, max_length=254)


@router.post('/account/invitations', status_code=201)
def invite(body: InviteRequest, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    if actor.role != 'owner':sec.fail(403, 'WORKSPACE_OWNER_REQUIRED')
    sec.budget(db, 'invite:' + actor.user_id, 8)
    from api.app.accounts import normalize_email
    email = None
    if body.email:
        try:email = normalize_email(body.email)
        except ValueError:sec.fail(422, 'INVALID_EMAIL')
    if db.execute('SELECT count(*) FROM workspace_invites WHERE business_id=? AND used_by IS NULL AND expires_at>?', (actor.business_id, sec.now())).fetchone()[0] >= 20:sec.fail(409, 'TOO_MANY_OPEN_INVITATIONS')
    code = secrets.token_urlsafe(24)
    expires = sec.now() + body.hours * 3600
    with sec.transaction(db):
        db.execute('INSERT INTO workspace_invites(code_hash,business_id,role,created_by,expires_at,used_by,created_at) VALUES (?,?,?,?,?,NULL,?)', (hashlib.sha256(code.encode()).hexdigest(), actor.business_id, body.role, actor.user_id, expires, sec.now()))
        sec.audit(db, actor, 'invite-' + uuid.uuid4().hex, 'INVITATION_CREATED', {'role': body.role, 'expires_in_hours': body.hours, 'emailed': bool(email)})
    emailed = False
    if email and mailer.configured():
        import os
        base = os.environ.get('SAFELEDGER_PUBLIC_URL', 'https://capzoryx-copilot.vercel.app').rstrip('/')
        name = db.execute("SELECT COALESCE(NULLIF(p.display_name,''),a.username) FROM auth_accounts a LEFT JOIN account_profiles p ON p.account_id=a.account_id WHERE a.account_id=?", (account,)).fetchone()[0]
        role_text = 'approve payments' if body.role == 'approver' else 'view the records'
        emailed = mailer.send(email, f'{name} invited you to a Capzoryx Copilot workspace', f'{name} invited you to {role_text} in their Capzoryx Copilot workspace.\n\nOpen this link, sign in or create a free account, and you will be added:\n{base}/?join={code}\n\nThe invitation expires in {body.hours} hours and works once.')
    return dict(code=code, role=body.role, expires_at=expires, expires_in_seconds=body.hours * 3600, emailed=emailed, simulation_only=True)


class InvitePreview(Exact):
    code: str = Field(min_length=20, max_length=100)


@router.post('/invitations/preview')
def preview_invitation(body: InvitePreview, request: Request, db=Depends(db_connection)):
    """Lets the sign-up page say who invited the visitor. Anyone holding the secret link may see this much, nothing more."""
    from api.app.accounts import rate
    browser_origin(request)
    rate(request, db, 'invprev', 20, 60, 120)
    row = db.execute("SELECT w.name,i.role,COALESCE(NULLIF(p.display_name,''),a.username) FROM workspace_invites i JOIN workspace_meta w ON w.business_id=i.business_id AND w.kind='personal' AND w.archived_at IS NULL "
                     "LEFT JOIN account_members m ON m.user_id=i.created_by LEFT JOIN auth_accounts a ON a.account_id=m.account_id LEFT JOIN account_profiles p ON p.account_id=a.account_id "
                     "WHERE i.code_hash=? AND i.expires_at>? AND i.used_by IS NULL", (hashlib.sha256(body.code.encode()).hexdigest(), sec.now())).fetchone()
    if not row:sec.fail(404, 'INVITATION_INVALID_OR_EXPIRED')
    return dict(workspace_name=row[0], role=row[1], invited_by=row[2], simulation_only=True)


class InviteId(Exact):
    invite_id: str = Field(min_length=16, max_length=16, pattern='^[a-f0-9]{16}$')


@router.post('/account/invitations/revoke')
def revoke(body: InviteId, actor=Depends(principal), db=Depends(db_connection)):
    if actor.role != 'owner':sec.fail(403, 'WORKSPACE_OWNER_REQUIRED')
    with sec.transaction(db):
        db.execute('DELETE FROM workspace_invites WHERE business_id=? AND used_by IS NULL AND substr(code_hash,1,16)=?', (actor.business_id, body.invite_id))
    return dict(simulation_only=True)


class MemberId(Exact):
    member_id: str = Field(min_length=5, max_length=80)


def _member(db, actor, member_id):
    row = db.execute('SELECT u.role,u.active FROM security_users u JOIN account_members m ON m.user_id=u.user_id WHERE u.user_id=? AND u.business_id=?', (member_id, actor.business_id)).fetchone()
    if not row or not row[1]:sec.fail(404, 'MEMBER_NOT_FOUND')
    if row[0] == 'owner':sec.fail(409, 'OWNER_CANNOT_BE_CHANGED')
    return row


@router.post('/account/members/remove')
def remove_member(body: MemberId, actor=Depends(principal), db=Depends(db_connection)):
    if actor.role != 'owner':sec.fail(403, 'WORKSPACE_OWNER_REQUIRED')
    with sec.transaction(db):
        _member(db, actor, body.member_id)
        db.execute('UPDATE security_users SET active=0 WHERE user_id=?', (body.member_id,))
        db.execute('DELETE FROM security_sessions WHERE user_id=?', (body.member_id,))
        sec.audit(db, actor, 'member-' + uuid.uuid4().hex, 'MEMBER_REMOVED', {'removed_user': body.member_id})
    return dict(simulation_only=True)


class MemberRole(Exact):
    member_id: str = Field(min_length=5, max_length=80)
    role: str = Field(pattern='^(approver|viewer)$')


@router.post('/account/members/role')
def change_role(body: MemberRole, actor=Depends(principal), db=Depends(db_connection)):
    if actor.role != 'owner':sec.fail(403, 'WORKSPACE_OWNER_REQUIRED')
    with sec.transaction(db):
        _member(db, actor, body.member_id)
        db.execute('UPDATE security_users SET role=? WHERE user_id=?', (body.role, body.member_id))
        db.execute('DELETE FROM security_sessions WHERE user_id=?', (body.member_id,))
        sec.audit(db, actor, 'member-' + uuid.uuid4().hex, 'MEMBER_ROLE_CHANGED', {'user': body.member_id, 'role': body.role})
    return dict(simulation_only=True)


@router.post('/account/leave')
def leave(request: Request, response: Response, actor=Depends(principal), db=Depends(db_connection)):
    browser_origin(request)
    account = account_of(db, actor)
    if actor.role == 'owner':sec.fail(409, 'OWNER_CANNOT_LEAVE')
    with sec.transaction(db):
        sec.audit(db, actor, 'member-' + uuid.uuid4().hex, 'MEMBER_LEFT', {'user': actor.user_id})
        db.execute('UPDATE security_users SET active=0 WHERE user_id=?', (actor.user_id,))
        db.execute('DELETE FROM security_sessions WHERE user_id=?', (actor.user_id,))
        token = issue(db, personal_member(db, account))
    set_cookie(response, token)
    return identity(db, sec.authenticate(db, token))


# ---------- clear / restore ----------
class ClearRequest(Exact):
    business_ids: list[str] = Field(min_length=1, max_length=20)


@router.post('/account/workspaces/clear')
def clear(body: ClearRequest, request: Request, response: Response, actor=Depends(principal), db=Depends(db_connection)):
    """Hide chosen workspaces (one per currency). Signed history is retained, so this is reversible for 30 days."""
    browser_origin(request)
    account = account_of(db, actor)
    sec.budget(db, 'clear:' + account, 6)
    ids = list(dict.fromkeys(body.business_ids))
    with sec.transaction(db):
        owned = {r[0]: r[1] for r in db.execute("SELECT m.business_id,u.role FROM account_members m JOIN security_users u ON u.user_id=m.user_id JOIN workspace_meta w ON w.business_id=m.business_id WHERE m.account_id=? AND u.active=1 AND w.archived_at IS NULL AND w.kind='personal'", (account,)).fetchall()}
        if any(owned.get(b) != 'owner' for b in ids):sec.fail(403, 'WORKSPACE_OWNER_REQUIRED')
        currencies = [_currency_of(db, b) or 'BDT' for b in ids]
        for business in ids:
            db.execute('UPDATE workspace_meta SET archived_at=? WHERE business_id=?', (sec.now(), business))
            db.execute('DELETE FROM workspace_invites WHERE business_id=? AND used_by IS NULL', (business,))
        remaining = personal_member(db, account) if db.execute("SELECT 1 FROM account_members m JOIN security_users u ON u.user_id=m.user_id JOIN workspace_meta w ON w.business_id=m.business_id WHERE m.account_id=? AND u.active=1 AND w.kind='personal' AND w.archived_at IS NULL", (account,)).fetchone() else None
        if remaining is None:
            business, user = 'workspace-' + uuid.uuid4().hex, 'user-' + uuid.uuid4().hex
            db.execute("INSERT INTO security_users VALUES (?,?,'owner',1)", (user, business))
            db.execute('INSERT INTO account_members VALUES (?,?,?)', (account, business, user))
            create_workspace_data(db, business, 'personal', 'My workspace', currencies[0])
            remaining = user
        token = issue(db, remaining)
    set_cookie(response, token)
    return dict(identity(db, sec.authenticate(db, token)), cleared=len(ids))


class BusinessId(Exact):
    business_id: str = Field(min_length=1, max_length=80)


@router.post('/account/workspaces/restore')
def restore(body: BusinessId, actor=Depends(principal), db=Depends(db_connection)):
    account = account_of(db, actor)
    with sec.transaction(db):
        row = db.execute("SELECT w.archived_at,u.role FROM account_members m JOIN security_users u ON u.user_id=m.user_id JOIN workspace_meta w ON w.business_id=m.business_id WHERE m.account_id=? AND m.business_id=? AND u.active=1 AND w.kind='personal'", (account, body.business_id)).fetchone()
        if not row or row[1] != 'owner':sec.fail(404, 'WORKSPACE_NOT_FOUND')
        if row[0] is None:return dict(simulation_only=True)
        if sec.now() - row[0] > RESTORE_DAYS * 86400:sec.fail(410, 'RESTORE_WINDOW_ENDED')
        db.execute('UPDATE workspace_meta SET archived_at=NULL WHERE business_id=?', (body.business_id,))
    return dict(simulation_only=True)
