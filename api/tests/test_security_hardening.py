"""Security hardening found in the 20 Oct review: spoofable client IP, weak lockout, weak passwords, stale sessions."""
import hashlib
import itertools
import sqlite3
from types import SimpleNamespace
import pytest
from api.tests.test_accounts import world, signup, HEADERS, PASSWORD
from api.app import accounts, security as sec

counter = itertools.count(1)


@pytest.fixture
def fast(monkeypatch):
    """Cheap deterministic hash so abuse tests do not spend seconds in scrypt; auth logic is unchanged."""
    def cheap(password, salt=None):
        salt = salt or 'a' * 32
        return 'scrypt-v1$' + salt + '$' + hashlib.sha256((salt + password).encode()).hexdigest()
    monkeypatch.setattr(accounts, 'password_hash', cheap)


def from_edge(edge, spoof=None):
    """Headers a request carries after Vercel/Cloudflare: infrastructure address plus a forgeable chain."""
    return {'cf-connecting-ip': edge, 'x-forwarded-for': spoof or f'203.0.{next(counter) % 250}.{next(counter) % 250}'}


def login(c, name, password, edge, spoof=None):
    return c.post('/api/auth/login', json={'username': name, 'password': password}, headers=from_edge(edge, spoof))


def test_client_keys_ignore_forged_left_side_of_forwarded_chain():
    def request(**headers):
        return SimpleNamespace(headers={k.replace('_', '-'): v for k, v in headers.items()}, client=SimpleNamespace(host='10.0.0.9'))
    a_claimed, a_edge = sec.client_keys(request(cf_connecting_ip='198.51.100.7', x_forwarded_for='1.1.1.1, 2.2.2.2'))
    b_claimed, b_edge = sec.client_keys(request(cf_connecting_ip='198.51.100.7', x_forwarded_for='9.9.9.9'))
    assert a_edge == b_edge and a_claimed != b_claimed
    _, only_chain_edge = sec.client_keys(request(x_forwarded_for='6.6.6.6, 198.51.100.8'))
    assert only_chain_edge == sec.client_keys(request(x_forwarded_for='7.7.7.7, 198.51.100.8'))[1]
    assert sec.client_keys(request())[0] == sec.client_keys(request())[1]  # no headers: socket peer for both
    long_garbage = ','.join(['x' * 500] * 50)
    assert all(len(v) == 32 for v in sec.client_keys(request(x_forwarded_for=long_garbage)))


def test_password_guessing_stops_even_when_forwarded_for_is_forged(world, fast):
    c, _ = world
    signup(c, 'target_person'); c.post('/api/auth/logout', json={})
    codes = [login(c, 'target_person', 'wrong-password-%d' % i, '198.51.100.20').status_code for i in range(10)]
    assert codes[:8] == [401] * 8 and codes[8:] == [429, 429], codes
    # Even the correct password is refused from that address until the window passes: no oracle during lockout.
    assert login(c, 'target_person', PASSWORD, '198.51.100.20').status_code == 429


def test_single_attacker_cannot_lock_the_owner_out(world, fast):
    c, _ = world
    signup(c, 'victim_owner'); c.post('/api/auth/logout', json={})
    for i in range(12):
        login(c, 'victim_owner', 'guess-%d' % i, '198.51.100.30')
    ok = login(c, 'victim_owner', PASSWORD, '203.0.113.50')
    assert ok.status_code == 200 and ok.json()['username'] == 'victim_owner'


def test_distributed_guessing_hits_per_account_ceiling(world, fast):
    c, _ = world
    signup(c, 'popular_target'); c.post('/api/auth/logout', json={})
    results = [login(c, 'popular_target', 'wrong-guess-%d' % i, f'192.0.2.{i + 1}').status_code for i in range(45)]
    assert results[:40] == [401] * 40 and set(results[40:]) == {429}
    assert login(c, 'popular_target', PASSWORD, '192.0.2.200').status_code == 429


def test_signup_flood_is_limited_per_edge_despite_rotating_forwarded_for(world, fast):
    c, _ = world
    codes = []
    for i in range(23):
        r = c.post('/api/auth/signup', json={'username': 'flood_%02d' % i, 'password': PASSWORD}, headers=from_edge('198.51.100.40'))
        codes.append(r.status_code)
    assert codes[:20] == [201] * 20 and codes[20:] == [429] * 3, codes
    assert c.post('/api/auth/signup', json={'username': 'honest_user', 'password': PASSWORD}, headers=from_edge('203.0.113.77')).status_code == 201


def test_same_claimed_user_is_limited_to_four_signups_per_minute(world, fast):
    c, _ = world
    codes = [c.post('/api/auth/signup', json={'username': 'same_%d' % i, 'password': PASSWORD}, headers=from_edge('198.51.100.%d' % (60 + i), '203.0.113.9')).status_code for i in range(6)]
    assert codes == [201] * 4 + [429] * 2


