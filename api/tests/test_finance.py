import copy
from datetime import date
from pathlib import Path
import json
import random
import pytest
from pydantic import ValidationError
from api.app.contracts import ScenarioRequest
from api.app.services.finance import (Dataset, FinancingRequest, analyze_duplicates, bdt_minor, compare_financing, fingerprint, project_cashflow, snapshot, validated)

FIXTURES=Path(__file__).resolve().parents[2]/'data/fixtures'

@pytest.fixture
def raw():
    return json.loads((FIXTURES/'seed_2026.json').read_text())

@pytest.fixture
def ds(raw):
    return validated(raw)

@pytest.fixture
def oracle():
    return json.loads((FIXTURES/'expected_results.json').read_text())


def scenario(ds, horizon=30, delay=0):
    return project_cashflow(ds,ScenarioRequest(as_of=ds.as_of,horizon_days=horizon,reserve_minor=1000000,delay_inflows_days=delay))


def test_fin01_exact_decimal_conversion():
    assert bdt_minor('0.10')+bdt_minor('0.20') == 30
    assert bdt_minor('35000.00') == 3500000
    assert bdt_minor('10000000000') == 10**12

@pytest.mark.parametrize('value', ['-1','NaN','Infinity','1e3','0.001',' 1.0','1,000','10000000001','',0.1,True])
def test_fin04_invalid_money_strings(value):
    with pytest.raises(ValueError): bdt_minor(value)


def test_fin01_fixture_reconciliation(ds,oracle):
    summary=snapshot(ds)
    assert len(ds.invoices)==oracle['invoice_count']==45
    assert len(ds.events)==oracle['event_count']==60
    assert summary['income_minor']==3000000
    assert summary['expenses_minor']==1000000
    assert summary['balance_minor']==12000000==oracle['balance_minor']
    assert summary['opening_balance_minor']+summary['income_minor']-summary['expenses_minor']==summary['balance_minor']
    assert summary['source_ids']==['opening-2026','row-event-CREDIT','row-event-DEBIT']
    assert sum(x.amount_minor for x in ds.invoices)==oracle['payables_minor']
    assert analyze_duplicates(ds)==[]

@pytest.mark.parametrize('horizon,delay,key',[(7,0,'forecast_7_closing_minor'),(30,0,'forecast_30_closing_minor'),(7,7,'delayed_7_closing_minor'),(30,7,'delayed_30_closing_minor')])
def test_fin07_fixed_forecasts(ds,oracle,horizon,delay,key):
    forecast=scenario(ds,horizon,delay)
    assert forecast['closing_balance_minor']==oracle[key]
    assert len(forecast['days'])==horizon
    assert forecast['first_shortfall_on']==oracle['first_shortfall_on']
    assert forecast['days'][0]['date']=='2026-10-18'
    assert forecast['closing_balance_minor']==forecast['opening_balance_minor']+sum(x['inflow_minor']-x['outflow_minor'] for x in forecast['days'])
    for row in forecast['days']:
        assert row['shortfall_minor']==max(0,1000000-row['projected_balance_minor'])


def test_fin06_linked_invoice_not_double_counted(ds):
    forecast=scenario(ds)
    day=forecast['days'][1]
    assert day['date']=='2026-10-19'
    assert day['outflow_minor']==3500000
    assert day['source_ids']==['row-event-INV105']
    assert sum(x['outflow_minor'] for x in forecast['days'])==17930000
    assert forecast['minimum_balance_minor']==-5500000
    assert scenario(ds,delay=7)['minimum_balance_minor']==-5930000


def test_fin02_exact_duplicate_is_flagged_and_counted_once(ds):
    dup=validated(json.loads((FIXTURES/'duplicate_exact.json').read_text()))
    flags=analyze_duplicates(dup)
    assert flags==[{'risk':'DUPLICATE_EXACT','invoice_ids':['INV-104','INV-104-DUP'],'source_ids':['row-inv-104','row-inv-104-DUP'],'execution_blocked':True}]
    assert scenario(ds)['closing_balance_minor']==scenario(dup)['closing_balance_minor']


