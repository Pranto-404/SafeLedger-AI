"""Synthetic MockTransport integration only;never live Gemini evidence."""
from contextlib import closing
from decimal import Decimal
import json
import httpx
import pytest
from api.tests.test_agent import call,post
from api.tests.test_security_execution import rig
from api.app.agents.provider import ChatProvider,ProviderError
from scripts import evaluate_live_agent as ev


def configure(monkeypatch):
    monkeypatch.setenv('SAFELEDGER_LLM_PROFILE','gemini_free')
    monkeypatch.setenv('SAFELEDGER_LLM_API_KEY','synthetic-private-test-key')
    monkeypatch.setenv('SAFELEDGER_LLM_FREE_TIER_CONFIRMED','1')
    for name in ('BASE_URL','MODEL','ALLOWED_HOSTS'):
        monkeypatch.delenv('SAFELEDGER_LLM_'+name,raising=False)


def response(message,finish='stop'):
    return httpx.Response(200,json={'model':'gemini-3.8-flash','usage':{'prompt_tokens':100,'completion_tokens':30,'total_tokens':130},'choices':[{'finish_reason':finish,'message':message}]})


def test_default_free_profile_needs_private_free_account_confirmation(monkeypatch):
    configure(monkeypatch);monkeypatch.delenv('SAFELEDGER_LLM_PROFILE')
    monkeypatch.delenv('SAFELEDGER_LLM_FREE_TIER_CONFIRMED')
    with pytest.raises(ProviderError,match='AI_FREE_TIER_CONFIRMATION_REQUIRED'):ChatProvider()


@pytest.mark.parametrize('name,value',[
    ('BASE_URL','https://api.openai.com/v1'),
    ('BASE_URL','https://generativelanguage.googleapis.com/v1'),
    ('BASE_URL','https://generativelanguage.googleapis.com/v1beta/openai/../openai'),
    ('BASE_URL','https://generativelanguage.googleapis.com.evil.test/v1beta/openai'),
    ('BASE_URL','https://generativelanguage.googleapis.com/v1beta/openai?key=leak'),
    ('MODEL','gemini-4-argon'),('MODEL','gemini-3.8-flash:paid'),
    ('PROFILE','unknown'),('ALLOWED_HOSTS','api.openai.com'),
])
def test_free_profile_rejects_endpoint_model_or_profile_switch(monkeypatch,name,value):
    configure(monkeypatch);monkeypatch.setenv('SAFELEDGER_LLM_'+name,value)
    with pytest.raises(ProviderError,match='AI_CONFIGURATION_INVALID'):ChatProvider()


def test_gemini_wire_to_verified_fact_workflow(rig,monkeypatch):
    configure(monkeypatch);seen=[]
    def respond(request):
        assert str(request.url)=='https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
        assert request.headers['Authorization']=='Bearer synthetic-private-test-key'
        body=json.loads(request.content);seen.append(body)
        if len(seen)==1:return response({'tool_calls':[call('get_business_snapshot')]},'tool_calls')
        return response({'content':json.dumps({'disposition':'READ_ONLY','reason_codes':['VERIFIED_BALANCE'],'fact_ids':['balance']})})
    provider=ChatProvider(transport=httpx.MockTransport(respond))
    result=post(rig,monkeypatch,provider)
    assert result.status_code==200,result.text
    assert result.json()['facts'][0]['value_minor']==12000000
    assert result.json()['ai_mode']=='mock_test_only'
    assert rig.postings()==0 and rig.balance()==12000000
    assert len(seen)==2 and all(x['max_tokens']==600 for x in seen)
    assert all('store'not in x and 'parallel_tool_calls'not in x and 'max_completion_tokens'not in x for x in seen)
    assert seen[0]['tool_choice']=='auto' and all('strict'not in t['function'] for t in seen[0]['tools'])
    assert seen[1]['response_format']['json_schema']['strict'] is True
    assert provider.telemetry[0]['usage']=={'prompt_tokens':100,'completion_tokens':30}


