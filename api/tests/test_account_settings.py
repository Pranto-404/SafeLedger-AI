"""Profile, photo, password change, email verification and reset codes, two-factor sign-in."""
import base64
import hashlib
import re
import time
import pytest
from api.tests.test_accounts import world, signup, PASSWORD
from api.app import mailer, mfa, accounts, profile

NEW_PASSWORD = 'amber orchard 4417 lighthouse'
PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 200).decode()


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, 'configured', lambda: True)
    monkeypatch.setattr(mailer, 'send', lambda to, subject, text: sent.append((to, subject, text)) or True)
    return sent


@pytest.fixture
def fast(monkeypatch):
    def cheap(password, salt=None):
        salt = salt or 'a' * 32
        return 'scrypt-v1$' + salt + '$' + hashlib.sha256((salt + password).encode()).hexdigest()
    monkeypatch.setattr(accounts, 'password_hash', cheap)
    monkeypatch.setattr(profile, 'password_hash', cheap)


def code_from(outbox, to):
    mail = [m for m in outbox if m[0] == to][-1]
    return re.search(r'\b(\d{6})\b', mail[2]).group(1)


def test_totp_matches_the_rfc_6238_test_vector():
    secret = base64.b32encode(b'12345678901234567890').decode().rstrip('=')
    assert mfa.code_at(secret, 59 // 30) == '287082'
    assert mfa.verify(secret, '287082', 0, now=59) == 1
    assert mfa.verify(secret, '287082', 1, now=59) is None  # a step can be used only once
    assert mfa.verify(secret, '000000', 0, now=59) is None and mfa.verify(secret, 'abc', 0, now=59) is None


def test_sealed_secret_round_trips_and_detects_tampering(world):
    s = mfa.new_secret()
    blob = mfa.seal(s)
    assert mfa.unseal(blob) == s and s not in blob
    with pytest.raises(ValueError):mfa.unseal(blob[:-2] + ('00' if blob[-2:] != '00' else '11'))


def test_profile_name_photo_and_smart_assist(world):
    c, _ = world
    signup(c, 'profile_user')
    p = c.get('/api/account/profile').json()
    assert p['username'] == 'profile_user' and p['display_name'] == '' and p['photo'] is None and p['smart_assist'] and not p['two_factor']
    assert c.post('/api/account/profile', json={'display_name': '  Rahim   Uddin  ', 'smart_assist': False}).status_code == 200
    assert c.get('/api/account/profile').json()['display_name'] == 'Rahim Uddin'
    assert c.get('/api/session').json()['display_name'] == 'Rahim Uddin'
    assert c.post('/api/account/photo', json={'image': 'data:image/png;base64,' + PNG}).status_code == 200
    assert c.get('/api/account/profile').json()['photo'].startswith('data:image/png;base64,')
    for bad in ['data:image/svg+xml;base64,' + PNG, 'data:image/png;base64,' + base64.b64encode(b'not an image at all, just text padding' * 4).decode(), 'javascript:alert(1)' + 'a' * 60, 'data:image/png;base64,' + base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 170_000).decode()]:
        assert c.post('/api/account/photo', json={'image': bad}).status_code == 422, bad[:40]
    assert c.post('/api/account/photo/remove', json={}).status_code == 200 and c.get('/api/account/profile').json()['photo'] is None
    assert c.post('/api/account/profile', json={'display_name': 'x' * 61}).status_code == 422


def test_change_password_revokes_other_sessions(world, fast):
    c, _ = world
    signup(c, 'pw_user')
    first_cookie = c.cookies.get('safeledger_session')
    c.post('/api/auth/logout', json={})
    c.post('/api/auth/login', json={'username': 'pw_user', 'password': PASSWORD})
    second_cookie = c.cookies.get('safeledger_session')
    assert c.post('/api/account/password', json={'current_password': 'wrong-password-1', 'new_password': NEW_PASSWORD}).json()['error']['code'] == 'CURRENT_PASSWORD_INCORRECT'
    assert c.post('/api/account/password', json={'current_password': PASSWORD, 'new_password': 'password123'}).json()['error']['code'] == 'PASSWORD_TOO_WEAK'
    assert c.post('/api/account/password', json={'current_password': PASSWORD, 'new_password': PASSWORD}).json()['error']['code'] == 'PASSWORD_UNCHANGED'
    assert c.post('/api/account/password', json={'current_password': PASSWORD, 'new_password': NEW_PASSWORD}).status_code == 200
    assert c.get('/api/session').status_code == 200  # this session survives
    c.cookies.set('safeledger_session', first_cookie)
    assert c.get('/api/session').status_code == 401  # the older session was signed out
    c.cookies.clear()
    assert c.post('/api/auth/login', json={'username': 'pw_user', 'password': PASSWORD}).status_code == 401
    assert c.post('/api/auth/login', json={'username': 'pw_user', 'password': NEW_PASSWORD}).status_code == 200


