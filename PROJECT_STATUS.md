# SafeLedger AI — verified checkpoint
Updated:2026-10-17 Asia/Dhaka. Deadline:2026-10-20 21:59 BD/15:59 UTC.

## DONE
M0 requirements/bootstrap and M1 finance foundation preserved. M2 implemented: private hashed bearer sessions,server-derived tenant/roles,authenticated financial APIs,immutable source/hash/expiry/version-bound proposals,HMAC signatures,separate human approval,no public executor,atomic idempotent sandbox posting/paired ledger,audit chain and full export,request/input limits,private local bootstrap and actual HTTP demo.

## VERIFIED
- `../.venv/bin/python -m pytest -q --junitxml=evidence/m2/pytest.xml`:174 passed,2 known warnings; zero skipped/disabled. Includes earlier M0/M1 plus auth/IDOR,self-approval,forged/expired approvals,state/source/audit tampering,duplicate invoice policy,rate limits,input rejection,transaction rollback,8-thread service and HTTP concurrency,competing-invoice funds race and private credential generation.
- `../.venv/bin/python scripts/m2_http_demo.py`: actual uvicorn process,duplicate/viewer/hash denial,4 concurrent human approvals plus retry produce one posting. Cash BDT120,000 ->85,000; paired entries sum0;30-day projection unchanged after posting because invoice is not deducted twice. Actual process terminated/restarted; replay retained same posting. Full11-event audit chain offline SHA recomputation passed. Actual evidence/logs in evidence/m2/.
- `cd web && npm run build`: TypeScript/Vite pass. `compileall`,M1 standalone demo regression and staged source whitespace checks passed.
- Source/tree identity and exact tested commit recorded in evidence/m2/verification.json at publication. Initial failures retained: M0 endpoint-expectation migration,local proxy harness failure,and real HTTP SQLite worker-thread ProgrammingError. Fixed per-request thread handoff; HTTP regression and actual server retest pass.
- Browser/mobile/keyboard E2E,live LLM/attack corpus,independent reviewer and dependency vulnerability audit NOT run. No financial frontend workflow yet; current page is connectivity/status only. No real money or real customer data used.

## BLOCKED / owner items
Registration NOT completed; owner explicitly said they will handle later. No external registration/ID action authorized or performed. Do not block coding on this; do not claim registered.
M3: LLM provider/model/budget/API configuration not established; keep secrets out of chat/Git/logs. Provider-neutral adapter can be built; actual live-model evaluation cannot be claimed without configured access.
M6: authorized persistent Python backend/public deployment target and project licensing/attribution review remain open. Connected GitHub Pranto-404/SafeLedger-AI is authorized; write through connector with expected HEAD,terminal Git read/fetch works. No forced shared history.
Known prototype limits: one BDT currency,full settlement,immutable imported snapshot,2000-event runtime cap,private24-hour demo sessions,no public renewal/MFA,stable secret needed across restarts,local admin trusted. Audit prefix truncation needs independently retained anchor; no administrator-proof/compliance claim.

## Next exact action
M3 only: constrained provider-neutral LLM adapter + finite READ/PROPOSE dispatch under caller's actual authorization,per-tool strict schemas,server-derived numbers/source IDs,timeout/call/token/request budgets,invalid/forged-source refusal and explicit AI-offline503. No approve/execute/role/admin tools. Preserve M2 tests. Use synthetic/mock providers for adversarial integration tests; label mocks and save actual eval evidence. Obtain private provider configuration before live claims. M4 frontend follows passing M3 contract/safety gate.

## Recovery
Read this file,NEXT_STEPS.md and git history; use docs/REQUIREMENTS.md instead of rereading PDFs. M2_SECURITY_DESIGN.md and FINANCIAL_METHODS.md describe implemented controls and limits. Do not overwrite features or reset private DB/credentials. Publish verified code/status/evidence checkpoint after each milestone; compare remote/local tree SHA before aligning local branch.
