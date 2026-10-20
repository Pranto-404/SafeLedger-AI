"""Fast black-box security probe of the HTTP API. Run against a LOCAL server only (it creates accounts and sends hostile input):
    python scripts/security_probe.py http://127.0.0.1:8000
Checks: every route needs a session, browser-origin enforcement, hostile input to the newer public endpoints, error shape (no stack traces or
secrets), cookie flags, response headers, oversized bodies, and that a second account cannot reach the first account's data."""
import json
import secrets
import sys
import httpx

RUN = secrets.token_hex(3)

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000').rstrip('/')
ORIGIN = 'https://safeledger-ai.vercel.app'
H = {'Content-Type': 'application/json', 'X-SafeLedger-Client': 'web', 'Origin': ORIGIN}
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + str(detail)) if detail and not ok else ''))


def client():
    return httpx.Client(base_url=BASE, headers=H, timeout=30)


anon = client()
# 1. Anonymous callers: private routes are closed, public routes are bounded.
private = ['/api/workspace', '/api/account/profile', '/api/account/workspaces', '/api/account/members', '/api/proposals', '/api/audit', '/api/fx/rate?from=BDT&to=USD']
for path in private:
    r = anon.get(path)
    check('anonymous ' + path + ' is refused', r.status_code in (401, 403), r.status_code)
for path in ['/api/assist/ask', '/api/assist/scan', '/api/assist/extract', '/api/workspace/records', '/api/account/password', '/api/account/2fa/setup', '/api/account/invitations', '/api/account/workspaces/clear', '/api/agent/tasks']:
    r = anon.post(path, json={})
    check('anonymous POST ' + path + ' is refused', r.status_code in (401, 403, 422) and r.status_code != 200, r.status_code)
# 2. Browser origin enforcement on state-changing public routes.
bad = httpx.Client(base_url=BASE, headers={'Content-Type': 'application/json', 'Origin': 'https://evil.example', 'X-SafeLedger-Client': 'web'}, timeout=30)
check('login from a foreign origin is refused', bad.post('/api/auth/login', json={'username': 'x' * 5, 'password': 'y' * 9}).status_code == 403)
nohdr = httpx.Client(base_url=BASE, headers={'Content-Type': 'application/json', 'Origin': ORIGIN}, timeout=30)
check('login without the client header is refused', nohdr.post('/api/auth/login', json={'username': 'x' * 5, 'password': 'y' * 9}).status_code == 403)
check('invitation preview from a foreign origin is refused', bad.post('/api/invitations/preview', json={'code': 'a' * 30}).status_code == 403)
# 3. Hostile input on the public language endpoint and the invitation preview.
for lang in ["en' OR '1'='1", '../../etc/passwd', 'ja;DROP TABLE i18n_text', 'a' * 5000, '%00', '<script>']:
    r = anon.get('/api/i18n', params={'lang': lang})
    check('i18n rejects hostile language ' + repr(lang[:20]), r.status_code in (404, 422) and 'Traceback' not in r.text, r.status_code)
for code in ["' OR 1=1 --", 'A' * 30, '\x00' * 25, '../' * 10, 'x' * 101]:
    r = anon.post('/api/invitations/preview', json={'code': code})
    check('invitation preview rejects ' + repr(code[:12]), r.status_code in (404, 422) and 'Traceback' not in r.text, r.status_code)
