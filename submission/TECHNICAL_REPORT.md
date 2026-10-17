# Public release addendum — 18 October 2026

The competition prototype is publicly deployed at https://safeledger-ai.vercel.app. It now provides a login-free read-only example, self-service username/passphrase accounts with isolated synthetic workspaces, and one-time approver invitations. Render Free uses persistent Turso rather than an ephemeral authoritative SQLite file. Desktop/mobile viewport qualification and 23 actual public HTTP checks passed, including exactly one independent approved posting and its audit. A real configured-model balance query also passed; the earlier eight-case model report remains historical source-hash-verified evidence, not a statistical accuracy result.

Current backend regression: 304 passed (2 known warnings); local product browser qualification: 12 scenarios and 4 axe scans. See docs/PUBLIC_ACCESS.md and evidence/public-release/. Free service cold-start/quota limits and lack of password recovery are disclosed. Previous presentation and silent demo artifacts describe an earlier checkpoint and must be treated as historical until refreshed for final submission. This release does not submit the competition entry or claim independent certification.

---

# SafeLedger AI technical submission draft
Topic E:SME Finance Copilot. Five Bangladesh students reported by owner. Synthetic data/sandbox only. English draft for the2026 Shenzhen International FinTech Competition. Registration and public deployment remain incomplete.

## Problem and implemented workflow
An SME owner needs a source-backed answer to “Can this business pay an invoice while meeting upcoming obligations?” SafeLedger AI validates synthetic invoices/cash transactions,calculates exact balances,projects7/30-day cash flow,compares fictional financing and sends a payment proposal through independent human approval to an auditable sandbox ledger. The LLM integration supports bounded planning/explanation/proposal but still lacks live-provider evaluation.

The signature design is the Verified Decision Chain:financial evidence,deterministic calculation,AI recommendation,backend policy,explicit separate human approval,idempotent sandbox execution,verifiable audit. The tested manual workflow can skip the unavailable AI service. No test is presented as proof of a live recommendation. This is an implementation/design contribution,not a claim of globally unique invention or certified compliance.

## Components and algorithms
React/TypeScript frontend with8 connected views. FastAPI/Pydantic server owns authentication,tenant scope,input contracts and financial routes. SQLite stores immutable datasets and transactional execution/audit state. No extra queue/service architecture. docs/ARCHITECTURE.md and docs/API_CONTRACT.md define actual boundaries.

Money uses integer BDT minor units,with strict schemas rejecting booleans,floats,unsafe integers and unknown fields. Baseline opening10000000 +cleared inflows3000000 -cleared outflows1000000 =12000000 minor units(BDT120000). A legitimate INV-105 payment3500000 yields8500000. Paired ledger entries sum to0. Forecast overlay removes the paid future obligation,avoiding double deduction. Baseline7-day closing:-1500000;30-day closing:-1875000. The baseline first reserve breach is2026-10-22. These are synthetic fixture results,not market predictions.

Forecasts are deterministic scheduled-cash scenarios,not learned predictions. Receipt delay applies only to scheduled inflows. Source IDs accompany totals/day entries/risks. Duplicate matching normalizes vendor/reference/amount and conservatively blocks ambiguous repeats. Financing uses fictional BDT50000 principal/30-day offers,flat term interest/upfront fees,net proceeds,total repayment,total cost and modelled repayment capacity. No APR,real lenders,loan approval probability or advice to borrow is implied. docs/FINANCIAL_METHODS.md gives assumptions/rounding/caps.

## Agent boundary
Provider-neutral HTTPS adapter admits only configured hosts,finite typed tools,two-call/20-second deadline/output/token/hourly budgets and constrained rationale references. Backend facts remain authoritative. Caller must explicitly permit a single scoped proposal;model prose cannot determine permission. No approve,execute,SQL,secret or arbitrary-code tool. Live task accuracy/attack success is unmeasured until a privately configured real model is evaluated. Mock/MockTransport tests cover malformed calls,privilege escalation,unsupported facts,stale data/identity and outage.

## Security and evaluation
Random private bearer sessions,hashed DB tokens,server-derived role/tenant,independent approver,immutable action hash/HMAC/expiry,payee allowlist,reserve/payment limit,BEGIN IMMEDIATE,idempotent unique posting and chained signed audit. All financial mutations require server validation. No real customer/ID/bank data or banking connection. Known admin/key-management limits are explicit.

Published M5 source7996a563520b549f6034261ce7e718381c96843c:225 pytest passes;10 full workflow +8 adversarial actual browser scenarios;10 automated axe scans with0 violations. HTTP concurrency/replay/restart proof shows exactly1 posting under4concurrent approval requests/retry. Chromium Linux and360/390/768/1366px widths. Registry npm/pip-audit scans report0 known advisories after targeted patches. Limited history credential scan found0 known-pattern candidates. None of these establishes full security,WCAG certification,independent audit or real mobile/Safari coverage. Retained failure/fix evidence and precise commands:evidence/m5/,docs/M5_QA_REPORT.md. Fresh-clone results will be recorded separately in evidence/m6/reproducibility/.

## Reproduction and remaining delivery
Repository:https://github.com/Pranto-404/SafeLedger-AI. README contains locked setup/private demo commands and real browser runners. No public default token. Source-only recovery:PROJECT_STATUS.md/NEXT_STEPS.md. Deployment requires durable FastAPI/SQLite hosting,private signing/session settings and a same-origin frontend API route. Vercel's authorized project-creation attempt returned403;no deployment/autoupdate success claimed.

Before final submission:close live-model,independent QA,public HTTPS/restart/auto-update and clean-clone gates;choose project license/verify dependency attribution;confirm all students' eligibility/registration privately;review organizer delivery instructions;record final sourceSHA/video duration/presentation timing/receipt. Do not submit this draft as a fully released/deployed product without resolving the stated gates. See SUBMISSION_CHECKLIST.md.
