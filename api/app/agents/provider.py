"""Two-call-budget HTTP adapter. No model/provider credentials are hardcoded."""
import json
import os
import re
import time
from urllib.parse import urlsplit
import httpx


from api.app.agents.errors import ProviderError


def strict_json(text):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def finite(value):raise ValueError('Nonfinite JSON')
    return json.loads(text,object_pairs_hook=unique,parse_constant=finite)


class ChatProvider:
    is_mock=False
    def __init__(self,transport=None,*,profile=None,base=None,model=None,key=None,allowed_hosts=None):
        self.profile=profile if profile is not None else os.environ.get('SAFELEDGER_LLM_PROFILE','gemini_free')
        if self.profile not in {'gemini_free','compatible'}:raise ProviderError('AI_CONFIGURATION_INVALID')
        free=self.profile=='gemini_free'
        self.base=(base if base is not None else os.environ.get('SAFELEDGER_LLM_BASE_URL','https://generativelanguage.googleapis.com/v1beta/openai' if free else '')).rstrip('/')
        self.model=model if model is not None else os.environ.get('SAFELEDGER_LLM_MODEL','gemini-3.8-flash' if free else '')
        self.key=key if key is not None else os.environ.get('SAFELEDGER_LLM_API_KEY','')
        if not all([self.base,self.model,self.key]):raise ProviderError('AI_NOT_CONFIGURED')
        try:
            parts=urlsplit(self.base)
            allowed=allowed_hosts if allowed_hosts is not None else {x.strip().lower() for x in os.environ.get('SAFELEDGER_LLM_ALLOWED_HOSTS','generativelanguage.googleapis.com' if free else 'api.openai.com,ai-gateway.vercel.sh').split(',') if x.strip()}
            expected_path='/v1beta/openai' if free else '/v1'
            invalid=parts.scheme!='https' or not parts.hostname or parts.hostname not in allowed or parts.username or parts.password or parts.query or parts.fragment or parts.port not in (None,443) or parts.path!=expected_path
            if free:invalid=invalid or parts.hostname!='generativelanguage.googleapis.com' or self.model not in {'gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3-flash-preview', 'gemini-3.1-flash-lite', 'gemini-3.5-flash-lite'}
        except ValueError:raise ProviderError('AI_CONFIGURATION_INVALID') from None
        if invalid:raise ProviderError('AI_CONFIGURATION_INVALID')
        if not 1<=len(self.model)<=120 or len(self.key)>1024:raise ProviderError('AI_CONFIGURATION_INVALID')
        # A model name cannot establish account billing status. Owner must check
        # AI Studio shows Free tier with billing disabled before enabling calls.
        if free and os.environ.get('SAFELEDGER_LLM_FREE_TIER_CONFIRMED')!='1':raise ProviderError('AI_FREE_TIER_CONFIRMATION_REQUIRED')
        self.calls=0;self.deadline=time.monotonic()+90
        self.telemetry=[]  # Metadata only;never request bodies,keys or model prose.
        self.transport=transport
        self.is_mock=transport is not None

    def complete(self,messages,*,tools=None,response_schema=None):
        self.calls+=1
        remaining=self.deadline-time.monotonic()
        if self.calls>2 or remaining<=0:raise ProviderError('AI_CALL_BUDGET_EXCEEDED')
        payload={'model':self.model,'messages':messages,'max_completion_tokens':600,'store':False}
        if tools is not None:payload.update(tools=tools,tool_choice='required',parallel_tool_calls=True)
        if response_schema is not None:payload['response_format']={'type':'json_schema','json_schema':{'name':'verified_rationale','strict':True,'schema':response_schema}}
        if self.profile=='gemini_free':
            # Keep Google's beta compatibility request minimal. Backend requires
            # a valid tool plan even though the wire uses auto selection.
            payload.pop('store');payload.pop('max_completion_tokens')
            payload.update(max_tokens=600,reasoning_effort='low')
            if tools is not None:
                payload.pop('parallel_tool_calls');payload['tool_choice']='auto'
                payload['tools']=[{**t,'function':{k:v for k,v in t['function'].items() if k!='strict'}} for t in tools]
        encoded=json.dumps(payload)
        if len(encoded.encode())>24000:raise ProviderError('AI_INPUT_BUDGET_EXCEEDED')
        try:
            with httpx.Client(transport=self.transport,trust_env=False,follow_redirects=False,timeout=min(30,remaining)) as client:
                with client.stream('POST',self.base+'/chat/completions',headers={'Authorization':'Bearer '+self.key},json=payload) as response:
                    if response.status_code==429:raise ProviderError('AI_QUOTA_EXHAUSTED')
                    if response.status_code!=200:raise ProviderError('AI_PROVIDER_REJECTED',http_status=response.status_code)
                    chunks=[];size=0
                    for chunk in response.iter_bytes():
                        size+=len(chunk)
                        if size>65536:raise ProviderError('AI_OUTPUT_BUDGET_EXCEEDED')
                        if time.monotonic()>self.deadline:raise ProviderError('AI_TIMEOUT')
                        chunks.append(chunk)
            raw=strict_json(b''.join(chunks).decode('utf-8'))
            if not isinstance(raw,dict):raise ProviderError('AI_INVALID_RESPONSE')
            def tag(value):
                return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.:/-]{1,160}',value) and self.key not in value else None
            usage=raw.get('usage')
            valid=isinstance(usage,dict) and all(type(usage.get(k)) is int and 0<=usage[k]<=10**9 for k in ('prompt_tokens','completion_tokens'))
            if valid and 'total_tokens' in usage:
                if self.profile=='gemini_free':
                    valid=type(usage['total_tokens']) is int and usage['total_tokens']>=usage['prompt_tokens']+usage['completion_tokens']
                else:
                    valid=type(usage['total_tokens']) is int and usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
            self.telemetry.append({'requested_model':tag(self.model),'reported_model':tag(raw.get('model')),'response_id':tag(raw.get('id')),'usage':{k:usage[k] for k in ('prompt_tokens','completion_tokens')} if valid else None})
            choices=raw.get('choices')
            if not isinstance(choices,list) or len(choices)!=1:raise ProviderError('AI_INVALID_RESPONSE')
            choice=choices[0]
            if choice.get('finish_reason') not in {'stop','tool_calls'}:raise ProviderError('AI_INCOMPLETE_RESPONSE')
            message=choice.get('message')
            if not isinstance(message,dict) or message.get('refusal'):raise ProviderError('AI_REFUSED')
            return message
        except (httpx.HTTPError,TimeoutError):raise ProviderError('AI_TIMEOUT_OR_NETWORK_FAILURE') from None
        except (ValueError,UnicodeError,AttributeError,TypeError,RecursionError):raise ProviderError('AI_INVALID_RESPONSE') from None
