"""Financing-option matching: exact schedules, independent arithmetic, cash-flow fit and authority."""
from datetime import timedelta
import pytest
from pydantic import ValidationError
from api.tests.test_accounts import world, signup
from api.tests.test_manual_inputs import record
from api.app.accounts import today_bd
from api.app.services.financing import LenderQuote, effective_annual_rate_bps, repayment_schedule


def quote(**changes):
    raw=dict(quote_id='q1',lender_name='Example Bank',product_type='term_loan',currency='BDT',principal_minor=100000,
             upfront_fee_minor=1000,rate_type='flat_per_term',rate_bps=250,repayment='single_payment',installments=1,
             term_days=90,quote_source='Branch email 2026-10-18',quoted_on=today_bd().isoformat())
    raw.update(changes)
    return raw


def test_flat_single_payment_matches_reference_arithmetic():
    q=LenderQuote.model_validate(quote())
    assert repayment_schedule(q)==[(90,102500,2500)]
    expected=(102500/99000)**(365/90)-1
    assert abs(effective_annual_rate_bps(99000,repayment_schedule(q))-expected*10000)<=1


def test_annual_reducing_amortizes_exactly_to_zero():
    q=LenderQuote.model_validate(quote(principal_minor=1200000,upfront_fee_minor=0,rate_type='annual_reducing',rate_bps=1200,repayment='equal_installments',installments=12,term_days=360))
    rows=repayment_schedule(q)
    r=0.12*30/365;annuity=1200000*r/(1-(1+r)**-12)
    assert [d for d,_,_ in rows]==[30*k for k in range(1,13)]
    assert all(abs(a-annuity)<=1 for _,a,_ in rows[:-1]) and abs(rows[-1][1]-annuity)<=12
    assert sum(a for _,a,_ in rows)-sum(i for _,_,i in rows)==1200000
    assert 1150<=effective_annual_rate_bps(1200000,rows)<=1300


def test_flat_rate_installments_reveal_higher_effective_cost():
    q=LenderQuote.model_validate(quote(principal_minor=1200000,upfront_fee_minor=0,rate_bps=1000,repayment='equal_installments',installments=12,term_days=360))
    rows=repayment_schedule(q)
    assert sum(a for _,a,_ in rows)==1320000 and sum(i for _,_,i in rows)==120000
    assert effective_annual_rate_bps(1200000,rows)>1800  # a "10% flat" loan costs about 19-20% a year


@pytest.mark.parametrize('change',[dict(upfront_fee_minor=100000),dict(installments=2),dict(repayment='equal_installments',installments=7,term_days=90),
                                   dict(rate_bps=1.5),dict(rate_bps=-1),dict(principal_minor=0),dict(term_days=1826),dict(currency='XXX'),
                                   dict(quoted_on='2026-10-18T00:00:00'),dict(lender_name=''),dict(approved=True)])
def test_invalid_or_unsupported_terms_rejected(change):
    with pytest.raises(ValidationError):LenderQuote.model_validate(quote(**change))


def day(n):return (today_bd()+timedelta(days=n)).isoformat()


def prepare(c):
    assert record(c,amount_minor=100000)[0].status_code==201
    assert record(c,amount_minor=300000,direction='outflow',status='scheduled',effective_on=day(5))[0].status_code==201
    assert record(c,amount_minor=500000,status='scheduled',effective_on=day(20))[0].status_code==201
    return c.get('/api/workspace').json()


def offers():
    return [quote(quote_id='small',principal_minor=100000,upfront_fee_minor=0,rate_bps=100,term_days=60),
            quote(quote_id='fits',principal_minor=250000,upfront_fee_minor=2500,rate_bps=300,term_days=60),
            quote(quote_id='costly',principal_minor=250000,upfront_fee_minor=0,rate_type='annual_reducing',rate_bps=4000,repayment='equal_installments',installments=2,term_days=60),
            quote(quote_id='short',principal_minor=250000,upfront_fee_minor=0,rate_bps=50,term_days=10)]


