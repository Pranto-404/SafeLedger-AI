# Security self-assessment — M2 prototype
Not a certification. Authentication,source-bound proposals,separate human approval and sandbox posting now implemented. No real money/real customer data. Exact design/limits: M2_SECURITY_DESIGN.md; financial assumptions: FINANCIAL_METHODS.md.

| Risk | Implemented control / actual evidence | Remaining gate |
| --- | --- | --- |
| Unauthorized/self approval | Server token-derived roles; no self-approval; viewer/agent403; independent actor rechecked; tests + live HTTP | Public authentication lifecycle/MFA/deployment |
| Tenant leakage | Auth-derived business in queries; A/B proposal,audit,approval negative tests | Browser/public-host verification |
| Double posting/replay/race | BEGIN IMMEDIATE, unique invoice/proposal posting, paired ledger;8-thread service + HTTP tests;4-request live concurrent proof; process restart replay | Larger stability/load evaluation |
| Altered/expired approval | Immutable source hash,HMAC,expiry,version,strict body; forged hash/approval/state/source tests | Key rotation/public session renewal |
| Wrong money | Strict minor units,source checksums,conservation,forecast overlay/no double count; M1 + M2 regression | Independent reviewer |
| Prompt/tool abuse | Memo inert; agent cannot approve or call executor; backend tests deny privileged role | Real bounded LLM and provider attack corpus M3 |
| Upload/input/exfiltration |1MiB body cap,strict JSON/CSV,redacted validation; formula-escape helper; no raw tokens/memos in traces | User-facing upload/export UX |
| Audit alteration | Signed chained events + immutable triggers; tamper tests; offline SHA recompute; captured anchor | Privileged-prefix truncation requires external anchor; admin-proof claims disallowed |
| Outage/DoS | Fail-closed signatures/DB, transactional rollback,minute request budgets | Provider budgets/timeouts M3; public edge defenses M6 |
| Secrets/dependencies | Private generated local credentials,hashed stored tokens,.gitignore,secret-free demo output checks | Comprehensive history/dependency scan M5 |

No browser/device/keyboard,independent audit,real LLM evaluation or public deployment pass claimed. Code author executed the recorded tests; this is not independent sign-off. Release remains blocked on later end-to-end product and security gates.

## M3 implemented extension
Strict finite native tool plans,constrained fact-reference rationale,stale snapshot/identity checks,two-call/timeout/output/hourly budgets,fail-closed provider errors and deferred atomic proposal creation now mock/transport-tested. Viewer escalation,privileged tools,invented facts and malformed plans refused. M2 concurrent HTTP/process-restart regression rerun after integration. Real-model injection/task success remains unmeasured and blocked on private provider configuration. Deployment/automatic Git updates attempted but blocked by Vercel403 scope access; no URL or public QA success claimed.

## M5 local QA extension (2026-10-17)
Real browser/API/SQLite security failure paths and session/tenant isolation verified;stored HTML/prompt memo escaped;expired signed proposal/wrong approval hash/role and tenant bypass denied with no posting.225 pytest +10 full-flow browser scenarios +8 adversarial browser scenarios pass.10 axe scans have zero automated WCAG2/2.1A/AA violations after actual focus/contrast/label fixes;not a conformance certification. npm and Python lock advisory scans report zero known vulnerabilities after targeted Vite/esbuild/pytest patches. Limited all-reachable-history/tracked-tree credential-pattern scan reports no candidates;not a comprehensive external secrets/PII assessment. Exact limits,failures and evidence:docs/M5_QA_REPORT.md,evidence/m5/. Earlier pending rows describe their original checkpoint;this extension supersedes them where evidence exists. Independent external review,live-model evaluation,public-host/device tests and release gates remain open.
