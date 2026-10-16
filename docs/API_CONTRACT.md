# API v1 scope freeze
Money fields end in `_minor`, strict integer poysha (100 per BDT); BDT only. Dates ISO yyyy-mm-dd; audit timestamps UTC. Request bodies forbid unknown fields; caller cannot choose authoritative business_id, role, payee or payment amount. Errors: 401 missing/expired auth, 403 forbidden, 404 inaccessible record, 409 policy/state conflict, 422 validation with field locations, 429 budget, 503 dependency unavailable. Never return secret/provider payloads.

## Implemented M0
GET /api/health -> status, version, build_commit, simulation_only=true, milestone=M0, ai_status=not_configured.
GET /api/ready -> database=sqlite, schema_version=1, status=ready; redacted 503 if unavailable.
No business data or financial mutation endpoints exposed. `/docs` shows implemented API only.

## Frozen planned routes — NOT implemented
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
