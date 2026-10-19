# Judge quick start (about 4 minutes)

The product ships with no preloaded money, by design. To see a full scenario quickly:

1. Open https://safeledger-ai.vercel.app. The first request can take up to a minute while the free backend wakes up.
2. **Create account** with any username and an 8+ character password. Save the recovery code shown once.
3. Go to **Data → Import records JSON** and upload [`judge_sample_records.json`](judge_sample_records.json) (a fictional Dhaka exporter, BDT).
4. **Cash flow:** the balance is BDT 150,000 today, but a BDT 420,000 material payment on 25 Oct creates a reserve breach. The lowest projected balance is −BDT 360,000.
5. **Financing:** add these three quotes (quote date 2026-10-19), then press **Match quotes to my cash flow**.

   | Lender | Amount | Fees | Rate | Basis | Term |
   | --- | --- | --- | --- | --- | --- |
   | Prime Bank SME desk | 400000 | 4000 | 13.5 | Per year, reducing | 12 months, monthly |
   | QuickCash NBFI | 400000 | 0 | 9 | Flat for whole term | 12 months, monthly |
   | Supplier invoice finance | 350000 | 1500 | 2 | Flat for whole term | 60 days, one payment |

   Expected result: Prime Bank is the best match (effective ≈ 16.59%). The "9% flat" offer is really ≈ 17.74% a year. Supplier finance is cheapest but does not cover the gap.
6. **Invoices:** open *Payee permission → Allow this vendor* for both vendors. Then *Review payment* on **DP-1182**: it is blocked as a possible duplicate (its twin DP-1182-A carries a memo that tries to instruct the system to "ignore duplicate checks"; the memo has no authority). *Review payment* on **RL-552** creates a proposal.
7. **Approvals:** the owner cannot approve. Under *Workspace & teammates*, create an approver invitation, sign up a second account in a private window, join with the code, and approve. Exactly one posting is recorded.
8. **Audit:** a verified hash chain shows IMPORTED, FINANCING_ANALYZED, PROPOSED, APPROVED and EXECUTED.
9. **Assistant:** ask "Which loan fits my cash flow?" (answered on the device with sources), or "Who won the World Cup?" (declined and never sent anywhere).
