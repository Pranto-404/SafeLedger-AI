"""Limited local credential-pattern scan; reports locations only,never matching values.
This is not a substitute for independent secret detection or manual review.
"""
from pathlib import Path
import json
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'github_token':re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b'),
    'provider_key':re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b'),
    'private_key':re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'aws_access_id':re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
}

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    candidates=[];scanned=0
    # Every reachable committed blob once;no matching content is emitted.
    objects=git('rev-list','--objects','--all').splitlines()
    seen=set()
    for entry in objects:
        parts=entry.split(b' ',1)
        if len(parts)!=2:continue
        sha,name=parts
        if sha in seen or git('cat-file','-t',sha.decode()).strip()!=b'blob':continue
        seen.add(sha);data=git('cat-file','blob',sha.decode());scanned+=1
        for kind,pattern in PATTERNS.items():
            if pattern.search(data):candidates.append({'scope':'history','object':sha.decode(),'path':name.decode(errors='replace'),'kind':kind})
    names=git('ls-files','-z').decode().split('\0');forbidden=[]
    for name in filter(None,names):
        p=ROOT/name
        if name.startswith('.private/') or p.name=='.env' or (p.name.startswith('.env.') and p.name!='.env.example') or '.sqlite' in p.name:forbidden.append(name)
        if p.is_file():
            data=p.read_bytes()
            for kind,pattern in PATTERNS.items():
                if pattern.search(data):candidates.append({'scope':'worktree','path':name,'kind':kind})
    ignored={name:subprocess.run(['git','check-ignore','-q',name],cwd=ROOT).returncode==0 for name in ['.private/check','check.sqlite3','.env']}
    result={'status':'passed' if not candidates and not forbidden and all(ignored.values()) else 'review_required','reachable_commits':len(git('rev-list','--all').splitlines()),'unique_history_blobs_scanned':scanned,'known_patterns':list(PATTERNS),'candidates':candidates,'forbidden_tracked_files':forbidden,'ignore_checks':ignored,'scope_limit':'Known credential patterns only;does not prove absence of all secrets/PII. Match values are never printed.'}
    output=ROOT/'evidence/m5/credential-scan.json';output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['candidates','forbidden_tracked_files']}))
    return 0 if result['status']=='passed' else 1

if __name__=='__main__':sys.exit(main())
