from pathlib import Path
import copy
import hashlib
import json
import sqlite3
import pytest
from pydantic import ValidationError
from api.app.services.finance import fingerprint
from api.app.services.intake import IntakeError, MAX_BYTES, parse_csv, parse_json, safe_csv_cell
from api.app.services.storage import create_schema, load_dataset, store_dataset

ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'data/fixtures'

@pytest.fixture
def ds():return parse_json((FIXTURES/'seed_2026.json').read_bytes())

@pytest.fixture
def db(tmp_path):
    with sqlite3.connect(tmp_path/'test.sqlite3') as connection:
        create_schema(connection)
        yield connection


def test_file01_json_and_csv_same_records(ds):
    invoices=parse_csv((FIXTURES/'seed_2026_invoices.csv').read_bytes(),'invoices')
    events=parse_csv((FIXTURES/'seed_2026_events.csv').read_bytes(),'events')
    assert invoices==ds.invoices and events==ds.events


def test_file01_actionable_field_errors():
    with pytest.raises(IntakeError) as err:
        parse_json((FIXTURES/'invalid_amount.json').read_bytes())
    assert err.value.errors[0]['field']=='events.0.amount_minor'
    assert 'not-money' not in str(err.value.errors)

@pytest.mark.parametrize('content',[b'not json',b'\xff',b'{"a":1,"a":2}',b'[]',b'{"x":NaN}'])
def test_file01_bad_json(content):
    with pytest.raises(IntakeError):parse_json(content)

@pytest.mark.parametrize('kind',['invoices','events'])
def test_file03_oversized_csv_and_json(kind):
    content=b'x'*(MAX_BYTES+1)
    with pytest.raises(IntakeError):parse_csv(content,kind)
    with pytest.raises(IntakeError):parse_json(content)

@pytest.mark.parametrize('content',[b'bad,header\n1,2',b'\xff',b'\x00\x01',b'amount_minor,amount_minor\n1,2'])
def test_file01_csv_headers_encoding_and_binary(content):
    with pytest.raises(IntakeError):parse_csv(content,'invoices')

@pytest.mark.parametrize('amount',['1.1','-1','=HYPERLINK("url")','1e3','true','NaN','0'])
def test_file01_csv_amount_errors_locate_line(amount):
    text=(FIXTURES/'seed_2026_invoices.csv').read_text()
    text=text.replace(',3500000,',','+amount+',',1)
    with pytest.raises(IntakeError) as err:parse_csv(text.encode(),'invoices')
    assert err.value.errors[0]['line']==2


def test_file01_csv_column_count_and_quoting():
    text=(FIXTURES/'seed_2026_invoices.csv').read_text()
    header,row=text.splitlines()[:2]
    with pytest.raises(IntakeError):parse_csv((header+'\n'+row+',EXTRA').encode(),'invoices')
    with pytest.raises(IntakeError):parse_csv((header+'\n"unclosed').encode(),'invoices')

@pytest.mark.parametrize('value',[ '=HYPERLINK("url")','+cmd','-1','@SUM(1)',' \t=1','\n=1'])
def test_file02_formula_export_escape(value):
    assert safe_csv_cell(value).startswith("'")


def test_file02_ordinary_text_unchanged():
    assert safe_csv_cell('Invoice INV-105')=='Invoice INV-105'


def test_sqlite_import_roundtrip_source_evidence(ds,db):
    result=store_dataset(db,'company-A',ds)
    assert result=={'dataset_sha256':fingerprint(ds),'invoice_count':45,'event_count':60}
    assert load_dataset(db,'company-A')==ds
    assert db.execute('SELECT count(*) FROM source_records').fetchone()[0]==105
    checksum=db.execute("SELECT record_sha256 FROM source_records WHERE business_id=? AND record_id=?",('company-A','INV-105')).fetchone()[0]
    assert checksum==fingerprint(ds.invoices[0])


def test_invalid_batch_makes_no_writes(db,ds):
    raw=ds.model_dump(mode='json');raw['events'][-1]['amount_minor']=0.1
    with pytest.raises(ValidationError):store_dataset(db,'company-A',raw)
    assert db.execute('SELECT count(*) FROM financial_datasets').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM source_records').fetchone()[0]==0


