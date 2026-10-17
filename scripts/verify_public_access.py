"""Local browser/API/SQLite qualification in one isolated network namespace."""
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
out=Path(os.environ.get('SAFELEDGER_EVIDENCE_DIR',str(ROOT/'evidence/public-access/browser'))).resolve()
out.mkdir(parents=True,exist_ok=True)
private=ROOT/'.private/public-ui';private.mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env.update(SAFELEDGER_DB=str(private/('ui-'+secrets.token_hex(5)+'.sqlite3')),SAFELEDGER_SIGNING_KEY=secrets.token_hex(32),SAFELEDGER_EVIDENCE_DIR=str(out))
runtime=ROOT.parent/'browser-runtime/node_modules/@sparticuz/chromium/build/index.js'
if runtime.exists():env.setdefault('SAFELEDGER_CHROMIUM_MODULE',str(runtime))
for key in ('TURSO_DATABASE_URL','TURSO_AUTH_TOKEN','RENDER','VERCEL'):env.pop(key,None)
processes=[]
try:
 with (out/'server.log').open('w') as log:
  server=subprocess.Popen([sys.executable,'-m','uvicorn','scripts.serve_public_access:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(server)
  for _ in range(60):
   if server.poll() is not None:raise RuntimeError('Local verification server stopped')
   try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/ready',timeout=1) as r:
     if r.status==200:break
   except Exception:time.sleep(.1)
  else:raise RuntimeError('Local server did not become ready')
  with (out/'run.log').open('w') as browserlog:
   browser=subprocess.Popen(['node','scripts/public_access_browser.cjs'],cwd=ROOT,env=env,stdout=browserlog,stderr=subprocess.STDOUT,start_new_session=True);processes.append(browser)
   code=browser.wait(timeout=180)
  print((out/'run.log').read_text())
  if code:raise SystemExit(code)
finally:
 for process in reversed(processes):
  try:os.killpg(process.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:process.wait(timeout=5)
  except subprocess.TimeoutExpired:
   try:os.killpg(process.pid,signal.SIGKILL)
   except ProcessLookupError:pass
