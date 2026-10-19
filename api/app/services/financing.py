"""Deterministic financing-option matching over user-entered lender quotes.

No lender integration, eligibility check, credit decision or application. Quotes are
self-reported evidence; every amount below is an exact integer in ledger minor units.
"""
from datetime import timedelta
from fractions import Fraction
import hashlib
import json
from typing import Annotated, Literal
from pydantic import Field, model_validator
from api.app.contracts import Contract, Currency, ISODate, Minor, PositiveMinor, RecordId
from api.app.services.finance import Dataset, scheduled_movements, snapshot, validated

MAX_TERM_DAYS = 1825
STALE_QUOTE_DAYS = 30
HIGH_COST_BPS = 3600
SUSPECT_COST_BPS = 10000
SUSPECT_FEE_SHARE = Fraction(1, 5)


class LenderQuote(Contract):
    quote_id: RecordId
    lender_name: Annotated[str, Field(min_length=1, max_length=100)]
    product_type: Literal["term_loan", "working_capital_line", "invoice_financing", "equipment_loan", "other"]
    currency: Currency
    principal_minor: PositiveMinor
    upfront_fee_minor: Minor
    rate_type: Literal["flat_per_term", "annual_reducing"]
    rate_bps: Annotated[int, Field(strict=True, ge=0, le=20000)]
    repayment: Literal["single_payment", "equal_installments"]
    installments: Annotated[int, Field(strict=True, ge=1, le=60)]
    term_days: Annotated[int, Field(strict=True, ge=1, le=MAX_TERM_DAYS)]
    quote_source: Annotated[str, Field(min_length=3, max_length=200)]
    quoted_on: ISODate

    @model_validator(mode="after")
    def consistent(self):
        if self.upfront_fee_minor >= self.principal_minor:
            raise ValueError("Upfront fee must be less than principal")
        if self.repayment == "single_payment" and self.installments != 1:
            raise ValueError("A single payment quote has exactly one installment")
        if self.repayment == "equal_installments" and self.term_days % self.installments:
            raise ValueError("Term days must divide evenly into installment periods")
        return self