def test_fin03_near_duplicate_conservative_liability(ds):
    near=validated(json.loads((FIXTURES/'duplicate_possible.json').read_text()))
    assert analyze_duplicates(near)[0]['risk']=='DUPLICATE_POSSIBLE'
    assert analyze_duplicates(near)[0]['execution_blocked']
    assert scenario(near)['closing_balance_minor']==scenario(ds)['closing_balance_minor']-5000000


def test_conflicting_exact_duplicates_rejected(raw):
    duplicate=copy.deepcopy(raw['invoices'][0]);duplicate.update(invoice_id='OTHER',source_record_id='OTHER',amount_minor=1)
    raw['invoices'].append(duplicate)
    with pytest.raises(ValidationError,match='Conflicting duplicate'): validated(raw)


def test_invoice_number_aliases_flag_exact_duplicate(raw):
    duplicate=copy.deepcopy(raw['invoices'][0]);duplicate.update(invoice_id='OTHER',source_record_id='OTHER',invoice_number=' a105 ')
    raw['invoices'].append(duplicate)
    assert analyze_duplicates(validated(raw))[0]['risk']=='DUPLICATE_EXACT'


def test_paid_invoice_excluded_without_losing_cleared_debit(raw):
    raw['invoices'][0]['status']='paid'
    event=next(x for x in raw['events'] if x['invoice_id']=='INV-105')
    event.update(status='cleared',effective_on=raw['as_of'])
    ds=validated(raw)
    assert snapshot(ds)['balance_minor']==8500000
    assert scenario(ds)['closing_balance_minor']==-1875000  # payment moved from forecast to current cash
    assert scenario(ds)['days'][1]['outflow_minor']==0

@pytest.mark.parametrize('change', ['duplicate_id','duplicate_source','future_clear','before_open_clear','unknown_link','wrong_amount','multiple_settlement','paid_without_clear','future_invoice','mixed_currency','timestamp','wrong_snapshot_order'])
def test_financial_input_inconsistencies_rejected(raw,change):
    if change=='duplicate_id': raw['events'][1]['event_id']=raw['events'][0]['event_id']
    elif change=='duplicate_source':raw['events'][0]['source_record_id']=raw['invoices'][0]['source_record_id']
    elif change=='future_clear':raw['events'][0]['effective_on']='2026-10-18'
    elif change=='before_open_clear':raw['events'][0]['effective_on']='2026-09-30'
    elif change=='unknown_link':raw['events'][2]['invoice_id']='UNKNOWN'
    elif change=='wrong_amount':raw['events'][2]['amount_minor']=1
    elif change=='multiple_settlement':raw['events'].append(dict(raw['events'][2],event_id='OTHER',source_record_id='OTHER'))
    elif change=='paid_without_clear':raw['invoices'][0]['status']='paid'
    elif change=='future_invoice':raw['invoices'][0]['issued_on']='2026-10-18'
    elif change=='mixed_currency':raw['events'][0]['currency']='USD'
    elif change=='timestamp':raw['events'][0]['effective_on']=1792000000
    elif change=='wrong_snapshot_order':raw['opening_on']='2026-10-18'
    with pytest.raises(ValidationError):validated(raw)


def test_scenario_snapshot_mismatch(ds):
    with pytest.raises(ValueError,match='immutable snapshot'):
        project_cashflow(ds,ScenarioRequest(as_of='2026-10-18',horizon_days=7,reserve_minor=0))


def test_overdue_obligations_on_day_one(raw):
    raw['events'][3]['effective_on']='2026-10-16'
    ds=validated(raw)
    assert scenario(ds)['days'][0]['outflow_minor']==9000000


def test_future_after_horizon_excluded_and_day7_included(raw):
    ds=validated(raw)
    day7=scenario(ds,7)['days'][-1]
    assert day7['date']=='2026-10-24' and day7['inflow_minor']==4000000
    raw['events'][4]['effective_on']='2026-10-25'
    assert scenario(validated(raw),7)['closing_balance_minor']==-5500000


def test_source_order_and_model_mutation(ds,raw):
    reversed_raw=copy.deepcopy(raw);reversed_raw['invoices'].reverse();reversed_raw['events'].reverse()
    assert scenario(ds)==scenario(validated(reversed_raw))
    ds.events[0].amount_minor=1.5
    with pytest.raises(ValidationError): snapshot(ds)


