"""Exact currency economics and empty-workspace controls, using disposable databases."""
import json
import sqlite3
import uuid
from pathlib import Path
import pytest
from api.tests.test_accounts import world, signup, PASSWORD
from api.app.currencies import CURRENCIES, scale
from api.app.services.finance import validated, fingerprint
from api.app.accounts import today_bd

@pytest.mark.parametrize('currency,units',[('JPY',12345),('USD',12345),('KWD',12345),('CLF',12345)])
def test_currency_signup_input_and_immutable_economics(world,currency,units):
    c,path=world
    result=c.post('/api/auth/signup',json={'username':'currency_owner','password':PASSWORD,'currency':currency})
    assert result.status_code==201,result.text
    business=result.json()['business_id']
    bundle=c.get('/api/workspace').json()
    assert bundle['snapshot']['currency']==currency and bundle['snapshot']['balance_minor']==0
    assert bundle['policy']['payment_limit_minor']==100000*scale(currency)
    body={'request_id':str(uuid.uuid4()),'expected_revision':bundle['dataset_revision'],'kind':'cash','amount_minor':units,'effective_on':today_bd().isoformat()}
    assert c.post('/api/workspace/records',json=body).status_code==201
    assert c.post('/api/workspace/records',json=body).json()['replayed']
    updated=c.get('/api/workspace').json()
    assert updated['snapshot']['balance_minor']==units
    assert updated['events'][0]['currency']==currency
    assert updated['month']['closing_balance_minor']==units
    change=c.post('/api/workspace/currency',json={'currency':'EUR','expected_revision':updated['dataset_revision']})
    assert change.status_code==409 and change.json()['error']['code']=='WORKSPACE_CURRENCY_LOCKED'
    with sqlite3.connect(path) as db:
        payload=json.loads(db.execute('SELECT payload FROM financial_datasets WHERE business_id=?',(business,)).fetchone()[0])
    assert payload['currency']==currency and payload['events'][0]['amount_minor']==units


def test_empty_currency_change_revision_import_and_permissions(world):
    c,path=world;signup(c,'currency_owner')
    before=c.get('/api/workspace').json()
    body={'currency':'KWD','expected_revision':before['dataset_revision']}
    assert c.post('/api/workspace/currency',json=body,headers={'Origin':'https://attacker.invalid'}).status_code==403
    assert c.post('/api/workspace/currency',json=body).status_code==200
    assert c.post('/api/workspace/currency',json={**body,'currency':'JPY'}).status_code==409
    after=c.get('/api/workspace').json()
    assert after['snapshot']['currency']=='KWD' and after['audit']['chain_verified']
    assert after['policy']['payment_limit_minor']==100000000
    assert after['audit']['events'][-1]['kind']=='CURRENCY_CHANGED'
    ds=dict(opening_source_id='opening',opening_on='2026-01-01',as_of='2026-01-01',opening_balance_minor=0,currency='USD',invoices=[],events=[])
    assert c.post('/api/workspace/import',json=ds).json()['error']['code']=='IMPORT_CURRENCY_MISMATCH'
    ds['currency']='KWD'
    assert c.post('/api/workspace/import',json=ds).status_code==201
    with sqlite3.connect(path) as db:db.execute("UPDATE security_users SET role='viewer'")
    assert c.post('/api/workspace/currency',json={'currency':'JPY','expected_revision':c.get('/api/workspace').json()['dataset_revision']}).status_code==403

@pytest.mark.parametrize('code',['XXX','BTC','usd','USDX',' USD',None,123])
def test_unsupported_currency_rejected(world,code):
    c,_=world
    assert c.post('/api/auth/signup',json={'username':'invalid_owner','password':PASSWORD,'currency':code}).status_code==422


def test_mixed_currency_and_mutated_dataset_rejected():
    raw=json.loads(Path('data/fixtures/duplicate_exact.json').read_text())
    raw['events'][0]['currency']='JPY'
    with pytest.raises(ValueError):validated(raw)
    raw=json.loads(Path('data/fixtures/duplicate_exact.json').read_text())
    ds=validated(raw);ds.currency='USD'
    with pytest.raises(ValueError):validated(ds)
    assert len(CURRENCIES)>150
    assert [scale(c) for c in ['JPY','USD','KWD','CLF']]==[1,100,1000,10000]


def test_new_workspace_currency_and_session_isolation(world):
    c,_=world;owner=signup(c,'workspace_owner')
    second=c.post('/api/account/workspaces',json={'kind':'personal','name':'Yen workspace','currency':'JPY'})
    assert second.status_code==201,second.text
    assert c.get('/api/workspace').json()['snapshot']['currency']=='JPY'
    assert c.post('/api/account/switch',json={'business_id':owner['business_id']}).status_code==200
    assert c.get('/api/workspace').json()['snapshot']['currency']=='BDT'

@pytest.mark.parametrize('currency',['JPY','KWD','CLF'])
def test_foreign_currency_signed_payment_and_replay(world,currency):
    c,_=world
    owner=c.post('/api/auth/signup',json={'username':'pay_owner','password':PASSWORD,'currency':currency}).json()
    day=today_bd().isoformat()
    def record(**fields):
        rev=c.get('/api/workspace').json()['dataset_revision']
        r=c.post('/api/workspace/records',json={'request_id':str(uuid.uuid4()),'expected_revision':rev,'effective_on':day,**fields})
        assert r.status_code==201,r.text
        return r.json()['source_id']
    record(kind='cash',amount_minor=50000)
    invoice=record(kind='invoice',amount_minor=12345,vendor_id='supplier',invoice_number='PAY-1',due_on=day,trust_vendor=True)
    r=c.post('/api/proposals',json={'invoice_id':invoice});assert r.status_code==201,r.text
    proposal=r.json();assert proposal['details']['currency']==currency
    invitation=c.post('/api/account/invitations',json={'role':'approver'}).json()['code']
    signup(c,'pay_approver')
    assert c.post('/api/account/join',json={'code':invitation}).status_code==200
    route='/api/proposals/'+proposal['proposal_id']+'/approve'
    body={'proposal_hash':proposal['action_hash'],'decision':'approve'}
    for _ in range(2):assert c.post(route,json=body).status_code==200
    bundle=c.get('/api/workspace').json()
    assert bundle['snapshot']['balance_minor']==37655
    assert bundle['snapshot']['currency']==currency
    assert bundle['audit']['chain_verified']
    assert sum(x.get('invoice_id')==invoice for x in bundle['events'])==1
    assert all(x['currency']==currency for x in bundle['events'])
