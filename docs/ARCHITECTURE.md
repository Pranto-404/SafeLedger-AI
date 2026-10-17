# Implemented architecture and trust boundaries
Current at M5 local QA. Scope:synthetic BDT finance prototype,not a banking service.

React19/TypeScript uses same-origin /api requests to FastAPI/Pydantic. Vite proxy connects them locally. SQLite stores immutable imported datasets,private session hashes,policies,payee allowlist,proposals,approvals,postings,balanced ledger entries and signed audit events. Production same-origin routing and persistent backend hosting remain unconfigured.

## Authority
Financial truth comes from validated source records and deterministic integer-minor-unit Python services. Browser role labels/control visibility never authorize a request. Server authentication derives user,business and role from a random opaque bearer token's stored hash and active session. Generated private owner/approver/viewer/agent sessions expire;there is no public default credential,role switch or account provisioning route. Browser retains token only in memory.

LLM adapter sends a bounded task/context to an admin-allowlisted HTTPS provider. Strict native tool plans select finite read functions or one explicitly permitted invoice proposal. Structured rationale references backend facts. No tool approves/executes a payment or writes the ledger. Provider outages return503 while financial analysis continues. Adapter/tool/security behavior is mock/HTTP-transport tested;live provider configuration and real-model evaluation remain absent.

## Data and calculations
Imports validate up to1MiB JSON with unique keys,strict integer minor units,dates,currency,counts,source IDs and entity relationships. One immutable snapshot per business;atomic owner import adds signed audit evidence. CSV parsers/fixtures exist internally;the UI supports JSON upload only. Dataset checksums bind original sources.

Cleared events determine income,expenses and current balance. Scheduled events/open invoices after explicit as_of determine deterministic7/30-day forecasts. Linked obligations count once. Execution overlays a verified posting and removes its corresponding future payable,so a payment never reduces the forecast twice. Receipt-delay/reserve inputs change a scenario,not execution policy. Duplicate exact/near-match flags fail closed before a proposal. Three fictional offers use flat per-term interest and an upfront fee;cost ranking and affordability are backend calculations.

## Sandbox transaction
POST/api/proposals binds invoice,payee,amount,currency,business,proposer,source/dataset hashes,version and15-minute expiry into immutable signed details. It returns policy preview and changes no balance. A separate authenticated approver submits exact action hash plus approve/reject. No self-approval or public /execute exists.

BEGIN IMMEDIATE serializes execution. Server rechecks identity,independence,source integrity,hash,expiry,duplicates,allowlisted vendor,current funds,reserve and limit. Approval,unique posting,paired balanced ledger entries and chained audit commit together or roll back. Same approved action replay returns the existing posting;distinct concurrent proposals cannot overdraw. Tests include transaction failure,concurrency and real child-process restart.

## Audit and operational limits
HMAC-signed hash chain plus immutable triggers detect record alteration without the signing key. API verifies the tenant chain before audit export. Independent offline hashes/captured anchors support inspection. A privileged administrator controlling both DB/key can replace/truncate history;external durable anchors/key management remain future controls. No admin-proof claim.

Request budgets,provider call/time/output limits,redacted errors,no-store API responses and private credential files are implemented. Public TLS/security headers,session lifecycle/key rotation,backup/restore and hosted availability still need deployment verification. Persistent SQLite must survive process restart;ephemeral serverless disk is unsuitable. Vercel Git-project creation previously returned403. No public URL/auto-update success exists.

Detailed contracts:API_CONTRACT.md. Financial assumptions:FINANCIAL_METHODS.md. Security:M2_SECURITY_DESIGN.md,M3_AGENT_DESIGN.md,SECURITY_SELF_ASSESSMENT.md. Evidence:evidence/m5/verification.json. Production release/real-model/independent reviewer gates remain open.