def test_email_verification_then_reset_by_code(world, fast, outbox):
    c, _ = world
    r = c.post('/api/auth/signup', json={'username': 'mail_user', 'password': PASSWORD, 'email': 'Owner@Example.com'})
    assert r.status_code == 201 and r.json()['email_verification_sent']
    assert c.get('/api/account/profile').json()['email'] == 'owner@example.com' and not c.get('/api/account/profile').json()['email_verified']
    # reset is impossible until the address is verified, and the answer never reveals that
    c.post('/api/auth/logout', json={})
    assert c.post('/api/auth/reset/request', json={'email': 'owner@example.com'}).json()['sent']
    assert not [m for m in outbox if 'reset' in m[2].lower()]
    c.post('/api/auth/login', json={'username': 'mail_user', 'password': PASSWORD})
    assert c.post('/api/account/email/verify', json={'code': '000000'}).status_code == 401
    assert c.post('/api/account/email/verify', json={'code': code_from(outbox, 'owner@example.com')}).status_code == 200
    assert c.get('/api/account/profile').json()['email_verified']
    c.post('/api/auth/logout', json={})
    outbox.clear()
    assert c.post('/api/auth/reset/request', json={'email': 'nobody@example.com'}).json()['sent'] and not outbox
    assert c.post('/api/auth/reset/request', json={'email': 'owner@example.com'}).json()['sent']
    code = code_from(outbox, 'owner@example.com')
    bad = {'email': 'owner@example.com', 'code': '123456' if code != '123456' else '654321', 'new_password': NEW_PASSWORD}
    assert c.post('/api/auth/reset/confirm', json=bad).status_code == 401
    assert c.post('/api/auth/reset/confirm', json={**bad, 'code': code, 'new_password': 'password123'}).status_code == 422
    assert c.post('/api/auth/reset/confirm', json={**bad, 'code': code}).status_code == 200
    assert c.post('/api/auth/reset/confirm', json={**bad, 'code': code}).status_code == 401  # a code works once
    assert c.post('/api/auth/login', json={'username': 'mail_user', 'password': PASSWORD}).status_code == 401
    assert c.post('/api/auth/login', json={'username': 'mail_user', 'password': NEW_PASSWORD}).status_code == 200


def test_reset_code_locks_after_five_wrong_guesses(world, fast, outbox):
    c, _ = world
    c.post('/api/auth/signup', json={'username': 'guess_user', 'password': PASSWORD, 'email': 'guess@example.com'})
    c.post('/api/account/email/verify', json={'code': code_from(outbox, 'guess@example.com')})
    c.post('/api/auth/logout', json={})
    c.post('/api/auth/reset/request', json={'email': 'guess@example.com'})
    good = code_from(outbox, 'guess@example.com')
    wrong = '111111' if good != '111111' else '222222'
    results = [c.post('/api/auth/reset/confirm', json={'email': 'guess@example.com', 'code': wrong, 'new_password': NEW_PASSWORD}).status_code for _ in range(6)]
    assert results[:5] == [401] * 5 and results[5] == 429
    assert c.post('/api/auth/reset/confirm', json={'email': 'guess@example.com', 'code': good, 'new_password': NEW_PASSWORD}).status_code == 429


def test_reset_requires_email_service_and_is_rate_limited(world, outbox, monkeypatch):
    c, _ = world
    codes = [c.post('/api/auth/reset/request', json={'email': 'same@example.com'}).status_code for _ in range(4)]
    assert codes == [200] * 4 and len([m for m in outbox if m[0] == 'same@example.com']) == 0  # unregistered: nothing is sent
    monkeypatch.setattr(mailer, 'configured', lambda: False)
    assert c.post('/api/auth/reset/request', json={'email': 'x@example.com'}).json()['error']['code'] == 'EMAIL_NOT_CONFIGURED'
    assert c.get('/api/auth/capabilities').json()['email_codes'] is False


