# Requirements baseline — frozen M0, 2026-10-17 Asia/Dhaka
Authority: uploaded organizer Appendix 2 (4 pages), then uploaded SafeLedger playbook (24 pages), then implementation decisions documented here. Read once during M0; preserve this concise baseline. Attachment hashes: SOURCE_MANIFEST.json.

## Official rules
- Theme: AI as a Financial Participant. Topic E: financing matching, cash-flow management/alerts, business financial analysis (p2).
- Scores: task completion 40%, security/compliance 30%, innovation/interaction 30%. On-chain challenge bonus is not a Topic E target (p2; wording on F bonus is internally awkward).
- Deadline: registration AND submission by 2026-10-20 23:59 UTC+8 = 21:59 Bangladesh = 15:59 UTC (p3). No later updates.
- Team: 2–5 full-time students at eligible institutions outside Mainland China, Hong Kong, Macao and Chinese Taipei; >=60% non-Chinese nationals; one team per person across tracks (p3). Five Bangladesh students is reported, not independently verified eligibility.
- English submissions/reviews/presentations (p3).
- Technical documentation: architecture, core algorithms, security. Deck <=10-minute presentation. Source: README, GitHub link, deployment instructions, tests. Security assessment: permission tiers, known risks (p3).
- Demo is called optional in general checklist but sandbox execution evidence explicitly asks for logs AND demo video for non-on-chain topics. Produce <=5-minute video to satisfy both (p3).
- At least one invited finalist attends Shenzhen in person. Finalists announced Oct31; finals Nov21–23. Independent work, attribution, IP and licensed dependencies required (p4).
- Printed contact: wangyr@pbcsf.tsinghua.edu.cn; site fintechathon.g-ican.com (p4). Exact registration form and delivery workflow are NOT established by Appendix2. No outbound requests authorized.

## Product acceptance scope (owner/playbook, not extra organizer rules)
- Validated synthetic invoices and cash events; source IDs and checksums; one ledger currency BDT; strict integer minor units; no float money.
- Exact income, expenses, reconciliation; deterministic 7/30-day projections distinguish cleared and scheduled cash, count invoices/receipts once. Duplicate exact/near match blocks execution. Explain assumptions, reserve/shortfall.
- Three clearly fictional offers: total fees/repayment, stated rate convention, term and affordability; no invented APR or approval odds.
- Bounded schema-validated LLM read/propose tools only. No agent approval/execution or ledger write; source validation beyond schema. AI outage leaves deterministic analysis available.
- Verified Decision Chain: evidence -> calculation -> AI recommendation -> backend policy -> separate authenticated human approval -> atomic idempotent sandbox execution -> verifiable trace.
- Tenant identity/role from authenticated server state; owner/proposer cannot self-approve. Proposal binds immutable amount, invoice, payee, currency, tenant, actor, expiry, version. Execution rechecks funds, duplicates, expiry and authorization.
- React/TS, FastAPI/Pydantic, SQLite persistent prototype; pytest, Playwright. Responsive 360/390/768/1366 widths and keyboard flow; real loading/errors/empty states.
- Release blockers: unauthorized/unapproved posting; money mismatch; duplicate posting; forged/expired/altered approvals; tenant leaks; prompt injection policy bypass; missing E2E execution evidence; reproducible critical crashes.
- No live transfers, real customer/ID/banking data, arbitrary code/SQL, fabricated test evidence, compliance certification claims or finalist guarantees.

## Registration — immediate P0 dependency (owner)
UNCONFIRMED. Obtain official Appendix3 form and confirm submission channel/required fields; check all five students' enrollment, nationality and single-team eligibility privately; resolve ID alternatives with organizer evidence if necessary. Record only redacted sent/receipt status. Do not put identities or IDs in Git. Do not send without explicit owner instruction. Product delivery is not registration.

## Schedule and change control
Oct17: M0 then M1 financial core. Oct18: M2 gated execution then M3 constrained AI. Oct19: M4 integration then M5 security/E2E; evening freeze if all P0 pass. Oct20: M6 reproducibility, deployment and submission well before 21:59 BD. Targets, not completed work; narrow optional scope if gates slip. One milestone at a time; no autonomous agent fleet.
