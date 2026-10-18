"""Create a minimal, secret-free native FastAPI candidate without changing production."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]


def prepare(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Choose a new empty output path')
    destination.mkdir(parents=True)
    for package in ['api/app']:
        shutil.copytree(ROOT/package,destination/package,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.sqlite*','.env*'))
    for name in ['api/__init__.py']:
        if (ROOT/name).exists():shutil.copy2(ROOT/name,destination/name)
    shutil.copy2(ROOT/'api/requirements.txt',destination/'requirements.txt')
    (destination/'pyproject.toml').write_text('[tool.vercel]\nentrypoint = "api.app.main:app"\n')
    (destination/'.python-version').write_text('3.12\n')
    config={'$schema':'https://openapi.vercel.sh/vercel.json','framework':'fastapi','functions':{'api/app/main.py':{'maxDuration':60}},'headers':[{'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'Referrer-Policy','value':'no-referrer'},{'key':'Cache-Control','value':'no-store'}]}]}
    (destination/'vercel.json').write_text(json.dumps(config,indent=2)+'\n')
    manifest={p.relative_to(destination).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.rglob('*') if p.is_file()}
    (destination/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return {'status':'prepared_not_deployed','files':len(manifest),'entrypoint':'api.app.main:app','secrets_included':False,'production_config_changed':False}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();print(json.dumps(prepare(args.output),indent=2))
