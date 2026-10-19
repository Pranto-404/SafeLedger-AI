"""Workspace sharing (members, invitations, roles, leaving) and clear/restore of per-currency workspaces."""
import pytest
from api.tests.test_accounts import world, signup, PASSWORD
from api.tests.test_manual_inputs import record
from api.app import mailer


def second_person(c, name):
    c.post('/api/auth/logout', json={})
    signup(c, name)


def test_members_invite_join_roles_remove_and_leave(world):
    c, _ = world
    owner = signup(c, 'share_owner')
    c.post('/api/account/profile', json={'display_name': 'Owner Person'})
    created = c.post('/api/account/invitations', json={'role': 'approver', 'hours': 24})
    assert created.status_code == 201 and created.json()['expires_in_seconds'] == 86400
    assert c.post('/api/account/invitations', json={'role': 'owner'}).status_code == 422
    assert c.post('/api/account/invitations', json={'role': 'viewer', 'hours': 500}).status_code == 422
    listing = c.get('/api/account/members').json()
    assert [m['role'] for m in listing['members']] == ['owner'] and listing['members'][0]['display_name'] == 'Owner Person' and len(listing['invitations']) == 1
    code = created.json()['code']
    second_person(c, 'share_helper')
    joined = c.post('/api/account/join', json={'code': code})
    assert joined.status_code == 200 and joined.json()['role'] == 'approver' and joined.json()['business_id'] == owner['business_id']
    assert c.post('/api/account/join', json={'code': code}).status_code == 409  # single use
    view = c.get('/api/account/members').json()
    assert view['your_role'] == 'approver' and view['invitations'] == [] and {m['username'] for m in view['members']} == {'share_owner', 'share_helper'}
    helper = next(m for m in view['members'] if m['you'])
    # only the owner manages people
    assert c.post('/api/account/members/remove', json={'member_id': helper['member_id']}).status_code == 403
    assert c.post('/api/account/invitations', json={'role': 'viewer'}).status_code == 403
    workspaces = c.get('/api/account/workspaces').json()['workspaces']
    assert {w['role'] for w in workspaces} == {'owner', 'approver'} and all(w['currency'] == 'BDT' for w in workspaces)
    # leaving returns to the person's own workspace
    left = c.post('/api/account/leave', json={})
    assert left.status_code == 200 and left.json()['role'] == 'owner' and left.json()['business_id'] != owner['business_id']
    assert all(w['business_id'] != owner['business_id'] for w in c.get('/api/account/workspaces').json()['workspaces'])


def login_as(c, name):
    c.post('/api/auth/logout', json={})
    c.cookies.clear()
    assert c.post('/api/auth/login', json={'username': name, 'password': PASSWORD}).status_code == 200


def test_owner_changes_role_removes_member_and_revokes_invitations(world):
    c, _ = world
    owner = signup(c, 'role_owner')
    code = c.post('/api/account/invitations', json={'role': 'viewer'}).json()['code']
    pending = c.get('/api/account/members').json()['invitations'][0]['invite_id']
    assert c.post('/api/account/invitations/revoke', json={'invite_id': pending}).status_code == 200
    assert c.get('/api/account/members').json()['invitations'] == []
    second_person(c, 'late_helper')
    assert c.post('/api/account/join', json={'code': code}).status_code == 409  # revoked
    login_as(c, 'role_owner')
    code = c.post('/api/account/invitations', json={'role': 'viewer'}).json()['code']
    second_person(c, 'role_helper')
    assert c.post('/api/account/join', json={'code': code}).json()['role'] == 'viewer'
    helper_cookie = c.cookies.get('safeledger_session')
    login_as(c, 'role_owner')
    member = next(m for m in c.get('/api/account/members').json()['members'] if m['username'] == 'role_helper')
    assert c.post('/api/account/members/role', json={'member_id': member['member_id'], 'role': 'approver'}).status_code == 200
    c.cookies.set('safeledger_session', helper_cookie)
    assert c.get('/api/session').status_code == 401  # a role change signs the person out so the new role applies
    login_as(c, 'role_owner')
    owner_row = next(m for m in c.get('/api/account/members').json()['members'] if m['role'] == 'owner')
    assert c.post('/api/account/members/remove', json={'member_id': owner_row['member_id']}).status_code == 409  # the owner is untouchable
    assert c.post('/api/account/members/remove', json={'member_id': member['member_id']}).status_code == 200
    assert [m['username'] for m in c.get('/api/account/members').json()['members']] == ['role_owner']
    login_as(c, 'role_helper')
    assert all(w['business_id'] != owner['business_id'] for w in c.get('/api/account/workspaces').json()['workspaces'])
    assert c.post('/api/account/switch', json={'business_id': owner['business_id']}).status_code == 403