def test_two_factor_setup_login_backup_code_and_disable(world, fast):
    c, _ = world
    signup(c, 'mfa_user')
    assert c.post('/api/account/2fa/setup', json={'password': 'wrong-password-1'}).status_code == 401
    setup = c.post('/api/account/2fa/setup', json={'password': PASSWORD}).json()
    secret = setup['secret']
    assert setup['uri'].startswith('otpauth://totp/Capzoryx%20Copilot:mfa_user?secret=' + secret)
    assert c.post('/api/account/2fa/enable', json={'code': '000000'}).status_code == 401
    step = int(time.time() // 30)
    enable = c.post('/api/account/2fa/enable', json={'code': mfa.code_at(secret, step)})
    assert enable.status_code == 200 and len(enable.json()['backup_codes']) == 10
    backups = enable.json()['backup_codes']
    assert c.get('/api/account/profile').json()['two_factor']
    c.post('/api/auth/logout', json={})
    # password alone no longer signs in
    first = c.post('/api/auth/login', json={'username': 'mfa_user', 'password': PASSWORD})
    assert first.status_code == 200 and first.json()['mfa_required'] and 'safeledger_session' not in c.cookies
    assert c.get('/api/session').status_code == 401
    challenge = first.json()['challenge']
    assert c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': '000000'}).status_code == 401
    # the code used to enable cannot be replayed; the next time step works
    assert c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': mfa.code_at(secret, step)}).status_code == 401
    ok = c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': mfa.code_at(secret, step + 1)})
    assert ok.status_code == 200 and ok.json()['username'] == 'mfa_user' and c.get('/api/session').status_code == 200
    assert c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': mfa.code_at(secret, step + 1)}).status_code == 401  # challenge is single use
    # backup code signs in once
    c.post('/api/auth/logout', json={})
    challenge = c.post('/api/auth/login', json={'username': 'mfa_user', 'password': PASSWORD}).json()['challenge']
    assert c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': backups[0]}).status_code == 200
    c.post('/api/auth/logout', json={})
    challenge = c.post('/api/auth/login', json={'username': 'mfa_user', 'password': PASSWORD}).json()['challenge']
    assert c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': backups[0]}).status_code == 401
    assert c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': backups[1]}).status_code == 200
    # disabling needs the password and a valid factor
    assert c.post('/api/account/2fa/disable', json={'password': PASSWORD, 'code': '000000'}).status_code == 401
    assert c.post('/api/account/2fa/disable', json={'password': PASSWORD, 'code': backups[2]}).status_code == 200
    c.post('/api/auth/logout', json={})
    assert 'mfa_required' not in c.post('/api/auth/login', json={'username': 'mfa_user', 'password': PASSWORD}).json()


def test_two_factor_challenge_is_bounded(world, fast):
    c, _ = world
    signup(c, 'brute_user')
    secret = c.post('/api/account/2fa/setup', json={'password': PASSWORD}).json()['secret']
    c.post('/api/account/2fa/enable', json={'code': mfa.code_at(secret, int(time.time() // 30))})
    c.post('/api/auth/logout', json={})
    challenge = c.post('/api/auth/login', json={'username': 'brute_user', 'password': PASSWORD}).json()['challenge']
    results = [c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': '%06d' % (100000 + i)}).status_code for i in range(7)]
    assert results[:5] == [401] * 5 and set(results[5:]) == {401}
    assert c.post('/api/auth/login/2fa', json={'challenge': challenge, 'code': mfa.code_at(secret, int(time.time() // 30) + 1)}).status_code == 401  # challenge burned


def test_reset_with_two_factor_needs_the_second_factor(world, fast, outbox):
    c, _ = world
    c.post('/api/auth/signup', json={'username': 'both_user', 'password': PASSWORD, 'email': 'both@example.com'})
    c.post('/api/account/email/verify', json={'code': code_from(outbox, 'both@example.com')})
    secret = c.post('/api/account/2fa/setup', json={'password': PASSWORD}).json()['secret']
    step = int(time.time() // 30)
    c.post('/api/account/2fa/enable', json={'code': mfa.code_at(secret, step)})
    c.post('/api/auth/logout', json={})
    c.post('/api/auth/reset/request', json={'email': 'both@example.com'})
    code = code_from(outbox, 'both@example.com')
    body = {'email': 'both@example.com', 'code': code, 'new_password': NEW_PASSWORD}
    assert c.post('/api/auth/reset/confirm', json=body).json()['error']['code'] == 'SECOND_FACTOR_REQUIRED'
    assert c.post('/api/auth/reset/confirm', json={**body, 'second_factor': mfa.code_at(secret, step + 1)}).status_code == 200
