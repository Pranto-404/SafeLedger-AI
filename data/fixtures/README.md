# Synthetic recipe2026 fixtures
All records are fictional, made by scripts/build_fixtures.py using Python Random(2026) only for vendor allocation. No private business/identity data or real lender offers. Regeneration is tested byte-for-byte. manifest.json has raw file SHA256 values; stored datasets and individual records get canonical-content SHA256.

- seed_2026.json:45 invoices,60 events, BDT; CSV equivalents supplied.
- expected_results.json: fixed oracle specified independently of finance functions. Opening BDT100,000 + cleared BDT30,000 - cleared BDT10,000 = BDT120,000. Invoice obligations BDT89,300. Forecast deducts additional scheduled rent BDT90,000 and adds BDT40,550 scheduled receipts. Final30 =120,000 -89,300 -90,000 +40,550 = -18,750BDT. Day7 excludes BDT4,300 small invoices and BDT550 receipts, yielding -15,000BDT.
- Day5 before BDT40,000 receipt:120,000 -35,000 -50,000 -90,000 = -55,000BDT. Seven-day receipt delay leaves day10 at -59,300BDT. Reserve BDT10,000 breached on2026-10-22.
- fictional_offers.json: equal BDT50,000 principal,30-day term. A:1% +BDT2,000 fee =BDT2,500 cost; B:4% +BDT100 fee =BDT2,100 cost; C:3% +BDT500 fee =BDT2,000 cost. All unaffordable given baseline reserve-adjusted repayment capacity0.
- duplicate_exact.json: an additional identical INV104 source; flagged and counted once economically.
- duplicate_possible.json: altered invoice number; flagged, both liabilities conservatively projected.
- untrusted_memo.json: malicious instructions as inert data; tests establish unchanged financial outputs, not live LLM injection resistance.
- invalid_amount.json: malformed last-intake example for rejection testing; never a valid imported fixture.
