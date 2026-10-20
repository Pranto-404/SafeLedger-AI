"""Verify a published commit in a fresh checkout/venv/node_modules;retain real command logs."""
from pathlib import Path
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--commit',required=True)
    parser.add_argument('--output',default='evidence/m6/reproducibility')
    args=parser.parse_args()
    if len(args.commit)!=40 or any(c not in '0123456789abcdef' for c in args.commit):parser.error('Use a full published commit SHA.')
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():raise SystemExit('Use a fresh evidence output directory;prior results are preserved.')
    result={'source_commit':args.commit,'repository':'https://github.com/Pranto-404/capzoryx-copilot','started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':[],'status':'running','scope':'Fresh remote checkout,Python venv and npm ci. Existing OS/Python/Node and optional Chromium binary reused;not a pristine VM/browser-install proof.'}
    env=dict(os.environ)
    for key in list(env):
        if key.startswith('SAFELEDGER_LLM_') or key in {'SAFELEDGER_DB','SAFELEDGER_SIGNING_KEY','SAFELEDGER_PLAYWRIGHT_MODULE'}:env.pop(key)
    def command(name,cmd,cwd,extra=None):
        start=time.monotonic()
        with (out/(name+'.log')).open('wb') as log:
            completed=subprocess.run(list(map(str,cmd)),cwd=cwd,env=dict(env,**(extra or {})),stdout=log,stderr=subprocess.STDOUT)
        result['checks'].append({'name':name,'command':list(map(str,cmd)),'exit_code':completed.returncode,'elapsed_seconds':round(time.monotonic()-start,2),'log':name+'.log'})
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if completed.returncode:raise RuntimeError(f'{name} failed;inspect saved log.')
    try:
        with tempfile.TemporaryDirectory(prefix='safeledger-fresh-clone-') as temp:
            root=Path(temp)/'repository'
            command('clone',['git','clone','--no-checkout',result['repository']+'.git',root],temp)
            command('checkout',['git','checkout','--detach',args.commit],root)
            observed=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
            if observed!=args.commit:raise RuntimeError('Checkout did not match requested commit.')
            result['observed_commit']=observed
            command('create-venv',[sys.executable,'-m','venv',root/'.venv'],root)
            python=root/'.venv/bin/python'
            command('python-install',[python,'-m','pip','install','-r','api/requirements.lock.txt'],root)
            command('python-version',[python,'--version'],root)
            command('python-packages',[python,'-m','pip','list','--format=json'],root)
            command('dependency-consistency',[python,'-m','pip','check'],root)
            command('pytest',[python,'-m','pytest','-q','--junitxml='+str(out/'pytest.xml')],root)
            command('npm-ci',['npm','ci','--prefix','web'],root)
            command('node-version',['node','--version'],root)
            command('frontend-build',['npm','run','build','--prefix','web'],root)
            command('bootstrap-smoke',[python,'scripts/verify_bootstrap.py'],root,{'SAFELEDGER_EVIDENCE_DIR':str(out/'bootstrap')})
            command('live-http',[python,'scripts/m2_http_demo.py'],root,{'SAFELEDGER_EVIDENCE_DIR':str(out/'http')})
            command('browser-workflow',[python,'scripts/m4_browser_demo.py'],root,{'SAFELEDGER_EVIDENCE_DIR':str(out/'browser')})
            command('browser-adversarial',[python,'scripts/m5_browser_qa.py'],root,{'SAFELEDGER_EVIDENCE_DIR':str(out/'adversarial')})
            result['status']='passed'
    except Exception as exc:
        result['status']='failed';result['failure']=str(exc)
        failed=[x for x in result['checks'] if x['exit_code']]
        if failed:result['first_failed_check']=failed[0]['name']
    result['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'source_commit':args.commit,'checks':len(result['checks']),'result':str(out/'result.json')}))
    return 0 if result['status']=='passed' else 1

if __name__=='__main__':sys.exit(main())
