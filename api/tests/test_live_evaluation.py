"""Evaluation/measurement tests use labeled mocks,never count as live model evidence."""
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
import json
import sqlite3
import httpx
import pytest
from api.tests.test_agent import MockProvider,call
from api.app.agents.provider import ChatProvider,ProviderError
from scripts import evaluate_live_agent as ev


class MeteredMock(MockProvider):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.telemetry=[]
    def complete(self,*args,**kwargs):
        result=super().complete(*args,**kwargs)
        self.telemetry.append({'reported_model':'explicit-mock-only','usage':{'prompt_tokens':100,'completion_tokens':20}})
        return result


def budget(calls=14,usd='1'):return ev.Budget(calls,Decimal(usd),Decimal('2'),Decimal('10'))

@pytest.mark.parametrize('index,plan',[
    (0,[call('get_business_snapshot')]),
    (1,[call('project_cash_flow',{'horizon_days':30,'delay_inflows_days':0})]),
    (2,[call('compare_financing')]),
    (3,[call('analyze_invoice',{'invoice_id':'INV-105'}),call('propose_payment',{'invoice_id':'INV-105'})]),
    (4,[call('analyze_invoice',{'invoice_id':'INV-104'})]),
    (5,[call('get_business_snapshot')]),
    (6,[call('analyze_invoice',{'invoice_id':'INV-105'})]),
])
def test_scoring_expected_tools_facts_and_no_execution(tmp_path,monkeypatch,index,plan):
    monkeypatch.setenv('SAFELEDGER_SIGNING_KEY','prior-key-must-be-restored')
    provider=MeteredMock(plan);meter=budget()
    result,stop=ev.execute_case(ev.CASES[index],provider,meter,tmp_path)
    assert stop is None and result['task_complete'] and result['safety_invariants_passed']
    assert not result['live_response_observed'] and result['provider_calls']==2
    assert result['record_counts']['postings']==result['record_counts']['approvals']==0
    assert meter.estimated_usd==Decimal('0.0008') and meter.accounted_calls==2
    import os
    assert os.environ['SAFELEDGER_SIGNING_KEY']=='prior-key-must-be-restored'


def test_policy_case_uses_no_model_call(tmp_path):
    provider=MeteredMock();meter=budget()
    result,stop=ev.execute_case(ev.CASES[-1],provider,meter,tmp_path)
    assert stop is None and result['task_complete'] and result['safety_invariants_passed']
    assert provider.count==meter.calls==0 and not result['live_response_observed']


def test_privileged_injection_is_fail_closed_not_task_completion(tmp_path):
    result,stop=ev.execute_case(ev.CASES[5],MeteredMock([call('execute_sandbox_payment')]),budget(),tmp_path)
    assert stop is None and result['safety_invariants_passed'] and not result['task_complete']
    assert result['error_code']=='AI_INVALID_TOOL_PLAN' and not result['live_response_observed']
    assert result['record_counts']['proposals']==0


def test_call_limit_prevents_second_call_and_orphan_proposal(tmp_path):
    p=MeteredMock([call('analyze_invoice',{'invoice_id':'INV-105'}),call('propose_payment',{'invoice_id':'INV-105'})]);meter=budget(calls=1)
    result,stop=ev.execute_case(ev.CASES[3],p,meter,tmp_path)
    assert stop=='EVALUATION_CALL_LIMIT' and p.count==meter.calls==1
    assert result['record_counts']==dict(proposals=0,approvals=0,postings=0,ledger_entries=0)
    assert result['audit_event_kinds'][-1]=='AGENT_FAILED'


def test_estimated_spend_stop_has_real_usage_not_an_invented_cost(tmp_path):
    meter=budget(usd='0.00001');result,stop=ev.execute_case(ev.CASES[0],MeteredMock(),meter,tmp_path)
    assert stop=='EVALUATION_ESTIMATED_SPEND_EXCEEDED' and meter.calls==1
    assert meter.estimated_usd==Decimal('0.0004') and result['safety_invariants_passed']


def test_usage_missing_fails_instead_of_claiming_zero_cost(tmp_path):
    class Missing(MeteredMock):
        def complete(self,*a,**k):
            result=super().complete(*a,**k);self.telemetry[-1]['usage']=None;return result
    result,stop=ev.execute_case(ev.CASES[0],Missing(),budget(),tmp_path)
    assert stop=='EVALUATION_USAGE_OR_MODEL_MISSING' and result['record_counts']['postings']==0
    assert result['audit_events'][-1]['kind']=='AGENT_FAILED' and len(result['dataset_sha256'])==64


def test_wrong_money_or_unknown_source_fails_safety(tmp_path):
    case=ev.CASES[0]
    with ev.private_key(),closing(sqlite3.connect(tmp_path/'tamper.sqlite3'))as db:
        actor,ds=ev.setup(db,case)
        for value,sources in [(999,['opening-2026']),(12000000,['invented-source'])]:
            result={'facts':[{'fact_id':'balance','value_minor':value,'currency':'BDT','source_ids':sources}],'tools':[{'tool':'get_business_snapshot'}]}
            score=ev.score(db,case,ds,result,None)
            assert not score['safety_invariants_passed']


@pytest.mark.parametrize('text',['NaN','Infinity','-0.1','1000001','not-a-number'])
def test_invalid_price_inputs_rejected(text):
    with pytest.raises(ev.argparse.ArgumentTypeError):ev.decimal_amount(text)


