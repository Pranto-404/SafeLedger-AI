"""Sign-in reliability: case-insensitive usernames, keep-me-signed-in lifetime, lockout behaviour, no enumeration."""
import sqlite3
import time

from api.app import accounts, mfa, security as sec
from api.app.ratelimit import limiter
from api.tests.test_accounts import world, signup, PASSWORD, COOKIE
from api.tests.test_account_settings import fast
from api.tests.test_security_hardening import login, from_edge


def cookie_max_age(response):
    header=response.headers['set-cookie']
    return int(next(p.split('=')[1] for p in header.split(';') if p.strip().lower().startswith('max-age')))


def session_expiry(path, token):
    import hashlib
    with sqlite3.connect(path) as db:
        return db.execute('SELECT expires_at FROM security_sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()[0]


def test_any_capitalisation_and_stray_spaces_sign_in(world):
    c, _ = world
    signup(c, 'Mixed_Case_9'); c.post('/api/auth/logout', json={})
    for typed in ('Mixed_Case_9', 'MIXED_CASE_9', 'mixed_case_9', '  Mixed_case_9  '):
        r = c.post('/api/auth/login', json={'username': typed, 'password': PASSWORD})
        assert r.status_code == 200 and r.json()['username'] == 'mixed_case_9', typed
        c.post('/api/auth/logout', json={})


def test_signup_collision_is_case_insensitive_even_without_the_validator(world):
    c, path = world
    signup(c, 'Taken_Name')
    assert c.post('/api/auth/signup', json={'username': 'TAKEN_name', 'password': PASSWORD}).status_code == 409
    # The database itself refuses a case variant, independent of application code.
    with sqlite3.connect(path) as db:
        try:
            db.execute("INSERT INTO auth_accounts VALUES ('x','TAKEN_NAME','h',1)")
            raised = False
        except sqlite3.IntegrityError:
            raised = True
    assert raised


def test_login_format_mistakes_are_ordinary_wrong_credentials(world):
    c, _ = world
    signup(c, 'format_user'); c.post('/api/auth/logout', json={})
    for typed in ('format user', 'format_user@example.com', 'x', 'é' * 5):
        r = c.post('/api/auth/login', json={'username': typed, 'password': PASSWORD})
        assert r.status_code == 401 and r.json() == {'error': {'code': 'INVALID_USERNAME_OR_PASSWORD'}}, typed


def test_migration_lowercases_legacy_rows_and_reports_collisions(world, caplog):
    c, path = world
    with sqlite3.connect(path) as db:
        db.execute('DROP INDEX IF EXISTS auth_accounts_username_nocase')
        db.executemany("INSERT INTO auth_accounts VALUES (?,?,?,?)", [('a1', 'Legacy_One', 'h', 1), ('a2', 'dup_name', 'h', 2), ('a3', 'DUP_NAME', 'h', 3)])
        accounts.canonicalize_usernames(db)
        names = dict(db.execute('SELECT account_id,username FROM auth_accounts').fetchall())
    assert names['a1'] == 'legacy_one' and names['a2'] == 'dup_name' and names['a3'] == 'DUP_NAME'  # collision untouched
    assert 'Username collision' in caplog.text


def test_keep_me_signed_in_lifetime_and_cookie_match(world):
    c, path = world
    signup(c, 'remember_me'); c.post('/api/auth/logout', json={})
    short = c.post('/api/auth/login', json={'username': 'remember_me', 'password': PASSWORD})
    assert cookie_max_age(short) == 86400
    left = session_expiry(path, c.cookies.get(COOKIE)) - sec.now()
    assert 86300 < left <= 86400
    long = c.post('/api/auth/login', json={'username': 'remember_me', 'password': PASSWORD, 'remember': True})
    assert cookie_max_age(long) == 30 * 86400
    left = session_expiry(path, c.cookies.get(COOKIE)) - sec.now()
    assert 30 * 86400 - 100 < left <= 30 * 86400
    header = long.headers['set-cookie'].lower()
    assert 'httponly' in header and 'samesite=lax' in header
    # Switching or adding a workspace must not downgrade a long session to 24 hours.
    made = c.post('/api/account/workspaces', json={'name': 'Second', 'currency': 'USD'})
    assert made.status_code == 201 and cookie_max_age(made) > 29 * 86400
    assert c.post('/api/auth/login', json={'username': 'remember_me', 'password': PASSWORD, 'remember': 'yes please'}).status_code == 422


def test_logout_and_password_change_revoke_long_sessions(world):
    c, path = world
    signup(c, 'revoke_me'); c.post('/api/auth/logout', json={})
    def alive(token):
        return c.get('/api/session', headers={'Cookie': COOKIE + '=' + token}).status_code == 200
    c.post('/api/auth/login', json={'username': 'revoke_me', 'password': PASSWORD, 'remember': True})
    token = c.cookies.get(COOKIE)
    assert alive(token)
    assert c.post('/api/auth/logout', json={}).status_code == 200
    assert not alive(token)  # the server forgot it, not just the browser
    # Password change signs out every other long session.
    c.cookies.clear()
    c.post('/api/auth/login', json={'username': 'revoke_me', 'password': PASSWORD, 'remember': True})
    first = c.cookies.get(COOKIE)
    c.cookies.clear()
    c.post('/api/auth/login', json={'username': 'revoke_me', 'password': PASSWORD})
    assert alive(first)
    assert c.post('/api/account/password', json={'current_password': PASSWORD, 'new_password': PASSWORD + '-changed'}).status_code == 200
    assert not alive(first)


def test_two_step_login_honours_keep_me_signed_in(world, fast):
    c, _ = world
    signup(c, 'two_step_user')
    setup = c.post('/api/account/2fa/setup', json={'password': PASSWORD})
    assert setup.status_code == 200, setup.text
    secret = setup.json()['secret']
    step = int(time.time() // 30)
    enabled = c.post('/api/account/2fa/enable', json={'code': mfa.code_at(secret, step)})
    assert enabled.status_code == 200
    backup = enabled.json()['backup_codes'][0]
    c.post('/api/auth/logout', json={})
    r = c.post('/api/auth/login', json={'username': 'two_step_user', 'password': PASSWORD, 'remember': True})
    assert r.json()['mfa_required'] is True and 'set-cookie' not in r.headers
    done = c.post('/api/auth/login/2fa', json={'challenge': r.json()['challenge'], 'code': mfa.code_at(secret, step + 1), 'remember': True})
    assert done.status_code == 200 and cookie_max_age(done) == 30 * 86400
    c.post('/api/auth/logout', json={})
    r = c.post('/api/auth/login', json={'username': 'two_step_user', 'password': PASSWORD})
    done = c.post('/api/auth/login/2fa', json={'challenge': r.json()['challenge'], 'code': backup})
    assert done.status_code == 200 and cookie_max_age(done) == 86400


def test_failed_attempts_report_how_long_to_wait_and_success_resets_the_pair(world, fast):
    c, _ = world
    signup(c, 'patient_user'); c.post('/api/auth/logout', json={})
    for i in range(7):
        assert login(c, 'patient_user', 'wrong-%d' % i, '198.51.100.120').status_code == 401
    assert login(c, 'patient_user', PASSWORD, '198.51.100.120').status_code == 200  # success clears this client's count
    c.post('/api/auth/logout', json={})
    for i in range(8):
        login(c, 'patient_user', 'wrong-%d' % i, '198.51.100.120')
    locked = login(c, 'patient_user', PASSWORD, '198.51.100.120')
    assert locked.status_code == 429
    wait = locked.json()['error']['retry_after']
    assert 1 <= wait <= 15 * 60 + 60 and locked.headers['Retry-After'] == str(wait)


def test_lockout_wait_shrinks_as_time_passes(world, fast, monkeypatch):
    c, _ = world
    signup(c, 'clock_user'); c.post('/api/auth/logout', json={})
    clock = [time.time()]
    monkeypatch.setattr(limiter, '_clock', lambda: clock[0])
    for i in range(8):
        login(c, 'clock_user', 'wrong-%d' % i, '198.51.100.130')
    first = login(c, 'clock_user', PASSWORD, '198.51.100.130').json()['error']['retry_after']
    clock[0] += 10 * 60
    second = login(c, 'clock_user', PASSWORD, '198.51.100.130')
    assert second.status_code == 429 and second.json()['error']['retry_after'] < first
    clock[0] += 16 * 60
    assert login(c, 'clock_user', PASSWORD, '198.51.100.130').status_code == 200


def test_attacker_slowing_one_account_does_not_shut_the_owner_out(world, fast, monkeypatch):
    c, _ = world
    signup(c, 'slowed_owner'); c.post('/api/auth/logout', json={})
    clock = [time.time()]
    monkeypatch.setattr(limiter, '_clock', lambda: clock[0])
    for i in range(45):
        login(c, 'slowed_owner', 'guess-%d' % i, f'192.0.2.{i + 1}')
    blocked = login(c, 'slowed_owner', PASSWORD, '203.0.113.150')
    assert blocked.status_code == 429
    clock[0] += blocked.json()['error']['retry_after'] + 1
    ok = login(c, 'slowed_owner', PASSWORD, '203.0.113.150')
    assert ok.status_code == 200  # the owner gets through after a short wait, not after 15 minutes


def test_no_account_enumeration_in_errors_or_lockouts(world, fast):
    c, _ = world
    signup(c, 'real_account'); c.post('/api/auth/logout', json={})
    real = [login(c, 'real_account', 'bad-%d' % i, '198.51.100.140') for i in range(10)]
    ghost = [login(c, 'ghost_account', 'bad-%d' % i, '198.51.100.141') for i in range(10)]
    assert [r.status_code for r in real] == [r.status_code for r in ghost]
    assert [r.json().get('error', {}).get('code') for r in real[:8]] == ['INVALID_USERNAME_OR_PASSWORD'] * 8
    assert all(r.json()['error']['code'] == 'TOO_MANY_FAILED_ATTEMPTS' for r in real[8:] + ghost[8:])
    # Same body for case variants of a missing or present account.
    a = c.post('/api/auth/login', json={'username': 'REAL_ACCOUNT', 'password': 'bad-password-x'}, headers=from_edge('198.51.100.142'))
    b = c.post('/api/auth/login', json={'username': 'GHOST_ACCOUNT', 'password': 'bad-password-x'}, headers=from_edge('198.51.100.143'))
    assert a.status_code == b.status_code == 401 and a.json() == b.json()
