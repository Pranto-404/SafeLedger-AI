"""Owner-triggered provider capability check. Sends constants only, never workspace data."""
import json
from api.app.agents.models import NoArgs,Rationale
from api.app.agents.provider import ChatProvider,ProviderError,strict_json
from api.app.agents.runner import parse_calls


def synthetic_check(provider=None):
    p=provider or ChatProvider()
    if p.profile!='gemini_free':raise ProviderError('AI_FREE_ONLY_DIAGNOSTIC_REQUIRED')
    tools=[{'type':'function','function':{'name':'get_business_snapshot','description':'Read the synthetic test snapshot only','parameters':NoArgs.model_json_schema(),'strict':True}}]
    plan=parse_calls(p.complete([{'role':'system','content':'Synthetic capability test. Call get_business_snapshot exactly once with empty arguments. Do not output prose.'},{'role':'user','content':'Read the synthetic snapshot.'}],tools=tools))
    if len(plan)!=1 or plan[0][0]!='get_business_snapshot':raise ProviderError('AI_INVALID_TOOL_PLAN')
    selected=p.complete([{'role':'system','content':'Synthetic test only. Return exactly the supplied disposition, reason codes and fact IDs in the required JSON schema.'},{'role':'user','content':json.dumps({'disposition':'READ_ONLY','reason_codes':['VERIFIED_BALANCE'],'fact_ids':['synthetic-balance']})}],response_schema=Rationale.model_json_schema())
    if not isinstance(selected.get('content'),str) or selected.get('tool_calls'):raise ProviderError('AI_INVALID_RATIONALE')
    try:rationale=Rationale.model_validate(strict_json(selected['content']))
    except (ValueError,TypeError):raise ProviderError('AI_INVALID_RATIONALE') from None
    if rationale.disposition!='READ_ONLY' or rationale.reason_codes!=['VERIFIED_BALANCE'] or rationale.fact_ids!=['synthetic-balance']:raise ProviderError('AI_UNGROUNDED_RATIONALE')
    return dict(provider_name='Google Gemini',synthetic_data_only=True,tool_plan_validated=True,rationale_validated=True,provider_calls=p.calls,simulation_only=True)