def test_matching_ranks_by_cash_flow_fit_then_cost_and_records_audit(world):
    c,_=world;signup(c,'finance_matcher');before=prepare(c)
    r=c.post('/api/financing/match',json={'as_of':before['snapshot']['as_of'],'quotes':offers()});assert r.status_code==200,r.text
    body=r.json();by={x['quote_id']:x for x in body['quotes']}
    assert body['funding_need_minor']==200000 and body['baseline_30_day_minimum_minor']==-200000 and body['baseline_first_shortfall_on']==day(5)
    assert by['small']['status']=='DOES_NOT_COVER_SHORTFALL'
    assert by['fits']['status']=='FITS_CASH_FLOW' and by['fits']['total_cost_minor']==10000 and by['fits']['net_proceeds_minor']==247500
    assert by['fits']['schedule']==[{'date':day(60),'payment_minor':257500,'interest_minor':7500}] and by['fits']['lowest_balance_with_financing_minor']==47500
    assert by['costly']['status']=='FITS_CASH_FLOW' and by['costly']['total_cost_minor']>10000 and 'HIGH_COST_FINANCING' in by['costly']['warnings']
    assert by['short']['status']=='REPAYMENT_BREACHES_RESERVE' and by['short']['first_reserve_breach_on']==day(10) and by['short']['additional_receipts_needed_minor']==201250
    assert [x['quote_id'] for x in body['quotes']][:2]==['fits','costly'] and body['best_match_quote_id']=='fits'
    assert all(x['user_supplied'] for x in body['quotes']) and any('not verified' in a for a in body['assumptions'])
    after=c.get('/api/workspace').json()
    assert after['dataset_revision']==before['dataset_revision'] and after['snapshot']==before['snapshot'] and after['proposals']==[]
    events=[e for e in after['audit']['events'] if e['kind']=='FINANCING_ANALYZED']
    assert after['audit']['chain_verified'] and len(events)==1 and events[0]['payload']['best_match_quote_id']=='fits'
    assert events[0]['payload']['analysis_sha256']==body['analysis_sha256'] and events[0]['trace_id']==body['trace_id']


def test_matching_is_deterministic_and_input_order_independent(world):
    c,_=world;signup(c,'finance_repeat');ws=prepare(c)
    first=c.post('/api/financing/match',json={'as_of':ws['snapshot']['as_of'],'quotes':offers()}).json()
    second=c.post('/api/financing/match',json={'as_of':ws['snapshot']['as_of'],'quotes':offers()[::-1]}).json()
    assert first['quotes']==second['quotes'] and first['best_match_quote_id']==second['best_match_quote_id']


def test_no_shortfall_prefers_cheapest_fit_and_flags_suspect_terms(world):
    c,_=world;signup(c,'finance_calm');assert record(c,amount_minor=10000000)[0].status_code==201
    ws=c.get('/api/workspace').json()
    quotes=[quote(quote_id='cheap'),quote(quote_id='fee_heavy',upfront_fee_minor=30000),quote(quote_id='old',quoted_on=day(-45),rate_bps=300)]
    body=c.post('/api/financing/match',json={'as_of':ws['snapshot']['as_of'],'quotes':quotes}).json()
    by={x['quote_id']:x for x in body['quotes']}
    assert body['funding_need_minor']==0 and body['best_match_quote_id']=='cheap'
    assert by['fee_heavy']['status']=='VERIFY_TERMS_WITH_LENDER' and 'QUOTE_OLDER_THAN_30_DAYS' in by['old']['warnings']


def test_authority_currency_date_and_stale_snapshot_rules(world):
    c,_=world;owner=signup(c,'finance_owner2');ws=prepare(c);as_of=ws['snapshot']['as_of']
    assert c.post('/api/financing/match',json={'as_of':as_of,'quotes':[quote(currency='USD')]}).json()['error']['code']=='QUOTE_CURRENCY_MISMATCH'
    assert c.post('/api/financing/match',json={'as_of':as_of,'quotes':[quote(quoted_on=day(1))]}).json()['error']['code']=='QUOTE_DATE_AFTER_SNAPSHOT'
    assert c.post('/api/financing/match',json={'as_of':day(-1),'quotes':[quote()]}).status_code==409
    assert c.post('/api/financing/match',json={'as_of':as_of,'quotes':[quote(),quote()]}).status_code==422
    assert c.post('/api/financing/match',json={'as_of':as_of,'quotes':[quote()]*11}).status_code==422
    code=c.post('/api/account/invitations',json={'role':'viewer'}).json()['code']
    c.post('/api/auth/logout',json={});signup(c,'finance_viewer')
    assert c.post('/api/account/join',json={'code':code}).status_code==200
    assert c.post('/api/financing/match',json={'as_of':as_of,'quotes':[quote()]}).status_code==403
    c.post('/api/auth/logout',json={});c.cookies.clear()
    assert c.post('/api/financing/match',json={'as_of':as_of,'quotes':[quote()]}).status_code==401
