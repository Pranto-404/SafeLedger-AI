"""Read-only checks of the public site and GitHub, plus repository facts. Only GETs of /api/health, /api/ready, the home page and two private routes
(which must answer 401). No sign-in, no account, no load.   python submission/evidence_build/live_and_repo.py <log_dir>"""
import json, subprocess, sys, datetime, collections, re, urllib.request, urllib.error
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; LOGS = Path(sys.argv[1])
SITE = 'https://capzoryx-copilot.vercel.app'
def stamp(): return datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')
def get(url, headers=None):
    req = urllib.request.Request(url, headers=dict({'User-Agent': 'capzoryx-evidence/1.0'}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=40) as r: return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e: return e.code, e.headers, e.read()
def git(*a): return subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
commit = git('rev-parse', 'HEAD')
def write(name, text, cmd): (LOGS / name).write_text(f"Capzoryx Copilot - execution evidence log\nCommand : {cmd}\nStarted : {stamp()}\nCommit  : {commit}\n{'=' * 70}\n{text}\n", encoding='utf-8')

# 9. GitHub Actions
st, h, body = get('https://api.github.com/repos/Pranto-404/capzoryx-copilot/actions/runs?per_page=5', {'Accept': 'application/vnd.github+json'})
lines = [f'HTTP {st}']
if st == 200:
    d = json.loads(body); lines.append(f"total_count {d['total_count']}")
    for r in d['workflow_runs']:
        lines.append(f"run {r['id']} | workflow {r['name']} | commit {r['head_sha']} | event {r['event']} | branch {r['head_branch']} | status {r['status']} | conclusion {r['conclusion']} | created {r['created_at']} | updated {r['updated_at']}")
else: lines.append(body[:300].decode('utf-8', 'replace'))
write('09_github_actions_latest_runs.log', '\n'.join(lines), 'GET https://api.github.com/repos/Pranto-404/capzoryx-copilot/actions/runs?per_page=5')

# 10. live site, read-only
out = []
for path in ['/api/health', '/api/ready']:
    st, h, body = get(SITE + path); out.append(f'GET {path} -> HTTP {st}\n{body.decode("utf-8", "replace")[:600]}\n')
st, h, body = get(SITE + '/')
out.append(f'GET / -> HTTP {st}  (body {len(body)} bytes, not stored)\nSecurity-relevant response headers:')
for k in ['content-security-policy', 'strict-transport-security', 'x-frame-options', 'referrer-policy', 'permissions-policy', 'x-content-type-options', 'cross-origin-opener-policy']:
    out.append(f'  {k}: {h.get(k, "(absent)")}')
out.append('')
for path in ['/api/workspace', '/api/account/profile']:
    st, h, body = get(SITE + path); out.append(f'GET {path} (no session) -> HTTP {st}  {body.decode("utf-8", "replace")[:160]}')
write('10_live_site_readonly.log', '\n'.join(out), f'GET {SITE}/api/health, /api/ready, / (headers), /api/workspace, /api/account/profile')

# 12. repository facts
tracked = git('ls-files').splitlines()
byfolder = collections.Counter(p.split('/')[0] if '/' in p else '(repo root)' for p in tracked)
ext = {'.py': 'Python', '.ts': 'TypeScript', '.tsx': 'TypeScript (React)', '.cjs': 'JavaScript (node scripts)', '.mjs': 'JavaScript (node scripts)', '.js': 'JavaScript', '.css': 'CSS', '.md': 'Markdown', '.json': 'JSON', '.html': 'HTML', '.sql': 'SQL', '.yaml': 'YAML', '.yml': 'YAML'}
loc = collections.Counter(); files = collections.Counter()
skip = re.compile(r'(^|/)(node_modules|dist|shots|fonts|_assets|package-lock\.json|locales/)')
for p in tracked:
    e = Path(p).suffix.lower()
    if e in ext and not skip.search(p) and not p.startswith('web/public/locales'):
        try: n = sum(1 for l in (ROOT / p).read_text(encoding='utf-8', errors='replace').splitlines() if l.strip())
        except OSError: continue
        loc[ext[e]] += n; files[ext[e]] += 1
main_py = (ROOT / 'api/app/main.py').read_text(encoding='utf-8')
ver = re.search(r'FastAPI\(title="([^"]+)", version="([^"]+)"', main_py)
tags = git('tag', '-l', '--format=%(refname:short) -> %(objectname:short) (%(creatordate:short))').splitlines()
r = ['Commit count on the current branch : ' + git('rev-list', '--count', 'HEAD'), 'Branch : ' + git('rev-parse', '--abbrev-ref', 'HEAD'), 'HEAD : ' + commit,
     'First commit date : ' + git('log', '--reverse', '--format=%cs').splitlines()[0], 'Latest commit date : ' + git('log', '-1', '--format=%cs'),
     'Tags (' + str(len(tags)) + '): ' + '; '.join(tags),
     'Tag submission-2026-10-20 points at : ' + git('rev-list', '-n', '1', 'submission-2026-10-20'), 'Tag v0.7.5 points at : ' + git('rev-list', '-n', '1', 'v0.7.5'),
     f'Release in api/app/main.py : title "{ver.group(1)}", version "{ver.group(2)}"', '', f'Tracked files: {len(tracked)}', 'Files by top-level folder:']
r += [f'  {k:18s} {v}' for k, v in sorted(byfolder.items(), key=lambda kv: -kv[1])]
r += ['', 'Non-blank lines of code by language (tracked files; translation files, lock files, fonts, screenshots excluded):']
r += [f'  {k:28s} {loc[k]:>8,d} lines in {files[k]} files' for k, _ in loc.most_common()]
r += ['', f'  {"TOTAL":28s} {sum(loc.values()):>8,d} lines']
tests = subprocess.run([sys.executable, '-m', 'pytest', 'api/tests', '--collect-only', '-q', '-p', 'no:cacheprovider'], cwd=ROOT, capture_output=True, text=True).stdout.strip().splitlines()[-1]
r += ['', 'Backend tests collected: ' + tests]
write('12_repository_facts.log', '\n'.join(r), 'git rev-list --count HEAD; git tag; git ls-files; count lines; read api/app/main.py')
print('ok')
