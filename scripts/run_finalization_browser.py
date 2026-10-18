"""Run the frontend/API product suite together against a disposable local database."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1]

def main():
    env=os.environ.copy()
    for key in ['TURSO_DATABASE_URL','TURSO_AUTH_TOKEN','RENDER','VERCEL']+[k for k in env if k.startswith('SAFELEDGER_LLM_')]:env.pop(key,None)
    # Serverless Chromium's tar extractor tries unsupported chown on this host.
    # Pre-extract its official bundled fonts without restoring archive ownership.
    cached=Path(tempfile.gettempdir())/'chromium'
    if cached.is_file() and cached.stat().st_size==0:cached.unlink()  # interrupted temporary extraction only
    module=env.get('SAFELEDGER_CHROMIUM_MODULE')
    if module:
        archive=Path(module).resolve().parents[1]/'bin/fonts.tar.br'
        if archive.exists():
            decoded=subprocess.run(['node','-e',"process.stdout.write(require('node:zlib').brotliDecompressSync(require('node:fs').readFileSync(process.argv[1])))",str(archive)],check=True,capture_output=True).stdout
            subprocess.run(['tar','--no-same-owner','-xf','-','-C',tempfile.gettempdir()],input=decoded,check=True)
    with tempfile.TemporaryDirectory(prefix='safeledger-browser-') as temporary:
        env.update(SAFELEDGER_DB=str(Path(temporary)/'test.sqlite3'),SAFELEDGER_SIGNING_KEY='b'*64,PYTHONPATH=str(ROOT))
        out=Path(env.get('SAFELEDGER_EVIDENCE_DIR',ROOT/'evidence/finalization/browser'));out.mkdir(parents=True,exist_ok=True)
        with (out/'server.log').open('w') as log:
            process=subprocess.Popen([sys.executable,'-m','uvicorn','scripts.serve_public_access:app','--host','127.0.0.1','--port','8000'],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                for _ in range(100):
                    try:urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1);break
                    except Exception:
                        if process.poll() is not None:raise RuntimeError('Local server failed; inspect server.log')
                        time.sleep(.1)
                return subprocess.run(['node',env.get('SAFELEDGER_BROWSER_SCRIPT','scripts/finalization_browser.cjs')],cwd=ROOT,env=env).returncode
            finally:process.terminate();process.wait()
if __name__=='__main__':raise SystemExit(main())
