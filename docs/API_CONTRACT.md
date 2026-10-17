# API v1 scope freeze
Money fields end in `_minor`, strict integer poysha (100 per BDT); BDT only. Dates ISO yyyy-mm-dd; audit timestamps UTC. Request bodies forbid unknown fields; caller cannot choose authoritative business_id, role, payee or payment amount. Errors: 401 missing/expired auth, 403 forbidden, 404 inaccessible record, 409 policy/state conflict, 422 validation with field locations, 429 budget, 503 dependency unavailable. Never return secret/provider payloads.

## Implemented M0
GET /api/health -> status, version, build_commit, simulation_only=true, milestone=M0, ai_status=not_configured.
GET /api/ready -> database=sqlite, schema_version=1, status=ready; redacted 503 if unavailable.
No business data or financial mutation endpoints exposed. `/docs` shows implemented API only.

## Original M0 route plan — implementation status superseded by M2 section below
| Method/route | Contract and gate |
| --- | --- |
| POST /api/invoices/import | Owner; ImportRequest structured JSON first; atomic validation, preserve source IDs, line errors for later CSV support; reject payloads >1MiB; <=1000 invoices/2000 events. Invalid batch writes nothing. |
| GET /api/dashboard | Authenticated tenant snapshot; current balance, cleared credits/debits, source IDs and as_of; no fabricated metrics. |
| POST /api/cashflow/scenarios | ScenarioRequest; as_of, 7/30 days, reserve_minor, optional inflow delay; daily values, shortfalls, source IDs, assumptions. |
| POST /api/finance/compare | Server fictional offer IDs + requested principal; reject missing conventions; totals and affordability assumptions. |
| POST /api/agent/tasks | Authenticated task <=2000 chars; finite tool calls; schema and provenance validation; degraded 503 on unavailable provider. |
| POST /api/proposals | ProposalRequest invoice_id only; server derives immutable financial fields; owner/approver or constrained agent; deny duplicate or prohibited payee. Never posts ledger. |
| POST /api/proposals/{id}/approve | ApprovalRequest exact hash + approve/reject; distinct authenticated human approver, no role from body. Human explicitly confirms payee/amount/hash. |
| POST /api/proposals/{id}/execute | Not a public client/LLM endpoint. Internal executor invoked after approval transaction; retries use server proposal ID as stable idempotency key. |
| GET /api/audit/{trace_id} | Authenticated matching tenant; redacted ordered events and hash chain. |

Models in api/app/contracts.py freeze M1 inputs and basic approval envelopes. AgentToolCall is only an outer envelope; arguments remain untrusted until M3 per-tool dispatch validation. No claim that schema alone prevents prompt injection.

Legal persisted transitions: AWAITING_APPROVAL -> APPROVED/REJECTED/EXPIRED; APPROVED -> EXECUTED/EXPIRED/DENIED. DRAFT and VALIDATED are transient validation stages before persistence; initial validation denial may persist DENIED. No skip to execution. Changed proposal requires new ID/hash and new approval. Approval expiry checked again at execution.

Execution idempotency: repeat valid request for the same completed proposal returns same posting; expired or altered unexecuted proposals cannot execute. Unique tenant+proposal posting key; atomic double-entry writes and audit. Final schemas for response fields require a documented versioned extension before M1 exposes them.

## M1 internal contract extension (2026-10-17)
InvoiceInput now has status open/paid (default open); CashEventInput has optional invoice_id. Strict ISO-date validation rejects timestamps. Internal Dataset extends import with opening_source_id/opening_on/as_of/opening_balance_minor/currency; validates IDs, canonical duplicate economics, settlement consistency and historical dates. Scenario/financing service outputs and assumptions are documented in FINANCIAL_METHODS.md. These services do not expose business HTTP routes until M2 authentication. GET health now reports milestone=M1, version0.1.0. This extends M0 inputs without introducing monetary write authority.

## M2 implemented authenticated routes
All business routes require Authorization: Bearer <private opaque session token>. Tenant/role come from DB. Session configuration is local administrator only. Headers/cookies/body cannot assign privilege. GET /api/session reports current role/tenant only to its authenticated session. GET /api/health now version0.2.0/milestoneM2; readiness still checks bootstrap SQLite schema.

- POST /api/invoices/import: owner; full Dataset envelope including opening/as_of fields; validates before atomic import+audit, no existing snapshot replacement;201 or409. Never auto-allowlists a payee.
- GET /api/dashboard, GET /api/invoices: own-business runtime data with posted effects once.
- POST /api/cashflow/scenarios: M1 ScenarioRequest; as_of must equal current runtime date, otherwise409 SNAPSHOT_DATE_CHANGED_REFRESH_REQUIRED.
- POST /api/finance/compare: {principal_minor}; server selects fixed fictional quotes and derives repayment capacity/source IDs. Unsupported principal returns422; caller cannot invent fee/rate/capacity.
- POST /api/proposals: {invoice_id};201 with proposal_id,state,action_hash,immutable details and verified policy preview. Never posts ledger.
- GET /api/proposals, GET /api/proposals/{UUID}: own-business proposals. No cross-tenant IDs.
- POST /api/proposals/{UUID}/approve: {proposal_hash,decision:approve|reject}; separate human approver. Returns REJECTED or EXECUTED with stable posting_id,balance and simulation marker. Server execution runs in same transaction. Retry returns same posting; no public /execute route.
- GET /api/audit/{trace_id}: filtered own-tenant timeline after full chain verification; GET /api/audit: complete own-tenant export and anchor.

Policy errors {error:{code}}; auth401,permission403,inaccessible404,state/integrity409,validation422,budget429,dependency/DB503. Strict validation redacts raw input. No real transfer endpoint. Server-only execute_approved validates independent human actor, authenticated session, approval MAC,immutable source and policy even if called internally; never expose it to the agent.
