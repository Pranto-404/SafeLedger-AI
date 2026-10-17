# Zero-money AI setup — Gemini Free Tier
Owner budget:BDT0. Default profile is now `gemini_free`. No paid service,billing activation,subscription or credit purchase is authorized. Actual Gemini evaluation is pending a private API key;HTTP mocks are not live-model evidence.

## Private setup
1. Open https://aistudio.google.com/ and use a project showing **Free tier**,with billing disabled. Do not add a card,link billing or upgrade. If unavailable,stop;deterministic finance remains available.
2. Create a Gemini API key privately. Never paste it into ChatGPT,Git,issues,screenshots,frontend variables or logs. Use only synthetic data:Google's free-tier terms permit content use to improve products.
3. Configure these backend environment variables privately. The application does not automatically load `.env` files:

```text
SAFELEDGER_LLM_PROFILE=gemini_free
SAFELEDGER_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
SAFELEDGER_LLM_MODEL=gemini-3.8-flash
SAFELEDGER_LLM_ALLOWED_HOSTS=generativelanguage.googleapis.com
SAFELEDGER_LLM_FREE_TIER_CONFIRMED=1
```

Set `SAFELEDGER_LLM_API_KEY` using private host secret settings. For local Bash,avoid putting its value in shell history:

```bash
read -rs SAFELEDGER_LLM_API_KEY
export SAFELEDGER_LLM_API_KEY
```

Paste the key into the hidden input and press Enter. Export the other settings in that same terminal before starting FastAPI. Confirmation is an owner acknowledgement,not independent billing verification. **A free-eligible model can also run on a paid project;the app cannot prove or enforce Google's project billing state.** Remove key/confirmation and stop requests if that state changes. No request occurs merely by constructing/importing the provider.

## Finite free evaluation
From the repo root,with private settings loaded:

```bash
.venv/bin/python scripts/evaluate_live_agent.py --free-tier --output evidence/free-preflight-NEW
.venv/bin/python scripts/evaluate_live_agent.py --live --free-tier --max-provider-calls 14 --output evidence/free-live-NEW
```

Use fresh paths. Preflight sends zero requests and deliberately exits3. `LIVE_OPT_IN_REQUIRED` means configuration passed,not a tested model. Missing key gives `AI_NOT_CONFIGURED`;missing confirmation gives `AI_FREE_TIER_CONFIRMATION_REQUIRED`. Run `--live` only after checking Free tier. Free evaluation rejects the legacy compatible profile and price/budget overrides. It tracks reported tokens with a zero-rate estimate whose account assumption is recorded;no paid allowance is implied. Missing usage/model metadata still fails.

Eight cases,at most14 attempts,600 requested output tokens/call,two calls/task,no retry,no execution. The600 cap may truncate a reasoning response;that is a visible failure,never silently relaxed. Google's compatibility endpoint is beta;actual tool/schema behavior,latency and quota require real evaluation. See LIVE_AGENT_EVALUATION.md for acceptance.

## Quota and security
HTTP429 becomes `AI_QUOTA_EXHAUSTED`,with503 API response and `deterministic_finance_available:true`. No retry,model switch,paid gateway or fabricated AI fallback. Planning/rationale failure creates no pending proposal or ledger posting. Existing dashboard,forecast,financing and explicitly human-approved sandbox routes remain available.

Exact HTTPS Google host/path and reviewed model are pinned. Broadening the host environment allowlist cannot redirect this profile to another provider. Paid-only/suffixed models are refused. No redirects/environment proxies. Gemini wire uses max_tokens,a minimal payload and tool_choice:auto;prose-only planning still fails server validation. Requested schemas never replace independent backend checks on tools,arguments,facts,permissions and disposition. Raw output is not displayed or logged. Legacy `compatible` profile remains for existing integrations/tests,never automatic fallback and not authorized for this zero-money deployment.

## Current sources and limits
Reviewed2026-10-17 UTC/18 BD:
- https://ai.google.dev/gemini-api/docs/pricing — gemini-3.8-flash Standard free input/output eligibility and free-tier data-use terms. Availability/quota can change;check actual project first.
- https://ai.google.dev/gemini-api/docs/openai — exact endpoint,Bearer key,tool calling and beta limitation.
- https://huggingface.co/docs/inference-providers/pricing — free inference credits currently$0.10/month,subject to change;not selected as default.

No claim of measured model accuracy,uninterrupted free service,public deployment or registration completion. Hosting is separate:DEPLOYMENT_STATUS.md. Do not put SQLite on ephemeral storage. Free hosting/Postgres support requires a separate verified milestone.