def test_invitation_email_is_sent_when_configured(world, monkeypatch):
    c, _ = world
    sent = []
    monkeypatch.setattr(mailer, 'configured', lambda: True)
    monkeypatch.setattr(mailer, 'send', lambda to, subject, text: sent.append((to, subject, text)) or True)
    signup(c, 'mail_owner')
    r = c.post('/api/account/invitations', json={'role': 'approver', 'email': 'Friend@Example.com'})
    assert r.json()['emailed'] and sent[0][0] == 'friend@example.com' and '/?join=' + r.json()['code'] in sent[0][2]
    assert c.post('/api/account/invitations', json={'email': 'not-an-email'}).status_code == 422


def test_clear_hides_selected_currency_workspaces_and_restore_brings_them_back(world):
    c, _ = world
    first = signup(c, 'clear_owner')
    assert record(c, amount_minor=500000)[0].status_code == 201
    usd = c.post('/api/account/workspaces', json={'kind': 'personal', 'name': 'US shop', 'currency': 'USD'}).json()
    assert record(c, amount_minor=1234)[0].status_code == 201
    listing = c.get('/api/account/workspaces').json()
    assert {w['currency'] for w in listing['workspaces']} == {'BDT', 'USD'} and listing['cleared'] == []
    old_cookie = c.cookies.get('safeledger_session')
    cleared = c.post('/api/account/workspaces/clear', json={'business_ids': [usd['business_id']]})
    assert cleared.status_code == 200 and cleared.json()['cleared'] == 1 and cleared.json()['business_id'] == first['business_id']
    after = c.get('/api/account/workspaces').json()
    assert [w['currency'] for w in after['workspaces']] == ['BDT'] and after['cleared'][0]['currency'] == 'USD'
    assert c.get('/api/workspace').json()['snapshot']['balance_minor'] == 500000  # untouched workspace keeps its data
    c.cookies.set('safeledger_session', old_cookie)
    assert c.get('/api/workspace').json()['error']['code'] == 'WORKSPACE_CLEARED'
    c.cookies.clear(); c.post('/api/auth/login', json={'username': 'clear_owner', 'password': PASSWORD})
    assert c.post('/api/account/switch', json={'business_id': usd['business_id']}).status_code == 403
    assert c.post('/api/account/workspaces/restore', json={'business_id': usd['business_id']}).status_code == 200
    assert c.post('/api/account/switch', json={'business_id': usd['business_id']}).status_code == 200
    assert c.get('/api/workspace').json()['snapshot']['balance_minor'] == 1234


def test_clear_all_leaves_a_fresh_empty_workspace_in_the_same_currency(world):
    c, _ = world
    first = signup(c, 'wipe_owner')
    assert record(c, amount_minor=777)[0].status_code == 201
    r = c.post('/api/account/workspaces/clear', json={'business_ids': [first['business_id']]})
    assert r.status_code == 200 and r.json()['business_id'] != first['business_id'] and r.json()['role'] == 'owner'
    fresh = c.get('/api/workspace').json()
    assert fresh['snapshot']['balance_minor'] == 0 and fresh['invoices'] == [] and fresh['snapshot']['currency'] == 'BDT'
    assert [w['business_id'] for w in c.get('/api/account/workspaces').json()['cleared']] == [first['business_id']]


def test_only_owners_can_clear_and_restore_and_old_data_cannot_be_forced(world):
    c, _ = world
    owner = signup(c, 'guard_owner')
    code = c.post('/api/account/invitations', json={'role': 'approver'}).json()['code']
    second_person(c, 'guard_helper')
    c.post('/api/account/join', json={'code': code})
    assert c.post('/api/account/workspaces/clear', json={'business_ids': [owner['business_id']]}).status_code == 403
    assert c.post('/api/account/workspaces/clear', json={'business_ids': ['workspace-does-not-exist']}).status_code == 403
    assert c.post('/api/account/workspaces/clear', json={'business_ids': []}).status_code == 422
    assert c.post('/api/account/workspaces/restore', json={'business_id': owner['business_id']}).status_code == 404


def test_rename_workspace_is_owner_only(world):
    c, _ = world
    signup(c, 'name_owner')
    assert c.post('/api/account/workspaces/rename', json={'name': '  Dhaka   shop  '}).status_code == 200
    assert c.get('/api/account/workspaces').json()['workspaces'][0]['name'] == 'Dhaka shop'
    assert c.post('/api/account/workspaces/rename', json={'name': ''}).status_code == 422
