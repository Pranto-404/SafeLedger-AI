"""Real browser -> Vite proxy -> FastAPI -> SQLite evidence. No tokens in logs/traces."""
from pathlib import Path
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('SAFELEDGER_EVIDENCE_DIR',ROOT/'evidence/m4/browser')).resolve()
OUT.mkdir(parents=True,exist_ok=True)

def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]

def ready(url,process):
    with httpx.Client(trust_env=False,timeout=2) as client:
        for _ in range(150):
            if process.poll() is not None:raise RuntimeError('Local server exited; inspect server log.')
            try:
                if client.get(url).status_code==200:return
            except httpx.HTTPError:pass
            time.sleep(.1)
    raise RuntimeError('Local server did not become ready.')

def run(script_name='m4_browser_demo.cjs',setup=None):
    with tempfile.TemporaryDirectory(prefix='safeledger-private-m4-') as temporary:
        private=Path(temporary)/'access'
        subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap_demo.py'),'--directory',str(private),'--fixture','duplicate_exact.json'],cwd=ROOT,check=True,capture_output=True)
        settings={}
        for line in (private/'demo.env').read_text().splitlines():
            name,value=shlex.split(line.removeprefix('export '))[0].split('=',1)
            settings[name]=value
        # Additional empty business proves browser import and tenant isolation using real API.
        env=dict(os.environ,**settings)
        if setup is not None:setup(private,settings)
        subprocess.run([sys.executable,'-c',"from api.app import security as s; import sqlite3,os,json; from pathlib import Path; p=Path(os.environ['M4_ACCESS']); d=json.loads(p.read_text()); db=sqlite3.connect(os.environ['SAFELEDGER_DB']); d['bearer_tokens']['empty_owner']=s.provision_session(db,'empty-owner','empty-business','owner'); p.write_text(json.dumps(d)); db.close()"],cwd=ROOT,env=dict(env,M4_ACCESS=str(private/'sessions.json')),check=True)
        api_port,web_port=port(),port()
        with (OUT/'api-server.log').open('w') as api_log,(OUT/'web-server.log').open('w') as web_log:
            api=subprocess.Popen([sys.executable,'-m','uvicorn','api.app.main:app','--host','127.0.0.1','--port',str(api_port)],cwd=ROOT,env=env,stdout=api_log,stderr=subprocess.STDOUT)
            web=subprocess.Popen(['npm','run','dev','--','--port',str(web_port),'--strictPort'],cwd=ROOT/'web',env=dict(env,SAFELEDGER_DEV_API_URL=f'http://127.0.0.1:{api_port}'),stdout=web_log,stderr=subprocess.STDOUT)
            try:
                ready(f'http://127.0.0.1:{api_port}/api/ready',api);ready(f'http://127.0.0.1:{web_port}',web)
                subprocess.run(['node',str(ROOT/'scripts'/script_name)],cwd=ROOT,env=dict(os.environ,SAFELEDGER_BROWSER_URL=f'http://127.0.0.1:{web_port}',SAFELEDGER_BROWSER_ACCESS=str(private/'sessions.json'),SAFELEDGER_EVIDENCE_DIR=str(OUT)),check=True)
            finally:
                for process in [web,api]:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':run()