def test_empty_dataset_and_zero_reserve():
    ds=Dataset(opening_source_id='opening',opening_on='2026-10-17',as_of='2026-10-17',opening_balance_minor=0,currency='BDT',invoices=[],events=[])
    forecast=project_cashflow(ds,ScenarioRequest(as_of=ds.as_of,horizon_days=7,reserve_minor=0))
    assert forecast['closing_balance_minor']==0 and forecast['first_shortfall_on'] is None


def test_untrusted_memo_has_no_financial_authority(ds):
    attack=validated(json.loads((FIXTURES/'untrusted_memo.json').read_text()))
    assert snapshot(attack)['balance_minor']==snapshot(ds)['balance_minor']
    assert scenario(attack)==scenario(ds)
    assert fingerprint(attack)!=fingerprint(ds)  # content change visible in provenance


def test_financial_conservation_over_100_generated_datasets():
    rng=random.Random(2026)
    for _ in range(100):
        amounts=[rng.randrange(1,1000000) for _ in range(10)]
        rows=[dict(source_record_id=f'row-{i}',event_id=f'event-{i}',direction='inflow' if i%2==0 else 'outflow',status='cleared',effective_on='2026-10-17',amount_minor=amount,currency='BDT') for i,amount in enumerate(amounts)]
        ds=Dataset(opening_source_id='opening',opening_on='2026-10-01',as_of='2026-10-17',opening_balance_minor=100000000,currency='BDT',invoices=[],events=rows)
        independent=100000000+sum(amounts[::2])-sum(amounts[1::2])
        assert snapshot(ds)['balance_minor']==independent


def financing_request(**overrides):
    raw=dict(principal_minor=5000000,repayment_capacity_minor=6000000,capacity_source_ids=['verified-forecast-day30'],offers=json.loads((FIXTURES/'fictional_offers.json').read_text()))
    raw.update(overrides)
    return raw


def test_fin08_full_cost_ranking_and_fee_disclosure(oracle):
    result=compare_financing(FinancingRequest.model_validate(financing_request()))
    assert [x['offer_id'] for x in result['offers']]==oracle['ranked_offers']
    assert [x['total_cost_minor'] for x in result['offers']]==[200000,210000,250000]
    assert all(x['affordable'] for x in result['offers'])
    a=result['offers'][-1]
    assert a['rate_bps']==100 and a['total_repayment_minor']==5050000
    assert a['net_proceeds_minor']==4800000 and a['total_cost_minor']==250000
    for offer in result['offers']:
        assert offer['total_cost_minor']==offer['total_repayment_minor']+offer['upfront_fee_minor']-offer['principal_minor']
        assert offer['source_ids'][1:]==['verified-forecast-day30']


def test_financing_honest_unaffordability_and_rounding():
    req=financing_request(repayment_capacity_minor=0)
    result=compare_financing(FinancingRequest.model_validate(req))
    assert all(not x['affordable'] and x['repayment_gap_minor']==x['total_repayment_minor'] for x in result['offers'])
    req=financing_request(principal_minor=101,repayment_capacity_minor=200)
    req['offers']=[dict(req['offers'][0],principal_minor=101,upfront_fee_minor=0,rate_bps=5000)]
    offer=compare_financing(FinancingRequest.model_validate(req))['offers'][0]
    assert offer['interest_minor']==51

@pytest.mark.parametrize('change',['missing_rate','missing_fee','different_term','different_principal','nonfictional','duplicate_ids','fee_too_high','no_sources','float_capacity'])
def test_financing_rejects_unsupported_assumptions(change):
    raw=financing_request()
    if change=='missing_rate':del raw['offers'][0]['rate_convention']
    elif change=='missing_fee':del raw['offers'][0]['upfront_fee_minor']
    elif change=='different_term':raw['offers'][0]['term_days']=60
    elif change=='different_principal':raw['offers'][0]['principal_minor']=1
    elif change=='nonfictional':raw['offers'][0]['fictional']=False
    elif change=='duplicate_ids':raw['offers'][0]['offer_id']=raw['offers'][1]['offer_id']
    elif change=='fee_too_high':raw['offers'][0]['upfront_fee_minor']=5000000
    elif change=='no_sources':raw['capacity_source_ids']=[]
    elif change=='float_capacity':raw['repayment_capacity_minor']=1.1
    with pytest.raises(ValidationError):FinancingRequest.model_validate(raw)