class FinancingMatchRequest(Contract):
    as_of: ISODate
    quotes: Annotated[list[LenderQuote], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def unique(self):
        if len({x.quote_id for x in self.quotes}) != len(self.quotes):
            raise ValueError("Duplicate quote IDs")
        return self


def half_up(value: Fraction) -> int:
    """Round a nonnegative exact rational to the nearest minor unit, halves up."""
    if value < 0:
        raise ValueError("Negative amount")
    return int((value * 2 + 1) // 2)


def repayment_schedule(quote: LenderQuote) -> list[tuple[int, int, int]]:
    """[(day_offset, payment_minor, interest_minor)] that repays principal exactly."""
    p, n = quote.principal_minor, quote.installments
    period = quote.term_days // n
    rate = Fraction(quote.rate_bps, 10000)
    if quote.rate_type == "flat_per_term" or n == 1:
        if quote.rate_type == "flat_per_term":
            interest = half_up(p * rate)
        else:
            interest = half_up(p * rate * Fraction(quote.term_days, 365))
        total = p + interest
        base, remainder = divmod(total, n)
        share, extra = divmod(interest, n)
        return [(period * (k + 1), base + (remainder if k == n - 1 else 0), share + (extra if k == n - 1 else 0)) for k in range(n)]
    r = rate * Fraction(period, 365)
    if r == 0:
        base, remainder = divmod(p, n)
        return [(period * (k + 1), base + (remainder if k == n - 1 else 0), 0) for k in range(n)]
    payment = half_up(p * r / (1 - (1 + r) ** -n))
    balance, rows = p, []
    for k in range(n):
        interest = half_up(balance * r)
        amount = balance + interest if k == n - 1 else payment
        balance -= amount - interest
        rows.append((period * (k + 1), amount, interest))
    if balance != 0 or any(amount <= interest for _, amount, interest in rows[:-1]):
        raise ValueError("Quote terms do not amortize")
    return rows


def effective_annual_rate_bps(net_proceeds: int, schedule: list[tuple[int, int, int]]) -> int:
    """Estimated IRR of the borrower's cash flows, annual compounding, rounded to 1 bps."""
    paid = sum(amount for _, amount, _ in schedule)
    if paid <= net_proceeds:
        return 0
    def present_value(y: float) -> float:
        return sum(amount / (1 + y) ** (day / 365) for day, amount, _ in schedule)
    low, high = 0.0, 1.0
    while present_value(high) > net_proceeds and high < 1e6:
        high *= 2
    for _ in range(200):
        mid = (low + high) / 2
        if present_value(mid) > net_proceeds:
            low = mid
        else:
            high = mid
    return round(high * 10000)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def match_financing(dataset: Dataset, reserve_minor: int, request: FinancingMatchRequest) -> dict:
    ds = validated(dataset)
    req = FinancingMatchRequest.model_validate(request.model_dump(mode="json"))
    if req.as_of != ds.as_of:
        raise ValueError("Financing as_of must equal the immutable snapshot as_of")
    for quote in req.quotes:
        if quote.currency != ds.currency:
            raise ValueError("Quotes must use the workspace ledger currency")
        if quote.quoted_on > ds.as_of:
            raise ValueError("Quote date cannot be after the snapshot date")
    current = snapshot(ds)["balance_minor"]
    movements = scheduled_movements(ds)
    horizon = max([30] + [q.term_days for q in req.quotes])
    baseline, cash = [], current
    for offset in range(1, horizon + 1):
        cash += sum(a if d == "inflow" else -a for d, a, _ in movements[ds.as_of + timedelta(days=offset)])
        baseline.append(cash)
    month_minimum = min([current] + baseline[:30])
    need = max(0, reserve_minor - month_minimum)
    shortfall_day = next((k + 1 for k, b in enumerate(baseline[:30]) if b < reserve_minor), None)
    source_ids = sorted({ds.opening_source_id} | set(snapshot(ds)["source_ids"]) | {s for day, rows in movements.items() if day <= ds.as_of + timedelta(days=horizon) for _, _, s in rows})
    rows = []
    for quote in req.quotes:
        schedule = repayment_schedule(quote)
        net = quote.principal_minor - quote.upfront_fee_minor
        interest = sum(i for _, _, i in schedule)
        repaid = sum(a for _, a, _ in schedule)
        rate = effective_annual_rate_bps(net, schedule)
        paid_by_day, balances = {}, []
        for day, amount, _ in schedule:
            paid_by_day[day] = paid_by_day.get(day, 0) + amount
        cumulative = 0
        for offset in range(1, horizon + 1):
            cumulative += paid_by_day.get(offset, 0)
            balances.append(baseline[offset - 1] + net - cumulative)
        with_loan_min = min([current] + balances[:quote.term_days])
        month_with_loan = min([current] + balances[:30])
        breach = next((k + 1 for k, b in enumerate(balances[:quote.term_days]) if b < reserve_minor), None)
        warnings = []
        if (ds.as_of - quote.quoted_on).days > STALE_QUOTE_DAYS:
            warnings.append("QUOTE_OLDER_THAN_30_DAYS")
        if quote.rate_type == "flat_per_term" and quote.installments > 1:
            warnings.append("FLAT_RATE_UNDERSTATES_EFFECTIVE_COST")
        if rate > HIGH_COST_BPS:
            warnings.append("HIGH_COST_FINANCING")
        if need and net > need * 3 // 2:
            warnings.append("BORROWS_MORE_THAN_NEEDED")
        suspect = rate > SUSPECT_COST_BPS or Fraction(quote.upfront_fee_minor, quote.principal_minor) > SUSPECT_FEE_SHARE
        if suspect:
            status = "VERIFY_TERMS_WITH_LENDER"
        elif net < need:
            status = "DOES_NOT_COVER_SHORTFALL"
        elif breach is not None:
            status = "REPAYMENT_BREACHES_RESERVE"
        else:
            status = "FITS_CASH_FLOW"
        rows.append({"quote_id": quote.quote_id, "lender_name": quote.lender_name, "product_type": quote.product_type,
                     "quote_source": quote.quote_source, "quoted_on": quote.quoted_on.isoformat(), "user_supplied": True,
                     "principal_minor": quote.principal_minor, "upfront_fee_minor": quote.upfront_fee_minor,
                     "net_proceeds_minor": net, "interest_minor": interest, "total_repayment_minor": repaid,
                     "total_cost_minor": interest + quote.upfront_fee_minor, "rate_type": quote.rate_type,
                     "rate_bps": quote.rate_bps, "term_days": quote.term_days, "installments": quote.installments,
                     "effective_annual_rate_bps": rate, "lowest_balance_with_financing_minor": with_loan_min,
                     "lowest_30_day_balance_with_financing_minor": month_with_loan,
                     "first_reserve_breach_on": (ds.as_of + timedelta(days=breach)).isoformat() if breach else None,
                     "additional_receipts_needed_minor": max(0, reserve_minor - with_loan_min),
                     "status": status, "warnings": warnings,
                     "schedule": [{"date": (ds.as_of + timedelta(days=d)).isoformat(), "payment_minor": a, "interest_minor": i} for d, a, i in schedule]})
    rows.sort(key=lambda x: (x["status"] != "FITS_CASH_FLOW", x["total_cost_minor"], x["effective_annual_rate_bps"], x["quote_id"]))
    eligible = [x for x in rows if x["status"] == "FITS_CASH_FLOW"]
    result = {"currency": ds.currency, "as_of": ds.as_of.isoformat(), "reserve_minor": reserve_minor,
              "current_balance_minor": current, "baseline_30_day_minimum_minor": month_minimum,
              "baseline_first_shortfall_on": (ds.as_of + timedelta(days=shortfall_day)).isoformat() if shortfall_day else None,
              "funding_need_minor": need, "best_match_quote_id": eligible[0]["quote_id"] if eligible else None,
              "lowest_rate_quote_id": min(rows, key=lambda x: (x["effective_annual_rate_bps"], x["quote_id"]))["quote_id"],
              "ranked_by": ["fits_cash_flow", "total_cost_minor", "effective_annual_rate_bps", "quote_id"],
              "quotes": rows, "source_ids": source_ids,
              "assumptions": ["Quotes are entered by the user and are not verified with any lender; no eligibility, approval or application is implied",
                              "Proceeds are assumed to arrive on day one; repayments fall at the end of each equal period",
                              "Flat rate: interest = principal x rate for the whole term. Annual reducing: equal installments on the outstanding balance",
                              "Effective annual rate is an estimated internal rate of return on net proceeds, for comparison only",
                              "Repayment capacity uses only recorded balances, scheduled receipts and open obligations; no new sales are inferred",
                              "Not financial advice. Confirm all terms, eligibility and total cost directly with the lender"]}
    result["analysis_sha256"] = _digest({"dataset": snapshot(ds)["dataset_sha256"], "reserve": reserve_minor, "request": req.model_dump(mode="json")})
    return result
