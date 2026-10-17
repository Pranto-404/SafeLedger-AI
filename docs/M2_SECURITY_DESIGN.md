# M2 security boundary and actual scope
This is a synthetic-account prototype, not a compliance certification or real-money product. Local administrator and server environment are trusted. Public deployments, external bank connections, live LLM behavior and browser/mobile UX remain unverified.

## Authorization
Opaque random256-bit bearer sessions; only SHA256 token digests in SQLite. Tenant, role, expiry and active account are resolved from server tables; client X-Role/business fields are ignored, request extra fields rejected. Business queries scope every record by authenticated business. No session provisioning, role switching or ledger write HTTP endpoint. Owner imports; owner/approver/agent propose; only a separate approver identity can approve/reject. Independent approver rechecked inside the write transaction and immediately before execution. Tokens belong in Authorization, never URLs or cookies; ambient cookies cannot authorize a request. Generated credentials private,24-hour expiry, no public defaults. Public login/renewal/MFA not implemented.

Per-request connections use check_same_thread=False because FastAPI sync dependencies and handlers can run on different worker threads; connections are not shared between requests. BEGIN IMMEDIATE serializes the financial critical section; FK/unique constraints enforce associations and one posting per invoice/proposal. HTTP concurrency is tested, not just pure service concurrency.

## Verified Decision Chain (AI stage pending M3)
1. Financial import validates source identities/money and atomically stores dataset + source hashes + import audit. Import cannot authorize a vendor or replace an existing snapshot.
2. Deterministic services compute snapshot/forecast/comparison.
3. Proposal derives invoice/vendor/amount/currency/source checksum/dataset checksum on server; binds proposer,tenant,version,created_at and900-second expiry. SHA256 action hash and namespace-specific HMAC protect immutable payload. DB trigger forbids alteration.
4. Policy denies exact/possible duplicate, already-paid invoice, unknown/disabled vendor, amount over limit, missing policy, insufficient cash after reserve or runtime capacity. Pure prototype configured payee IDs, not bank accounts. No inference of bank verification.
5. Distinct authenticated human supplies exact action hash and approve/reject. Approval MAC binds actor,decision,hash,time; immutable once written. Self-approval and agent approval denied.
6. Approval + server-only execution run inside one locked transaction. Recheck current session/role,source,expiry,approval signature,allowlist,limits and funds. Insert unique posting + two offsetting cash/payables entries + audit; verify resulting balance before commit. Failure rolls all financial state back and records denial separately when infrastructure supports it. Failed denial logging returns503; it is not silently treated as audited.
7. Hash-linked UTC audit events have namespace-specific HMAC and append-only triggers. Export includes full tenant chain; public SHA hashes can be recomputed offline. Server verifies HMAC before returning chain_verified. Actual exported head is retained as evidence anchor.

Idempotent approved-action replay returns the existing posting, including after actual process restart; it never consumes funds again. Rejected/expired/unapproved actions cannot execute. Pending proposal retry returns same immutable proposal; re-propose after expiry creates a new one. An already-executed approval retry can return its receipt after proposal expiry, provided current approver is authenticated and integrity checks pass; that is not another execution.

Immutable imported dataset stays unchanged. Runtime analysis overlays verified posted entries, marks the invoice paid, replaces its scheduled settlement with cleared posting evidence, and advances as_of to posting's Bangladesh business date as necessary. No double deduction in cash flow. Historical data remain a simulation snapshot; this is not bank balance freshness verification.

## Input and abuse limits
1MiB ASGI body cap before parsing; JSON content type; invalid encoding/JSON,duplicate keys and nonfinite constants rejected; Pydantic strict financial fields and extra-field denial. API validation errors omit input/ctx. Route IDs bounded. Per-session240 GET or60 mutation/read-POST requests/minute; invalid-auth peer budget20/minute. Socket peer used directly; no untrusted forwarded-IP authority. Database errors reveal only generic code; server diagnostics log exception class, not raw SQL or tokens. No CORS wildcard/cookie credentials. Browser deployment headers/HTTPS are M6 gates.

## Known limits
- No live LLM, no browser UI workflow, no independent audit, no dependency vulnerability scan or public hosting verification yet.
- Persistent signing secret is mandatory for signatures; lost/wrong key makes operations fail closed. Key rotation/public session renewal are not implemented. Trusted local admin can provision new sessions without replacing financial data; a supported CLI renewal flow is future work.
- Privileged attacker controlling server code/environment/DB can drop triggers/rewrite state. HMAC blocks changes without signing key; truncation to a valid audit prefix requires an independently retained head/count to detect. Do not claim administrator-proof immutability or non-repudiation.
- Runtime dataset cap2000 cash events. If a payment would exceed it without replacing a linked settlement, policy denies. Single currency,full invoice settlements and M1 financial assumptions apply.
- Rate limits are prototype minute buckets, not a distributed perimeter/WAF. SQLite is one persistent backend instance; operational hardening and public-auth lifecycle remain deployment gates.
- AI recommendation stage and adversarial provider output tests are M3 work. Current malicious-memo tests prove backend authority cannot be changed by stored text, not live-model injection robustness.
