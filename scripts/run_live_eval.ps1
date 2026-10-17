# ============================================================
#  SafeLedger AI — LLM Eval & Final Steps
#  Run these commands ONE BY ONE in your PowerShell terminal
# ============================================================

# ── STEP 1: Set your Gemini API key privately (key is hidden, no echo)
#    Go to: https://aistudio.google.com/apikey → Create API key
#    Make sure your project shows "Free tier" with billing DISABLED.
#    Then run this — it will prompt you to paste the key (hidden):

$SAFELEDGER_LLM_API_KEY = Read-Host -AsSecureString "Paste Gemini API key"
$env:SAFELEDGER_LLM_API_KEY = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SAFELEDGER_LLM_API_KEY))

# ── STEP 2: Set all other required env vars for this session
$env:SAFELEDGER_LLM_PROFILE           = "gemini_free"
$env:SAFELEDGER_LLM_BASE_URL          = "https://generativelanguage.googleapis.com/v1beta/openai"
$env:SAFELEDGER_LLM_MODEL             = "gemini-3.5-flash-lite"
$env:SAFELEDGER_LLM_ALLOWED_HOSTS     = "generativelanguage.googleapis.com"
$env:SAFELEDGER_LLM_FREE_TIER_CONFIRMED = "1"

# ── STEP 3: Verify env is set (should show "READY")
if ($env:SAFELEDGER_LLM_API_KEY -and $env:SAFELEDGER_LLM_FREE_TIER_CONFIRMED -eq "1") {
    Write-Host "ENV READY - Key length: $($env:SAFELEDGER_LLM_API_KEY.Length) chars" -ForegroundColor Green
} else {
    Write-Host "ENV MISSING - check vars above" -ForegroundColor Red
}

# ── STEP 4: Run the preflight (zero API calls, just config check — should exit 3 or 0)
Set-Location "d:\China Comp\SafeLedger-AI"
& ".venv\Scripts\python.exe" scripts\evaluate_live_agent.py --free-tier --output evidence\preflight-live-1

# ── STEP 5: If preflight exits 3 with reason "LIVE_OPT_IN_REQUIRED" — that's GOOD (key found, just needs --live flag)
#    If it exits 3 with "AI_NOT_CONFIGURED" or "AI_FREE_TIER_CONFIRMATION_REQUIRED" — re-check steps 1+2.

# ── STEP 6: Run the LIVE evaluation (8 cases, max 14 API calls, free tier)
#    This WILL call Gemini. Make sure your project is Free tier.
& ".venv\Scripts\python.exe" scripts\evaluate_live_agent.py --live --free-tier --max-provider-calls 14 --output evidence\live-eval-1

# ── STEP 7: Check results
Get-Content evidence\live-eval-1\evaluation.json | python -c "
import json,sys
r=json.load(sys.stdin)
print('STATUS:', r['status'])
print('Provider calls:', r.get('provider_calls',0))
cases=r.get('cases',[])
print('Cases completed:', len(cases))
for c in cases:
    icon = '✅' if c['task_complete'] and c['safety_invariants_passed'] else '❌'
    print(f'  {icon} {c[\"case_id\"]:25s} task={c[\"task_complete\"]} safety={c[\"safety_invariants_passed\"]}')
"