def test_sqlite_failure_mid_import_rolls_back(db,ds):
    db.execute("CREATE TRIGGER fail_import BEFORE INSERT ON source_records WHEN NEW.record_id='INV-104' BEGIN SELECT RAISE(ABORT,'injected storage failure'); END")
    with pytest.raises(sqlite3.IntegrityError):store_dataset(db,'company-A',ds)
    assert db.execute('SELECT count(*) FROM financial_datasets').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM source_records').fetchone()[0]==0


def test_duplicate_import_does_not_overwrite_or_partially_append(db,ds):
    store_dataset(db,'company-A',ds)
    changed=ds.model_dump(mode='json');changed['opening_balance_minor']=1
    with pytest.raises(sqlite3.IntegrityError):store_dataset(db,'company-A',changed)
    assert load_dataset(db,'company-A')==ds
    assert db.execute('SELECT count(*) FROM source_records').fetchone()[0]==105


def test_two_businesses_can_use_same_source_ids_without_collision(db,ds):
    store_dataset(db,'company-A',ds)
    changed=ds.model_dump(mode='json');changed['opening_balance_minor']=1
    store_dataset(db,'company-B',changed)
    assert load_dataset(db,'company-A').opening_balance_minor==10000000
    assert load_dataset(db,'company-B').opening_balance_minor==1
    with pytest.raises(KeyError):load_dataset(db,'unknown')
    # Storage key separation only: authenticated HTTP IDOR testing is M2.


def test_tampered_snapshot_checksum_rejected(db,ds):
    store_dataset(db,'company-A',ds)
    raw=ds.model_dump(mode='json');raw['opening_balance_minor']=1
    with db:db.execute('UPDATE financial_datasets SET payload=? WHERE business_id=?',(json.dumps(raw),'company-A'))
    with pytest.raises(ValueError,match='checksum'):load_dataset(db,'company-A')


def test_source_manifest_matches_bytes_and_recipe_reproducible():
    import subprocess,sys
    before={p.name:p.read_bytes() for p in FIXTURES.iterdir() if p.suffix in {'.csv','.json'}}
    subprocess.run([sys.executable,'scripts/build_fixtures.py'],cwd=ROOT,check=True,capture_output=True)
    assert before=={p.name:p.read_bytes() for p in FIXTURES.iterdir() if p.suffix in {'.csv','.json'}}
    manifest=json.loads((FIXTURES/'manifest.json').read_text())
    for name,checksum in manifest['files_sha256'].items():assert hashlib.sha256((FIXTURES/name).read_bytes()).hexdigest()==checksum


@pytest.mark.parametrize('change',['checksum','payload','deleted_row'])
def test_tampered_source_records_rejected(db,ds,change):
    store_dataset(db,'company-A',ds)
    with db:
        if change=='checksum':db.execute("UPDATE source_records SET record_sha256='forged' WHERE record_id='INV-105'")
        elif change=='payload':db.execute("UPDATE source_records SET payload='{}' WHERE record_id='INV-105'")
        else:db.execute("DELETE FROM source_records WHERE record_id='INV-105'")
    with pytest.raises(ValueError,match='integrity'):load_dataset(db,'company-A')


def test_csv_overlong_numeric_field_is_actionable():
    text=(FIXTURES/'seed_2026_invoices.csv').read_text().replace(',3500000,',','+'9'*5000+',',1)
    with pytest.raises(IntakeError) as err:parse_csv(text.encode(),'invoices')
    assert err.value.errors[0]['line']==2 and err.value.errors[0]['field']=='amount_minor'


def test_csv_batch_to_staging_database(db,ds):
    raw=ds.model_dump(mode='json')
    for kind in ['invoices','events']:
        raw[kind]=[row.model_dump(mode='json') for row in parse_csv((FIXTURES/f'seed_2026_{kind}.csv').read_bytes(),kind)]
    store_dataset(db,'csv-business',raw)
    assert load_dataset(db,'csv-business')==ds
