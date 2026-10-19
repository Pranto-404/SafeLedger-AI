"""Adversarial synthetic failover checks. No real keys, credit balances or network."""
import json
import time
from types import SimpleNamespace
import httpx
import pytest
from api.app.agents import fallback
from api.app.agents.provider import ChatProvider,ProviderError
from api.app.agents.models import TaskRequest
from api.tests.test_accounts import world,signup
from api.tests.test_free_provider import configure,response


def provider(monkeypatch,handler,secondary=False):
    configure(monkeypatch)
    return ChatProvider(transport=httpx.MockTransport(handler),**({'profile':'compatible','base':'https://api.openai.com/v1','model':'synthetic-model','key':'secondary-synthetic-secret','allowed_hosts':{'api.openai.com'}} if secondary else {}))


def test_fallback_is_off_without_explicit_spend_authorization(monkeypatch):
    for key in ['SAFELEDGER_ALLOW_PAID_AI','SAFELEDGER_OPENAI_FALLBACK_ENABLED','SAFELEDGER_OPENAI_API_KEY','SAFELEDGER_OPENAI_MODEL']:monkeypatch.delenv(key,raising=False)
    primary=SimpleNamespace(profile='gemini_free')
    for key,value in [('SAFELEDGER_OPENAI_FALLBACK_ENABLED','1'),('SAFELEDGER_OPENAI_API_KEY','synthetic-key'),('SAFELEDGER_OPENAI_MODEL','synthetic-model')]:monkeypatch.setenv(key,value)
    assert fallback.with_authorized_fallback(primary) is primary
    assert not fallback.configured_secondary()
    monkeypatch.setenv('SAFELEDGER_ALLOW_PAID_AI','1')
    assert fallback.configured_secondary()


def test_quota_failover_uses_only_one_secondary_and_total_three_calls(monkeypatch):
    calls=[]
    p=provider(monkeypatch,lambda r:(calls.append('primary') or httpx.Response(429)))
    s=provider(monkeypatch,lambda r:(calls.append(str(r.url)) or response({'content':'synthetic'})),True)
    routed=fallback.ConsentFallback(p,s)
    assert routed.complete([{'role':'user','content':'synthetic question'}])['content']=='synthetic'
    assert routed.used_fallback
    routed.complete([{'role':'user','content':'synthetic second stage'}])
    assert calls==['primary','https://api.openai.com/v1/chat/completions','https://api.openai.com/v1/chat/completions']
    with pytest.raises(ProviderError,match='AI_CALL_BUDGET_EXCEEDED'):routed.complete([])
    assert routed.calls==3


@pytest.mark.parametrize('code',[400,401,403,404,500,502])
def test_non_quota_provider_rejections_do_not_silently_switch(monkeypatch,code):
    p=provider(monkeypatch,lambda r:httpx.Response(code))
    s=provider(monkeypatch,lambda r:pytest.fail('Unexpected secondary call'),True)
    routed=fallback.ConsentFallback(p,s)
    with pytest.raises(ProviderError,match='AI_PROVIDER_REJECTED'):routed.complete([])
    assert not routed.used_fallback


def test_secondary_failure_has_no_recursive_retry_or_secret_leak(monkeypatch):
    p=provider(monkeypatch,lambda r:httpx.Response(429))
    calls=[]
    s=provider(monkeypatch,lambda r:(calls.append(1) or httpx.Response(429,json={'error':'secondary-synthetic-secret'})),True)
    routed=fallback.ConsentFallback(p,s)
    with pytest.raises(ProviderError) as e:routed.complete([])
    assert str(e.value)=='AI_QUOTA_EXHAUSTED' and len(calls)==1


def test_expired_deadline_never_contacts_a_provider(monkeypatch):
    p=provider(monkeypatch,lambda r:pytest.fail('Expired call'))
    s=provider(monkeypatch,lambda r:pytest.fail('Expired call'),True)
    routed=fallback.ConsentFallback(p,s);routed.deadline=time.monotonic()-1
    with pytest.raises(ProviderError,match='AI_CALL_BUDGET_EXCEEDED'):routed.complete([])


def test_secondary_destination_is_fixed_without_environment_mutation(monkeypatch):
    for key,value in {'SAFELEDGER_ALLOW_PAID_AI':'1','SAFELEDGER_OPENAI_FALLBACK_ENABLED':'1','SAFELEDGER_OPENAI_API_KEY':'secondary-key','SAFELEDGER_OPENAI_MODEL':'synthetic-model','SAFELEDGER_LLM_PROFILE':'gemini_free','SAFELEDGER_LLM_BASE_URL':'https://generativelanguage.googleapis.com/v1beta/openai'}.items():monkeypatch.setenv(key,value)
    seen=[]
    monkeypatch.setattr(fallback,'ChatProvider',lambda **kwargs:(seen.append(kwargs) or SimpleNamespace(is_mock=True)))
    fallback.with_authorized_fallback(SimpleNamespace(profile='gemini_free',is_mock=True))
    assert seen[0]['base']=='https://api.openai.com/v1' and seen[0]['allowed_hosts']=={'api.openai.com'}
    import os
    assert os.environ['SAFELEDGER_LLM_PROFILE']=='gemini_free'
    assert os.environ['SAFELEDGER_LLM_BASE_URL']=='https://generativelanguage.googleapis.com/v1beta/openai'


def test_sharing_consent_and_configuration_status_remain_server_enforced(world,monkeypatch):
    c,_=world;signup(c,'consent_check')
    monkeypatch.setenv('SAFELEDGER_LLM_API_KEY','synthetic-key')
    monkeypatch.setenv('SAFELEDGER_LLM_FREE_TIER_CONFIRMED','1')
    monkeypatch.setenv('SAFELEDGER_LLM_MODEL','not-an-allowed-free-model')
    monkeypatch.setattr(ChatProvider,'complete',lambda *a,**k:pytest.fail('Consent not supplied'))
    r=c.post('/api/agent/tasks',json={'task':'hello','fallback_ai_consent':True})
    assert r.status_code==403 and r.json()['error']['code']=='EXTERNAL_AI_CONSENT_REQUIRED'
    status=c.get('/api/agent/status').json()
    assert not status['configured'] and status['configuration_error']=='AI_CONFIGURATION_INVALID'
    assert status['availability_checked'] is False
    assert 'synthetic-key' not in json.dumps(status)
    assert not TaskRequest(task='hello').fallback_ai_consent
