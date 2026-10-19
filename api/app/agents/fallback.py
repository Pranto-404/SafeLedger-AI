"""Explicit-consent, bounded failover. Disabled by default under the zero-spend policy.
No ChatGPT browser/subscription reuse, hidden provider switch, key rotation or automatic billing.
"""
import os
import time
from api.app.agents.provider import ChatProvider, ProviderError

RECOVERABLE={'AI_QUOTA_EXHAUSTED','AI_TIMEOUT_OR_NETWORK_FAILURE','AI_TIMEOUT'}


def configured_secondary():
    # OpenAI API usage is metered; a subscription or env flag cannot make it free.
    # Production defaults must remain free-only until the owner authorizes API spend.
    return (os.environ.get('SAFELEDGER_OPENAI_FALLBACK_ENABLED')=='1'
            and os.environ.get('SAFELEDGER_ALLOW_PAID_AI')=='1'
            and bool(os.environ.get('SAFELEDGER_OPENAI_API_KEY'))
            and bool(os.environ.get('SAFELEDGER_OPENAI_MODEL')))


class ConsentFallback:
    def __init__(self,primary,secondary):
        self.primary=primary;self.secondary=secondary;self.current=primary
        self.calls=0;self.deadline=time.monotonic()+90
        self.is_mock=primary.is_mock and secondary.is_mock
        self.used_fallback=False

    @property
    def telemetry(self):return self.primary.telemetry+self.secondary.telemetry

    def complete(self,messages,**kwargs):
        if self.calls>=3 or time.monotonic()>=self.deadline:raise ProviderError('AI_CALL_BUDGET_EXCEEDED')
        self.calls+=1;self.current.deadline=min(self.current.deadline,self.deadline)
        try:return self.current.complete(messages,**kwargs)
        except ProviderError as exc:
            # Invalid output, authentication/configuration failures and refusals are not retried.
            if self.current is not self.primary or exc.code not in RECOVERABLE:raise
            if self.calls>=3 or time.monotonic()>=self.deadline:raise
            self.current=self.secondary;self.used_fallback=True
            self.calls+=1;self.secondary.deadline=min(self.secondary.deadline,self.deadline)
            return self.secondary.complete(messages,**kwargs)


def with_authorized_fallback(primary):
    if not configured_secondary() or primary.profile!='gemini_free':return primary
    secondary=ChatProvider(profile='compatible',base='https://api.openai.com/v1',
                           model=os.environ['SAFELEDGER_OPENAI_MODEL'],key=os.environ['SAFELEDGER_OPENAI_API_KEY'],
                           allowed_hosts={'api.openai.com'})
    return ConsentFallback(primary,secondary)