def test_unauthenticated_probe_flood_is_limited_per_edge(world):
    c, _ = world
    spoofed = [c.get('/api/session', headers=from_edge('198.51.100.90')).status_code for _ in range(25)]
    assert set(spoofed) == {401}  # rotating forged chain stays under the generous edge ceiling
    same = [c.get('/api/session', headers=from_edge('198.51.100.91', '192.0.2.1')).status_code for _ in range(22)]
    assert same[:20] == [401] * 20 and same[20:] == [429, 429]


@pytest.mark.parametrize('password', ['password', 'Password123', 'PASSWORD1', '12345678', 'aaaaaaaa', 'abababab', 'safeledger', 'Capzoryx', '1q2w3e4r', 'qwertyuiop', 'weak_user'])
def test_common_and_username_passwords_rejected(world, password):
    c, _ = world
    r = c.post('/api/auth/signup', json={'username': 'weak_user', 'password': password})
    assert r.status_code == 422 and r.json()['error']['fields'][0]['type'] == 'value_error', r.text


def test_strong_passwords_and_exact_whitespace_still_accepted(world):
    c, _ = world
    for i, password in enumerate(['correct horse battery staple', ' spaced pass 99 ', 'Tr0ub4dor&3-x', 'ঢাকা-ব্যবসা-২০২৬!']):
        assert c.post('/api/auth/signup', json={'username': 'strong_%d' % i, 'password': password}, headers=from_edge('198.51.100.%d' % (100 + i))).status_code == 201, password


def test_login_never_applies_the_weak_password_policy(world, fast):
    """Existing accounts with older weak passwords must still be able to sign in and then change it."""
    c, path = world
    signup(c, 'legacy_user'); c.post('/api/auth/logout', json={})
    with sqlite3.connect(path) as db:
        db.execute('UPDATE auth_accounts SET password_hash=? WHERE username=?', (accounts.password_hash('password123'), 'legacy_user'))
    assert c.post('/api/auth/login', json={'username': 'legacy_user', 'password': 'password123'}).status_code == 200


def test_recovery_guessing_is_locked_and_new_password_must_be_strong(world, fast):
    c, _ = world
    created = signup(c, 'recoverable_user'); c.post('/api/auth/logout', json={})
    body = lambda code, pw=PASSWORD: {'username': 'recoverable_user', 'password': pw, 'recovery_code': code}
    assert c.post('/api/auth/recover', json=body(created['recovery_code'], 'password123'), headers=from_edge('198.51.100.120')).status_code == 422
    wrong = [c.post('/api/auth/recover', json=body('x' * 30), headers=from_edge('198.51.100.121')).status_code for _ in range(7)]
    assert wrong == [401] * 5 + [429] * 2
    assert c.post('/api/auth/recover', json=body(created['recovery_code']), headers=from_edge('203.0.113.121')).status_code == 200


def test_expired_sessions_are_removed_on_login(world, fast):
    c, path = world
    signup(c, 'tidy_user'); c.post('/api/auth/logout', json={})
    with sqlite3.connect(path) as db:
        user = db.execute('SELECT user_id FROM security_sessions UNION SELECT user_id FROM security_users LIMIT 1').fetchone()[0]
        db.executemany('INSERT INTO security_sessions VALUES (?,?,?)', [(hashlib.sha256(b'old%d' % i).hexdigest(), user, 1) for i in range(5)])
    assert login(c, 'tidy_user', PASSWORD, '198.51.100.130').status_code == 200
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM security_sessions WHERE expires_at<?', (sec.now(),)).fetchone()[0] == 0


def test_failed_attempt_rows_are_bounded_and_pruned(world, fast):
    c, path = world
    signup(c, 'bounded_user'); c.post('/api/auth/logout', json={})
    login(c, 'bounded_user', 'bad-guess', '198.51.100.140')
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO auth_failures VALUES ('old-scope',1,5)")
    login(c, 'bounded_user', 'bad-guess-2', '198.51.100.141')
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM auth_failures WHERE scope='old-scope'").fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM auth_failures').fetchone()[0] <= 6


@pytest.mark.parametrize('platform', ['RENDER', 'VERCEL'])
def test_hosted_start_fails_closed_without_persistent_database(monkeypatch, tmp_path, platform):
    from api.app.database import connect
    for key in ('RENDER', 'VERCEL', 'TURSO_DATABASE_URL', 'TURSO_AUTH_TOKEN', 'SAFELEDGER_ALLOW_EPHEMERAL_DB'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('SAFELEDGER_DB', str(tmp_path / 'x.sqlite3'))
    monkeypatch.setenv(platform, '1' if platform == 'VERCEL' else 'true')
    with pytest.raises(sqlite3.DatabaseError):
        connect()
    monkeypatch.setenv('SAFELEDGER_ALLOW_EPHEMERAL_DB', '1')
    connect().close()  # explicit, deliberate override for disposable environments only