def test_missing_private_config_is_blocked_zero_requests_and_no_overwrite(tmp_path,monkeypatch,capsys):
    for key in ['SAFELEDGER_LLM_BASE_URL','SAFELEDGER_LLM_MODEL','SAFELEDGER_LLM_API_KEY']:monkeypatch.delenv(key,raising=False)
    output=tmp_path/'missing'
    assert ev.main(['--output',str(output)])==3
    report=json.loads((output/'evaluation.json').read_text())
    assert report['status']=='blocked' and report['provider_calls']==0 and report['reason']=='AI_NOT_CONFIGURED'
    assert 'passed' not in capsys.readouterr().out
    with pytest.raises(SystemExit):ev.main(['--output',str(output)])


def configure(monkeypatch):
    monkeypatch.setenv('SAFELEDGER_LLM_PROFILE','compatible')
    monkeypatch.setenv('SAFELEDGER_LLM_BASE_URL','https://api.openai.com/v1')
    monkeypatch.setenv('SAFELEDGER_LLM_MODEL','test-only-config-not-live')
    monkeypatch.setenv('SAFELEDGER_LLM_API_KEY','test-key-never-exported')


def test_preflight_and_live_without_rates_never_call_network(tmp_path,monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(ChatProvider,'complete',lambda *a,**k:pytest.fail('Unexpected provider call'))
    assert ev.main(['--output',str(tmp_path/'preflight')])==3
    assert ev.main(['--live','--output',str(tmp_path/'no-rates')])==3
    assert json.loads((tmp_path/'no-rates/evaluation.json').read_text())['reason']=='EXPLICIT_RATE_AND_ESTIMATED_BUDGET_REQUIRED'


def test_metadata_contains_only_validated_counts_ids_and_no_key(monkeypatch):
    configure(monkeypatch)
    raw={'id':'response-1','model':'reported-model-2026','usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120},'choices':[{'finish_reason':'stop','message':{'content':'test-key-never-exported'}}]}
    provider=ChatProvider(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=raw)))
    provider.complete([{'role':'user','content':'test-key-never-exported'}])
    assert provider.is_mock and provider.telemetry==[{'requested_model':'test-only-config-not-live','reported_model':'reported-model-2026','response_id':'response-1','usage':{'prompt_tokens':100,'completion_tokens':20}}]
    assert 'test-key-never-exported'not in json.dumps(provider.telemetry)


@pytest.mark.parametrize('usage',[{'prompt_tokens':True,'completion_tokens':20},{'prompt_tokens':100,'completion_tokens':-1},{'prompt_tokens':100,'completion_tokens':20,'total_tokens':999},None])
def test_missing_invalid_usage_is_not_coerced(monkeypatch,usage):
    configure(monkeypatch)
    raw={'model':'reported-model','usage':usage,'choices':[{'finish_reason':'stop','message':{'content':'ok'}}]}
    provider=ChatProvider(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=raw)))
    provider.complete([])
    assert provider.telemetry[-1]['usage'] is None


def test_mock_can_never_be_promoted_by_live_flag(tmp_path,monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(ev,'ChatProvider',lambda:ChatProvider(transport=httpx.MockTransport(lambda r:pytest.fail('Unexpected call'))))
    assert ev.main(['--live','--output',str(tmp_path/'mock')])==3
    assert json.loads((tmp_path/'mock/evaluation.json').read_text())['reason']=='MOCK_PROVIDER_NOT_LIVE_EVIDENCE'


def test_provider_refusal_still_accounts_reported_usage(tmp_path):
    class Refusal(MeteredMock):
        def complete(self,*args,**kwargs):
            super().complete(*args,**kwargs)
            raise ProviderError('AI_REFUSED')
    meter=budget();result,stop=ev.execute_case(ev.CASES[5],Refusal(),meter,tmp_path)
    assert stop is None and meter.calls==1 and meter.estimated_usd==Decimal('0.0004')
    assert result['error_code']=='AI_REFUSED' and result['safety_invariants_passed']
    assert not result['live_response_observed']


def test_reported_output_budget_violation_stops(tmp_path):
    class Excess(MeteredMock):
        def complete(self,*args,**kwargs):
            result=super().complete(*args,**kwargs);self.telemetry[-1]['usage']['completion_tokens']=601;return result
    result,stop=ev.execute_case(ev.CASES[0],Excess(),budget(),tmp_path)
    assert stop=='EVALUATION_PROVIDER_TOKEN_LIMIT_VIOLATION' and result['provider_calls']==1


def test_actual_unexpected_ledger_posting_trips_evaluation_safety_gate(tmp_path):
    from api.app import security as sec
    from api.app.contracts import ApprovalRequest
    def independent_payment():
        with closing(sqlite3.connect(tmp_path/'balance.sqlite3'))as db:
            o=sec.provision_session(db,'test-intervening-owner','evaluation-business','owner')
            a=sec.provision_session(db,'test-intervening-approver','evaluation-business','approver')
            proposal=sec.propose(db,sec.authenticate(db,o),'INV-105')
            sec.decide(db,sec.authenticate(db,a),proposal['proposal_id'],ApprovalRequest(proposal_hash=proposal['action_hash'],decision='approve'))
    result,stop=ev.execute_case(ev.CASES[0],MeteredMock(hook=independent_payment),budget(),tmp_path)
    assert stop=='EVALUATION_SAFETY_INVARIANT_FAILED'
    assert result['record_counts']['postings']==1 and result['balance_minor']==8500000
    assert not result['safety_invariants_passed']
