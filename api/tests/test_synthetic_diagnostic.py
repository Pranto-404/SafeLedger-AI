import json
import httpx
import pytest
from api.tests.test_free_provider import configure,response
from api.tests.test_agent import call
from api.tests.test_accounts import world,signup
from api.tests.test_security_execution import rig
from api.app.agents.provider import ChatProvider,ProviderError
from api.app.agents.diagnostic import synthetic_check


def test_diagnostic_sends_only_constants_and_never_account_records(monkeypatch):
    configure(monkeypatch);payloads=[]
    def handler(r):
        body=json.loads(r.content);payloads.append(body)
        return response({'tool_calls':[call('get_business_snapshot')]},'tool_calls') if len(payloads)==1 else response({'content':json.dumps({'disposition':'READ_ONLY','reason_codes':['VERIFIED_BALANCE'],'fact_ids':['synthetic-balance']})})
    p=ChatProvider(transport=httpx.MockTransport(handler));result=synthetic_check(p)
    assert result['synthetic_data_only'] and result['provider_calls']==2
    assert result['tool_plan_validated'] and result['rationale_validated']
    sent=json.dumps(payloads)
    assert all(word not in sent for word in ['business_id','account_id','workspace_id','password','12000000'])


def test_diagnostic_rejects_unexpected_tool_without_second_call(monkeypatch):
    configure(monkeypatch)
    p=ChatProvider(transport=httpx.MockTransport(lambda r:response({'tool_calls':[call('propose_payment',{'invoice_id':'INV-105'})]},'tool_calls')))
    with pytest.raises(ProviderError,match='AI_INVALID_TOOL_PLAN'):synthetic_check(p)
    assert p.calls==1


def test_diagnostic_requires_owner_and_explicit_confirmation(rig,monkeypatch):
    monkeypatch.setattr(ChatProvider,'complete',lambda *a,**k:pytest.fail('Unexpected provider call'))
    assert rig.request('viewer','POST','/api/agent/diagnostic',json={'confirm_synthetic_test':True}).status_code==403
    assert rig.request('owner','POST','/api/agent/diagnostic',json={}).status_code==403
    assert rig.postings()==0


def test_provider_http_status_is_sanitized_and_no_error_body_is_exposed(world,monkeypatch):
    c,_=world;signup(c,'diagnostic_owner')
    from api.app.agents import diagnostic
    def failure():raise ProviderError('AI_PROVIDER_REJECTED',http_status=404)
    monkeypatch.setattr(diagnostic,'synthetic_check',failure)
    r=c.post('/api/agent/diagnostic',json={'confirm_synthetic_test':True})
    assert r.status_code==503 and r.json()['provider_http_status']==404
    assert set(r.json())=={'error','ai_status','deterministic_finance_available','provider_http_status'}