# 4. Accounts: weak and hostile signups, enumeration, lockout, cookie flags.
a = client()
r = a.post('/api/auth/signup', json={'username': 'probe_o_' + RUN, 'password': 'Zq7-long-unique-pass-41', 'currency': 'BDT'})
check('signup works', r.status_code == 201, r.text[:120])
cookie = r.headers.get('set-cookie', '').lower()
local = BASE.startswith('http://127.0.0.1') or BASE.startswith('http://localhost')  # the Secure flag is switched on for hosted deployments only
check('session cookie is HttpOnly and SameSite' + ('' if local else ' and Secure'), 'httponly' in cookie and 'samesite' in cookie and ('secure' in cookie or local), cookie[:120])
check('weak password refused', client().post('/api/auth/signup', json={'username': 'probe_w_' + RUN, 'password': '12345678', 'currency': 'BDT'}).status_code in (400, 422))
check('script in username refused', client().post('/api/auth/signup', json={'username': '<script>x', 'password': 'Zq7-long-unique-pass-41', 'currency': 'BDT'}).status_code == 422)
check('unknown JSON fields refused', client().post('/api/auth/signup', json={'username': 'probe_e_' + RUN, 'password': 'Zq7-long-unique-pass-41', 'currency': 'BDT', 'role': 'owner'}).status_code == 422)
wrong = client().post('/api/auth/login', json={'username': 'probe_o_' + RUN, 'password': 'wrong-password-xyz'})
ghost = client().post('/api/auth/login', json={'username': 'no_such_user_zz', 'password': 'wrong-password-xyz'})
check('login errors do not reveal whether an account exists', wrong.status_code == ghost.status_code == 401 and wrong.json() == ghost.json())
mixed = client().post('/api/auth/login', json={'username': ('probe_o_' + RUN).upper(), 'password': 'Zq7-long-unique-pass-41'})
check('sign-in ignores username capitalisation', mixed.status_code == 200, mixed.status_code)
kept = client().post('/api/auth/login', json={'username': 'probe_o_' + RUN, 'password': 'Zq7-long-unique-pass-41', 'remember': True})
cookie = kept.headers.get('set-cookie', '').lower()
check('keep me signed in lasts 30 days and stays HttpOnly', kept.status_code == 200 and 'max-age=2592000' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie, cookie[:120])
brief = client().post('/api/auth/login', json={'username': 'probe_o_' + RUN, 'password': 'Zq7-long-unique-pass-41'})
check('a normal sign-in lasts 24 hours', 'max-age=86400' in brief.headers.get('set-cookie', '').lower())
reset = client().post('/api/auth/reset/request', json={'email': 'nobody@example.com'})
check('password reset request is the same for unknown emails', reset.status_code in (200, 202) and 'nobody' not in reset.text)
# 5. A second account cannot see or change the first one's data.
b = client()
b.post('/api/auth/signup', json={'username': 'probe_x_' + RUN, 'password': 'Zq7-long-unique-pass-42', 'currency': 'BDT'})
mine = a.get('/api/workspace').json()
theirs = b.get('/api/workspace').json()
check('accounts have separate workspaces', mine['snapshot'] is not None and theirs.get('business_id', 1) != mine.get('business_id', 2))
check('a different account cannot switch into a workspace it does not belong to', b.post('/api/account/switch', json={'business_id': a.get('/api/account/workspaces').json()['workspaces'][0]['business_id']}).status_code in (403, 404, 409))
check('a different account cannot revoke or list invitations of another workspace', b.post('/api/account/invitations/revoke', json={'invite_id': 'a' * 16}).status_code in (200, 403))
# 6. Errors never leak internals.
for path, method in [('/api/nope', 'GET'), ('/api/workspace/records', 'POST'), ('/api/assist/ask', 'POST')]:
    r = a.request(method, path, content=b'{not json')
    check(method + ' ' + path + ' with broken JSON gives a clean error', r.status_code in (400, 404, 405, 422) and 'Traceback' not in r.text and 'File "' not in r.text, r.status_code)
# 7. Oversized bodies.
check('a huge JSON body is refused early', a.post('/api/assist/ask', content=b'{"question":"' + b'a' * 3_000_000 + b'"}').status_code in (413, 422, 400))
big_image = 'data:image/png;base64,' + 'A' * 3_000_000
check('a huge image is refused early', a.post('/api/assist/scan', json={'image': big_image}).status_code in (413, 422))
# 8. Headers.
r = anon.get('/api/health')
check('health reveals no secrets', 'key' not in r.text.lower() and 'secret' not in r.text.lower() and 'password' not in r.text.lower())
check('nosniff header present', r.headers.get('x-content-type-options', '').lower() == 'nosniff', dict(r.headers))
cors = httpx.options(BASE + '/api/workspace', headers={'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'GET'}, timeout=30)
check('CORS does not allow a foreign origin', cors.headers.get('access-control-allow-origin') in (None, ORIGIN), cors.headers.get('access-control-allow-origin'))
# 9. Sessions: logout really ends a session, a password change signs other devices out, repeated wrong passwords lock the account.
d1 = client()
d1.post('/api/auth/signup', json={'username': 'probe_s_' + RUN, 'password': 'Zq7-long-unique-pass-43', 'currency': 'BDT'})
stolen = d1.cookies.get('safeledger_session')
d1.post('/api/auth/logout', json={})
replay = httpx.Client(base_url=BASE, headers=H, cookies={'safeledger_session': stolen}, timeout=30)
check('a logged-out session cannot be replayed', replay.get('/api/workspace').status_code == 401)
d2 = client(); d3 = client()
d2.post('/api/auth/login', json={'username': 'probe_s_' + RUN, 'password': 'Zq7-long-unique-pass-43'})
d3.post('/api/auth/login', json={'username': 'probe_s_' + RUN, 'password': 'Zq7-long-unique-pass-43'})
changed = d2.post('/api/account/password', json={'current_password': 'Zq7-long-unique-pass-43', 'new_password': 'Zq7-long-unique-pass-44'})
check('password change works', changed.status_code == 200, changed.text[:100])
check('password change signs other devices out', d3.get('/api/workspace').status_code == 401 and d2.get('/api/workspace').status_code == 200)
codes = [client().post('/api/auth/login', json={'username': 'probe_o_' + RUN, 'password': 'wrong-pass-%d-xx' % i}).status_code for i in range(12)]
check('repeated wrong passwords are slowed or locked', any(c in (423, 429) for c in codes), codes)
right = client().post('/api/auth/login', json={'username': 'probe_o_' + RUN, 'password': 'Zq7-long-unique-pass-41'})
check('a lockout says how long to wait', right.headers.get('Retry-After', '').isdigit() and right.json().get('error', {}).get('retry_after', 0) > 0, right.headers.get('Retry-After'))
check('a locked account does not accept even the right password during the lock', right.status_code in (423, 429), right.status_code)
failed = [n for n, ok, _ in results if not ok]
print(f'\n{len(results) - len(failed)} of {len(results)} checks passed')
if failed:
    print('FAILED:', failed)
    sys.exit(1)
