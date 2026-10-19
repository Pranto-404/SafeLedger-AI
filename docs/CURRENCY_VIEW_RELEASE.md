# Currency view — 2026-10-19

Scope: first stage only. Guided tutorial and unified local/online assistant are pending until the user says continue.

All supported currencies can now be selected from View currency on every workspace page, irrespective of records or role. Conversion requires an explicit user-entered rate (target major units per one ledger major unit). No exchange-rate network request, paid service, default rate, or financial record is created. Pending choices do not alter figures until Apply rate. Original-currency selection clears the converted view immediately.

The conversion uses integer rational arithmetic with BigInt, rounding half away from zero only for final target minor units. Converted figures carry ≈ and the manually supplied rate/date; they are reference amounts, not live quotes or restatements. Original records, payment approval details, entry parsing, exports, signed proposals and assistant financial facts retain their ledger currency. Existing backend integrity constraints remain in force. The owner can still select the actual record currency while a workspace is empty.

Preferences persist only in the current browser, separately by account and workspace, with schema versioning and validation. Storage failure leaves in-session switching usable. No account data or authentication token is stored by this feature. Another device will require its own selection/rate.

Validation: production TypeScript/Vite build; currency parsing tests for 0/2/3/4 decimals; exact reporting conversion tests covering positive/negative rounding, safe-integer-boundary amounts, invalid rates and stored preference validation; 17 backend currency/security regression tests; local assistant evaluation (36 supported, 22 out-of-domain abstentions, 8 security cases). The assistant's currency instructions now describe the new UI. No new AI capability changes in this stage.
