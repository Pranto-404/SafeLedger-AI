# M0 architecture and trust boundaries
Single React/TypeScript frontend -> same-origin FastAPI -> SQLite on persistent disk. LLM provider adapter calls bounded READ/PROPOSE tools via server dispatch. Separate human approval and server transaction executor control ledger changes. No additional services until necessary.

Financial truth lives in deterministic Python services and validated DB records. Uploaded memo is untrusted data. Provider narrative never supplies authoritative monetary values, source IDs or permissions. Frontend displays server state; never optimistic execution success.

M0 only: liveness, SQLite schema readiness, development UI and strict input contracts. Authentication, financial services, persistence entities, tool dispatch, approval and audit are not implemented.

M1: read-only deterministic engine and validated staged imports. Keep authenticated data routes closed until M2 server sessions and tenant scoping exist; unit-test finance core independently. M2: server-side bearer sessions from isolated seeded accounts; hashed tokens in DB, expiry, role and tenant from server state. No shared public default credentials. Agent identity cannot inherit human approval privilege. Token transport, rate limits and deployment headers require testing before exposure.

M2 execution transaction: BEGIN IMMEDIATE; fetch tenant-scoped immutable proposal; verify hash/version/expiry/independent approval; recheck duplicates, allowlisted payee and funds/reserve; write uniquely constrained proposal posting, paired balanced entries and hash-linked audit event; commit all or rollback. Idempotent retry returns same execution ID. Approval consumes only once; no public direct ledger endpoint. Concurrent distinct proposals must not overdraw. Audit tamper evidence does not protect against a privileged DB admin rewriting the whole chain; export anchored digest with release evidence.

Single currency BDT, UTC audit timestamps, Asia/Dhaka business dates. Explicit as_of date prevents runtime-clock-dependent fixture forecasts. Cleared cash affects current balance; scheduled events after as_of affect forecasts. Invoice obligations linked to events to prevent double counting. Paid invoices excluded from future payables.

M3 provider-neutral structured adapter: finite tool list, per-tool Pydantic arguments, time/call/token budget, provenance/numeric fact verification, no approval or execution functions. AI offline shown explicitly; no fallback presented as a real LLM result.

Deployment: frontend Vercel if selected account available, Python backend on an authorized persistent host. SQLite must survive restart. Static frontend build alone cannot host FastAPI/SQLite. Do not assume backend account access.

## M2 implemented status
Authenticated bearer sessions,tenant-scoped routes,immutable source-bound HMAC proposals,separate human approval,atomic idempotent sandbox ledger and signed audit chain are now implemented and tested. See M2_SECURITY_DESIGN.md for actual controls and limits; evidence/m2/ for real HTTP/process-restart/concurrency results. M3 LLM,M4 finance UI and M6 public deployment remain future work.
