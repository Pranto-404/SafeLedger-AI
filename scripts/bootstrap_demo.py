"""Generate private local demo access. Never publish generated credentials."""
from pathlib import Path
import argparse
import json
import os
import secrets
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.app import security as sec
from api.app.services.intake import parse_json
from api.app.services.storage import store_dataset


def bootstrap(destination,fixture="seed_2026.json"):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True,mode=0o700)
    if any(destination.iterdir()):
        raise SystemExit('Destination must be empty; existing demo credentials/data are not overwritten.')
    destination.chmod(0o700)
    key=secrets.token_hex(32)
    os.environ['SAFELEDGER_SIGNING_KEY']=key
    path=destination/'demo.sqlite3'
    tokens={}
    try:
        with sqlite3.connect(path) as db:
            sec.create_schema(db)
            ds=parse_json((Path(__file__).resolve().parents[1]/'data/fixtures'/fixture).read_bytes())
            store_dataset(db,'synthetic-demo',ds)
            with db:
                db.execute('INSERT INTO security_policies VALUES (?,?,?)',('synthetic-demo',1000000,10000000))
                db.executemany('INSERT INTO trusted_vendors VALUES (?,?,1)',[('synthetic-demo',vendor) for vendor in sorted({x.vendor_id for x in ds.invoices})])
            for role in ['owner','approver','viewer','agent']:
                tokens[role]=sec.provision_session(db,'demo-'+role,'synthetic-demo',role,ttl_seconds=86400)
        env=destination/'demo.env'
        credentials=destination/'sessions.json'
        # Use JSON for sessions and shell-safe quotes for generated hex/absolute DB path.
        quote=lambda value: "'"+value.replace("'","'\\''")+"'"
        env.write_text('export SAFELEDGER_DB='+quote(str(path))+'\nexport SAFELEDGER_SIGNING_KEY='+quote(key)+'\n')
        credentials.write_text(json.dumps({'simulation_only':True,'expires_after_hours':24,'bearer_tokens':tokens},indent=2)+'\n')
        for p in [path,env,credentials]:p.chmod(0o600)
        print('Private local demo created. Credentials were not printed. See README M2 setup; do not commit or upload this directory.')
    except BaseException:
        # Do not silently retry or overwrite a partially created private directory.
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',default='.private/demo')
    parser.add_argument('--fixture',choices=['seed_2026.json','duplicate_exact.json','duplicate_possible.json','untrusted_memo.json'],default='seed_2026.json')
    args=parser.parse_args();bootstrap(args.directory,args.fixture)
