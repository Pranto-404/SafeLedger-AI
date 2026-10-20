"""Regression tests for the 20 Oct 2026 full security review (see docs/SECURITY_REVIEW_20261020.md, section 'Full review')."""
import time
import pytest
from api.tests.test_accounts import world, signup, PASSWORD
from api.tests.test_account_settings import outbox, fast, code_from, NEW_PASSWORD
from api.tests.test_i18n import translator
from api.tests.test_workspaces_sharing import second_person, login_as
from api.app import mailer, mfa
from api.app.ratelimit import limiter


def turn_on_two_step(c):
    secret = c.post('/api/account/2fa/setup', json={'password': PASSWORD}).json()['secret']
    backups = c.post('/api/account/2fa/enable', json={'code': mfa.code_at(secret, int(time.time() // 30))}).json()['backup_codes']
    return secret, backups


# ---- the recovery key must not be a way around two-step sign-in ----
def test_recovery_key_needs_the_second_step_when_two_step_is_on(world, fast):
    c, _ = world
    key = signup(c, 'rk_mfa_user')['recovery_code']
    secret, backups = turn_on_two_step(c)
    c.post('/api/auth/logout', json={})
    body = {'username': 'rk_mfa_user', 'password': NEW_PASSWORD, 'recovery_code': key}
    missing = c.post('/api/auth/recover', json=body)
    assert missing.status_code == 401 and missing.json()['error']['code'] == 'SECOND_FACTOR_REQUIRED' and 'safeledger_session' not in c.cookies
    wrong = c.post('/api/auth/recover', json={**body, 'second_factor': '000000'})
    assert wrong.status_code == 401 and wrong.json()['error']['code'] == 'INVALID_CODE' and 'safeledger_session' not in c.cookies
    # the failed tries changed nothing: the old password still reaches the second step
    assert c.post('/api/auth/login', json={'username': 'rk_mfa_user', 'password': PASSWORD}).json().get('mfa_required')
    ok = c.post('/api/auth/recover', json={**body, 'second_factor': backups[0]})
    assert ok.status_code == 200 and ok.json()['recovery_code'] != key
    assert c.post('/api/auth/recover', json={**body, 'second_factor': backups[1]}).status_code == 401  # the old key is spent


def test_recovery_key_still_works_alone_without_two_step(world, fast):
    c, _ = world
    key = signup(c, 'rk_plain_user')['recovery_code']
    c.post('/api/auth/logout', json={})
    assert c.post('/api/auth/recover', json={'username': 'rk_plain_user', 'password': NEW_PASSWORD, 'recovery_code': key}).status_code == 200


# ---- the mailbox is not an open mailer ----
def test_one_address_cannot_be_flooded_with_codes(world, fast, outbox):
    c, _ = world
    signup(c, 'flood_user')
    for _ in range(12):
        c.post('/api/account/email', json={'email': 'victim@example.com'})
    assert len([m for m in outbox if m[0] == 'victim@example.com']) == mailer.PER_RECIPIENT_HOURLY


def test_site_wide_hourly_and_daily_ceilings(world, monkeypatch):
    mailer.reset_budget()
    granted = [mailer.reserve('target%d@example.com' % i) for i in range(mailer.BULK_HOURLY + 10)]
    assert granted == [True] * mailer.BULK_HOURLY + [False] * 10
    # password-reset mail is not starved by bulk mail, but it still obeys the daily ceiling
    assert mailer.reserve('someone@example.com', bulk=False)
    monkeypatch.setattr(mailer, 'DAILY_CAP', mailer._daily['count'])
    assert not mailer.reserve('another@example.com', bulk=False)


def test_invitation_email_respects_the_per_address_ceiling(world, outbox):
    c, _ = world
    signup(c, 'invite_flood')
    flags = []
    for _ in range(7):
        flags.append(c.post('/api/account/invitations', json={'role': 'viewer', 'email': 'friend@example.com'}).json()['emailed'])
        c.cookies  # keep the session; only the invitation budget (8 a minute) applies here
    assert flags == [True] * mailer.PER_RECIPIENT_HOURLY + [False] * (7 - mailer.PER_RECIPIENT_HOURLY)


def test_reserve_never_logs_the_address(caplog):
    mailer.reset_budget()
    with caplog.at_level('WARNING', logger='safeledger.mail'):
        for _ in range(mailer.PER_RECIPIENT_HOURLY + 2):
            mailer.reserve('secret.person@example.com')
    assert 'secret.person' not in caplog.text


# ---- the public language endpoint cannot be used to drain the model quota ----
def test_failed_translation_attempts_back_off(world, translator):
    c, _ = world
    translator['mode'] = 'evil'  # every answer is rejected, so the language stays untranslated
    for _ in range(6):
        assert c.get('/api/i18n?lang=fr').json()['strings'] == {}
    assert len(translator['calls']) == 1
    translator['mode'] = 'quota'
    for _ in range(6):
        assert c.get('/api/i18n?lang=es').status_code == 200
    assert len(translator['calls']) == 2
    translator['mode'] = 'good'  # a language that is making progress is not slowed down
    for _ in range(3):
        c.get('/api/i18n?lang=ja')
    assert len(translator['calls']) == 5


# ---- password reset does not reveal which addresses have accounts ----
def test_reset_confirm_answers_alike_for_known_and_unknown_addresses(world, fast, outbox):
    c, _ = world
    c.post('/api/auth/signup', json={'username': 'probe_known', 'password': PASSWORD, 'email': 'known@example.com'})
    c.post('/api/account/email/verify', json={'code': code_from(outbox, 'known@example.com')})
    turn_on_two_step(c)
    c.post('/api/auth/logout', json={})

    def attempt(email, pw=NEW_PASSWORD):
        r = c.post('/api/auth/reset/confirm', json={'email': email, 'code': '123456', 'new_password': pw})
        return r.status_code, r.json()['error']['code']
    assert attempt('known@example.com') == attempt('nobody@example.com') == (401, 'INVALID_RESET_CODE')  # was SECOND_FACTOR_REQUIRED for a real two-step account
    assert attempt('known@example.com', 'password123') == attempt('nobody@example.com', 'password123') == (422, 'PASSWORD_TOO_WEAK')
    # with the real code the second step is asked for, and asking does not burn the code
    limiter.reset()  # the per-minute request budget, not what is under test
    c.post('/api/auth/reset/request', json={'email': 'known@example.com'})
    code = code_from(outbox, 'known@example.com')
    body = {'email': 'known@example.com', 'code': code, 'new_password': NEW_PASSWORD}
    assert c.post('/api/auth/reset/confirm', json=body).json()['error']['code'] == 'SECOND_FACTOR_REQUIRED'
    assert c.post('/api/auth/reset/confirm', json={**body, 'second_factor': '000000'}).json()['error']['code'] == 'INVALID_CODE'


# ---- the owner's smart-assist switch also protects what teammates can send to the cloud model ----
def test_teammates_cannot_send_owner_records_to_the_model_when_the_owner_turned_it_off(world):
    c, _ = world
    signup(c, 'privacy_owner')
    code = c.post('/api/account/invitations', json={'role': 'viewer'}).json()['code']
    assert c.post('/api/account/profile', json={'smart_assist': False}).status_code == 200
    second_person(c, 'privacy_viewer')
    assert c.post('/api/account/join', json={'code': code}).status_code == 200
    r = c.post('/api/assist/ask', json={'question': 'How much cash do I have?'})
    assert r.status_code == 403 and r.json()['error']['code'] == 'WORKSPACE_OWNER_SMART_ASSIST_OFF'
    task = c.post('/api/agent/tasks', json={'task': 'Summarise my position', 'external_ai_consent': True})
    assert task.status_code == 403 and task.json()['error']['code'] == 'WORKSPACE_OWNER_SMART_ASSIST_OFF'  # the planner path is covered too
    login_as(c, 'privacy_owner')
    assert c.post('/api/account/profile', json={'smart_assist': True}).status_code == 200
    login_as(c, 'privacy_viewer')
    again = c.post('/api/assist/ask', json={'question': 'How much cash do I have?'})
    assert again.json()['error']['code'] != 'WORKSPACE_OWNER_SMART_ASSIST_OFF'  # allowed again (here it stops only because no model is configured)


# ---- someone removed from a workspace can be invited back ----
def test_a_removed_member_can_be_invited_again(world):
    c, _ = world
    owner = signup(c, 'again_owner')
    code = c.post('/api/account/invitations', json={'role': 'viewer'}).json()['code']
    second_person(c, 'again_helper')
    assert c.post('/api/account/join', json={'code': code}).status_code == 200
    login_as(c, 'again_owner')
    member = next(m for m in c.get('/api/account/members').json()['members'] if m['username'] == 'again_helper')
    assert c.post('/api/account/members/remove', json={'member_id': member['member_id']}).status_code == 200
    code2 = c.post('/api/account/invitations', json={'role': 'approver'}).json()['code']
    login_as(c, 'again_helper')
    back = c.post('/api/account/join', json={'code': code2})
    assert back.status_code == 200 and back.json()['role'] == 'approver' and back.json()['business_id'] == owner['business_id']
    login_as(c, 'again_owner')
    people = c.get('/api/account/members').json()['members']
    assert sorted(m['username'] for m in people) == ['again_helper', 'again_owner'] and next(m for m in people if m['username'] == 'again_helper')['role'] == 'approver'
    # an invitation can never change the owner's own seat
    code3 = c.post('/api/account/invitations', json={'role': 'viewer'}).json()['code']
    assert c.post('/api/account/join', json={'code': code3}).status_code == 409
    assert c.get('/api/account/members').json()['your_role'] == 'owner'


# ---- hashed email codes never fall back to a public key ----
def test_email_codes_refuse_to_work_without_a_signing_key(world, monkeypatch):
    from api.app import profile
    from api.app.security import PolicyError
    monkeypatch.delenv('SAFELEDGER_SIGNING_KEY')
    with pytest.raises(PolicyError):
        profile._code_hash('reset', 'a@example.com', '123456')