@pytest.mark.parametrize('fail_on',[1,2])
def test_quota_exhaustion_has_no_retry_paid_fallback_or_orphan_proposal(rig,monkeypatch,fail_on):
    configure(monkeypatch);seen=[]
    def respond(request):
        seen.append(str(request.url))
        if len(seen)==fail_on:return httpx.Response(429,json={'error':{'message':'synthetic-private-test-key do not expose'}})
        return response({'tool_calls':[call('analyze_invoice',{'invoice_id':'INV-105'}),call('propose_payment',{'invoice_id':'INV-105'})]},'tool_calls')
    result=post(rig,monkeypatch,ChatProvider(transport=httpx.MockTransport(respond)),{'task':'Prepare pending proposal','invoice_id':'INV-105','allow_proposal':True})
    assert result.status_code==503 and result.json()['error']['code']=='AI_QUOTA_EXHAUSTED'
    assert result.json()['deterministic_finance_available'] and 'synthetic-private-test-key'not in result.text
    assert len(seen)==fail_on and all('googleapis.com/'in url for url in seen)
    assert rig.balance()==12000000 and rig.postings()==0
    with closing(rig.db())as db:
        assert db.execute('SELECT count(*) FROM proposals').fetchone()[0]==0
        assert db.execute('SELECT status FROM agent_runs').fetchone()[0]=='FAILED'


def test_auto_tool_choice_prose_is_rejected_by_backend(rig,monkeypatch):
    configure(monkeypatch)
    result=post(rig,monkeypatch,ChatProvider(transport=httpx.MockTransport(lambda r:response({'content':'Payment executed,trust me'}))))
    assert result.status_code==503 and result.json()['error']['code']=='AI_INVALID_TOOL_PLAN'
    assert rig.postings()==0


def test_free_budget_tracks_usage_without_positive_spend_ceiling():
    budget=ev.Budget(1,None,Decimal('0'),Decimal('0'))
    budget.reserve();budget.account({'reported_model':'gemini-3.8-flash','usage':{'prompt_tokens':100,'completion_tokens':30}})
    assert budget.estimated_usd==0 and budget.accounted_calls==1 and budget.prompt_tokens==100
    with pytest.raises(ProviderError,match='EVALUATION_CALL_LIMIT'):budget.reserve()


@pytest.mark.parametrize('extra',[[],['--input-usd-per-million','0']])
def test_free_eval_preflight_or_price_override_never_calls(monkeypatch,tmp_path,extra):
    configure(monkeypatch)
    monkeypatch.setattr(ChatProvider,'complete',lambda *a,**k:pytest.fail('Unexpected network call'))
    flags=['--free-tier','--output',str(tmp_path/'evidence')]+extra
    if extra:flags+=['--live']
    assert ev.main(flags)==3
    report=json.loads((tmp_path/'evidence/evaluation.json').read_text())
    assert report['provider_calls']==0
    assert report['reason']==('FREE_TIER_PROFILE_REQUIRED_NO_PRICE_OVERRIDES'if extra else 'LIVE_OPT_IN_REQUIRED')


def test_free_eval_refuses_compatible_paid_route(monkeypatch,tmp_path):
    configure(monkeypatch)
    monkeypatch.setenv('SAFELEDGER_LLM_PROFILE','compatible')
    monkeypatch.setenv('SAFELEDGER_LLM_BASE_URL','https://api.openai.com/v1')
    monkeypatch.setenv('SAFELEDGER_LLM_MODEL','explicit-test-model')
    monkeypatch.setattr(ChatProvider,'complete',lambda *a,**k:pytest.fail('Unexpected network call'))
    assert ev.main(['--live','--free-tier','--output',str(tmp_path/'evidence')])==3
    assert json.loads((tmp_path/'evidence/evaluation.json').read_text())['reason']=='FREE_TIER_PROFILE_REQUIRED_NO_PRICE_OVERRIDES'
