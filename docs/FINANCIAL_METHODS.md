# M1 finance methods and explicit limits
M1 provides internal services and a reproducible CLI. No financial HTTP endpoints, ledger posting, authenticated users or LLM exist yet. No real financial advice/provider is represented.

## Data and time contract
One immutable BDT snapshot: opening balance/source, opening_on, as_of, invoices, cash events. Amounts are strict integer poysha, positive for records, zero allowed for opening/reserve; no float, boolean or numeric-string coercion. `bdt_minor` accepts only nonnegative decimal strings with <=2 fractional digits, without hidden rounding. Maximum input amount 10^12 minor units. Date strings must be ISO YYYY-MM-DD; timestamps are rejected.

Opening is the start-of-day balance on opening_on. Cleared events must fall between opening_on and as_of inclusive. Snapshot balance = opening + cleared inflows - cleared outflows. Income/expenses here mean cleared cash movements, not accrual profit. No FX conversion. Future-issued invoices, partial settlements, mismatched/unknown invoice links, repeated event/source IDs and conflicting canonical duplicates are rejected.

Invoice status is open/paid. Optional CashEvent.invoice_id links a full-amount payable outflow to its invoice. Paid requires one canonical cleared event; open requires scheduled if linked. One event per canonical invoice; paid liability is excluded from forecast while its cleared cash effect remains. Unlinked cash events are additional independent movements: intake cannot infer an undocumented economic link, so user must link invoice settlements or it will count separate obligations.

## Projection
Scenario as_of must equal snapshot as_of. Horizon 7 or 30 days starts at as_of+1. Starting cash is snapshot balance; day closing = prior closing + scheduled inflows - scheduled outflows - open invoices not already represented by a scheduled linked event. Future cleared records are rejected, not silently guessed. Dates beyond horizon excluded; day7/day30 included. Past-due open payables/scheduled cash are moved to day1, with assumption disclosed. The delay scenario shifts only scheduled inflows after day1 normalization.

Safety shortfall = max(0,reserve - day closing). A negative projection is allowed as an alert; it is not permission to overdraw or an actual ledger posting. Minimum includes current opening cash and projected daily closings. Within-day ordering, new sales/tax, probabilistic confidence, seasonality and new interest are not modeled.

## Duplicates
Exact canonical key = stable vendor ID + uppercase ASCII alphanumeric invoice number (punctuation removed). Equal keys must have matching amount/date/status or import is rejected for correction. Identical canonical duplicates retain both source records, raise execution_blocked risk, and represent one economic liability in the forecast.

Possible duplicate = different canonical number, same vendor/issue date/amount AND Python SequenceMatcher ratio >=0.85 on normalized numbers. Related candidates are grouped. Both liabilities remain in the conservative projection and the risk flag requires review/block in M2. This is a documented heuristic, not a fraud classifier or proof that all duplicates are detected. Legitimate similar invoices can trigger review; unrelated numbers with equal amounts are not automatically flagged. Maximum1000 invoices caps the pairwise search.

## Fictional financing
Only flat_per_term, BDT, single maturity payments, equal principal and equal term comparisons are supported. All fees and rate conventions required. Interest minor = half-up(principal_minor * rate_bps /10000), implemented as integer arithmetic. Net proceeds = principal - upfront fee. Repayment = principal + interest. Total cost = repayment + upfront fee - principal. Rank by total cost with offer ID as stable tie-break; do not imply APR ranking.

Affordability = repayment <= supplied verified repayment_capacity_minor; gap = max(0,repayment-capacity). CLI capacity = max(0,30-day projected closing - safety reserve), excluding the proposed loan proceeds. It is a simple conservative reserve-adjusted capacity check, not a simulation of loan inflows, term-by-term debt service, eligibility or lender approval. Source IDs are preserved; future HTTP/LLM dispatch must derive them on the server and reject invented references. All three seeded offers are unaffordable in the baseline deficit scenario.

## Intake, atomicity and provenance
JSON/CSV <=1MiB; <=1000 invoices/2000 events, strict headers/encoding/dates and field errors. CSV numbers use integer minor units; no scientific/decimal/formula input. Malformed input returns field/line details without echoing raw rows. Memo remains untrusted data. Formula-safe export helper tested; no export endpoint implemented.

Internal staging imports validate the complete dataset before writes, then insert snapshot and all records in one SQLite transaction. Re-import of a business snapshot refuses replacement; updates/reset are future explicit workflows. Unique business/source/record keys preserve identities. Different business IDs may reuse their own source IDs; this storage separation is NOT an authenticated HTTP tenant isolation claim. Mid-import DB failure rolls back all rows.

Canonical sorted-key JSON SHA256 identifies dataset/each source record. Load revalidates dataset checksum and all source record payloads/digests/counts. Fixture manifest stores raw file checksums. These checks detect accidental changes against the stored digest; a privileged database writer could rewrite data and hashes together. No cryptographic audit tamper resistance is claimed in M1.
