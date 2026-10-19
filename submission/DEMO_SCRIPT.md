# Demo video script (≤ 5 minutes): current release 0.4.0

Record against https://safeledger-ai.vercel.app at commit `30ecef8` or later. **Open the site 2 minutes before recording** so the free Render backend is warm. Use two fresh accounts you create for the video (owner and approver). Enter only made-up business figures. Never show passwords, recovery codes, browser dev tools or URLs containing tokens. Do not cut a failed step into a fake success: re-record instead.

Prepare before recording (off camera): the owner account with these records added on the **Data** page (dates relative to today):

| Record | Type | Amount (BDT) | Date |
| --- | --- | --- | --- |
| Opening cash from bank statement | Cash in, cleared | 150,000 | today |
| Raw material purchase | Cash out, scheduled | 420,000 | today + 6 |
| Customer receivable (export order) | Cash in, scheduled | 600,000 | today + 25 |
| Rahman Logistics RL-552 | Unpaid invoice, payee allowed | 20,000 | due today + 3 |
| Dhaka Packaging DP-1182 | Unpaid invoice, payee allowed | 35,000 | due today + 10 |
| Dhaka Packaging DP-1182-A (same vendor, date, amount: a resent copy) | Unpaid invoice | 35,000 | due today + 10 |

Financing quotes to type on camera (quote date = today):

| Lender | Product | Amount | Fees | Rate | Basis | Term / repayment |
| --- | --- | --- | --- | --- | --- | --- |
| Prime Bank SME desk | Term loan | 400,000 | 4,000 | 13.5 | Per year, reducing | 12 months, monthly |
| QuickCash NBFI | Working-capital line | 400,000 | 0 | 9 | Flat for whole term | 12 months, monthly |
| Supplier invoice finance | Invoice financing | 350,000 | 1,500 | 2 | Flat for whole term | 60 days, one payment |

Verified on the local build with exactly these inputs: need BDT 360,000 from day 6; Prime Bank fits (effective 16.59%, total cost BDT 33,432.79, best match); QuickCash fits but is 17.74% effective with the flat-rate warning (cost BDT 36,000); supplier finance is cheapest (15.79%, BDT 8,500) but does not cover the shortfall.

Also invite the approver account (Workspace & teammates → Create approver invitation → join from the second account).

| Time | Screen | Narration (English) |
| --- | --- | --- |
| 0:00–0:20 | Landing page → owner overview | "Small businesses run out of cash before they run out of customers. SafeLedger is an SME finance copilot where AI does real financial work, but never holds the authority to move money." |
| 0:20–0:50 | Overview cards, expand source evidence | "Every number is calculated by the server in exact integer units from records the owner entered, and each figure links to its source records. There are no bank credentials and no bank transfers." |
| 0:50–1:25 | Cash flow page, then 7-day receipt delay | "The deterministic forecast shows a reserve breach on day six: we are BDT 360,000 short before the export receipt arrives. A seven-day delay scenario shows how much worse it gets, without touching the ledger." |
| 1:25–2:30 | **Financing** page: add three quotes, then Match | "Topic E asks for financing-option matching. The owner enters the real offers they received. SafeLedger computes every installment exactly, converts each to an effective annual rate, and tests it against this cash flow. The supplier finance is the cheapest, but it is too small to cover the gap. And notice: the nine percent flat offer looks cheaper than the bank's thirteen and a half percent, but converted to an effective annual rate it is seventeen point seven percent against sixteen point six. The best match is the bank loan: it covers the gap and keeps the balance above the reserve through the last installment. SafeLedger does not apply for credit. It shows its assumptions, and the analysis is written to the signed audit trail." |
| 2:30–3:00 | Assistant: "Which loan fits my cash flow?" then an open question → permission card → Keep it local | "The assistant answers on the device first, with source evidence. When it needs the online model it asks permission and shares only this question and the verified figures. Off-topic and injection prompts never leave the browser." |
| 3:00–3:25 | Invoices: Review payment on DP-1182 → blocked (DUPLICATE_INVOICE_BLOCKED); Review payment on RL-552 | "This packaging invoice was sent twice with a slightly different reference, so policy blocks payment until a human reviews it. For the freight invoice the workflow creates a proposal bound to the payee, amount, source hash and a fifteen-minute expiry. Nothing is paid yet." |
| 3:25–4:10 | Switch to the approver account, then Approvals → review dialog → approve | "A different person must approve. The owner cannot approve their own proposal, and no AI tool can approve or execute. The server rechecks the balance, reserve, payee permission and the exact action hash, then posts once. Retries return the same posting." |
| 4:10–4:40 | Audit page: verified chain, FINANCING_ANALYZED, PROPOSED, APPROVED, EXECUTED; Export | "Every step is in a tenant hash chain signed with HMAC, so tampering is detectable. More than four hundred automated tests run in GitHub Actions on every push, plus a security review that found and fixed a real rate-limit bypass." |
| 4:40–5:00 | Overview | "SafeLedger: verified evidence in, an explainable decision out, and a human in charge of the money. Limits we disclose: no bank connection, free-tier hosting, and forecasts are scenarios, not predictions." |

Captions: add English subtitles. Export at 1080p, at most 5:00.
