# Financing-option matching (release 0.4.0)

Commit `30ecef8`, 19 October 2026. Closes audit finding SL-001 (Topic E financing-option matching was retired).

## What the SME owner gets

The owner types in the offers they actually received (bank term loan, NBFI working-capital line, invoice financing, equipment loan). Capzoryx Copilot:

1. computes the exact repayment schedule for each offer in integer minor units;
2. converts every offer to an **estimated effective annual rate**, so a "9% flat" offer can be compared fairly with a "13.5% per year on reducing balance" offer;
3. overlays proceeds and repayments on the owner's own recorded cash-flow forecast;
4. reports whether the offer **covers the projected shortfall** and **keeps the balance above the reserve until the last repayment**;
5. ranks offers by cash-flow fit, then total cost, and names a best match, with warnings in plain language.

It never contacts a lender, checks eligibility, applies for credit or claims approval odds.

## Contract

`POST /api/financing/match` with `{as_of, quotes[1..10]}`. Each quote: `quote_id, lender_name, product_type, currency, principal_minor, upfront_fee_minor, rate_type (flat_per_term | annual_reducing), rate_bps (0..20000), repayment (single_payment | equal_installments), installments (1..60), term_days (1..1825), quote_source, quoted_on`.

Server-owned inputs: the runtime dataset, the forecast and the reserve from `security_policies`. The request cannot supply balance, reserve or capacity. Roles: owner or approver (viewer receives 403). Rate budget: 30 per minute per workspace. Each analysis appends a signed `FINANCING_ANALYZED` audit event with the analysis SHA-256. The ledger is never modified.

## Methods

Let P be the principal, F the upfront fee, r the quoted rate, n the number of installments and T the term in days. Proceeds are assumed on day 1 and payments at the end of each equal period p = T/n.

- **Flat per term:** interest I = round_half_up(P × r). Total repayment P + I is split evenly; the last installment absorbs the remainder.
- **Annual, reducing balance:** period rate i = r × p / 365. Installment A = round_half_up(P·i / (1 − (1+i)^−n)) using exact rational arithmetic. Each period's interest is round_half_up(balance × i), and the last payment clears the balance exactly to zero.
- **Single payment, annual rate:** I = round_half_up(P × r × T / 365).
- **Effective annual rate (estimate):** the y that solves Σ payment_k / (1+y)^(day_k/365) = P − F, found by bisection and rounded to 1 basis point. It is used only for comparison and display; it is never used as authoritative money.
- **Cash-flow fit:** baseline daily balance B(d) comes from the same deterministic scheduler as the Cash flow page, extended to the longest term. With financing, B'(d) = B(d) + (P − F) − cumulative payments(d). Funding need = max(0, reserve − min₃₀ B).
- **Status:** `VERIFY_TERMS_WITH_LENDER` if the effective rate is above 100% or the fee is above 20% of principal; otherwise `DOES_NOT_COVER_SHORTFALL` if net proceeds are below the need; otherwise `REPAYMENT_BREACHES_RESERVE` if any B'(d) is below the reserve during the term; otherwise `FITS_CASH_FLOW`.
- **Warnings:** quote older than 30 days; flat rate on installments understates cost; effective rate above 36%; proceeds more than 1.5× the need.
- **Ranking:** fits first, then total cost (interest + fees), then effective rate, then quote ID. The result is independent of input order (tested).

## Worked example (verified on the local build, BDT)

Workspace: cleared cash BDT 150,000; scheduled raw-material payment BDT 420,000 on day 6; customer receipt BDT 600,000 on day 25; open invoices RL-552 BDT 20,000 (day 3) and a possible duplicate pair DP-1182 / DP-1182-A of BDT 35,000 each (day 10, both counted conservatively). Baseline lowest balance is −BDT 360,000 from day 6, so the need is BDT 360,000 (reserve 0).

| Offer | Quoted | Effective annual (est.) | Total cost | Result |
| --- | --- | --- | --- | --- |
| Prime Bank term loan, BDT 400,000, fee 4,000, 12 monthly | 13.50% p.a. reducing | 16.59% | BDT 33,432.79 | **Best match**: fits cash flow, lowest balance BDT 36,000 |
| QuickCash NBFI line, BDT 400,000, no fee, 12 monthly | 9.00% flat | 17.74% | BDT 36,000.00 | Fits, with warning: flat rate understates effective cost |
| Supplier invoice finance, BDT 350,000, fee 1,500, 60 days single payment | 2.00% flat | 15.79% | BDT 8,500.00 | Does not cover the BDT 360,000 shortfall |

The insight a chatbot would miss: the offer with the lowest headline rate (9% flat) costs more than the bank's 13.5% once both are converted to an effective annual rate, and the cheapest offer overall is too small to solve the problem.

## Verification

- `api/tests/test_financing.py`: 18 tests. Reference arithmetic is computed independently, amortization is checked to clear exactly to zero, ranking is checked to be order-independent, and the suite covers currency/date/stale-snapshot rejection, viewer 403, anonymous 401, no ledger mutation and the signed audit event.
- Full suite on GitHub Actions (Linux): passed at `30ecef8`.
- Production: `/api/health` reports `0.4.0` and build `30ecef8`; the unauthenticated financing route returns 401.
