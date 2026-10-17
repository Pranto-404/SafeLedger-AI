"""Deterministic BDT finance. These services have no LLM/network/write authority."""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher
import hashlib
import json
import re
from typing import Annotated, Literal
from pydantic import Field, model_validator
from api.app.contracts import Contract, ImportRequest, ISODate, Minor, PositiveMinor, RecordId, ScenarioRequest


def bdt_minor(value: str) -> int:
    """Reject excess precision; never silently round imported money."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,11}(?:\.[0-9]{1,2})?", value):
        raise ValueError("Expected nonnegative BDT with at most two decimal places")
    amount = int(Decimal(value) * 100)
    if amount > 10**12:
        raise ValueError("Amount exceeds prototype limit")
    return amount


def fingerprint(value: Contract) -> str:
    content = json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


def invoice_key(invoice):
    # Punctuation-only aliases count as exact canonical duplicates. Original retained.
    number = re.sub(r"[^A-Z0-9]", "", invoice.invoice_number.upper())
    return invoice.vendor_id, number


class Dataset(ImportRequest):
    opening_source_id: RecordId
    opening_on: ISODate
    as_of: ISODate
    opening_balance_minor: Minor
    currency: Literal["BDT"]

    @model_validator(mode="after")
    def consistent(self):
        if self.opening_on > self.as_of:
            raise ValueError("opening_on must not follow as_of")
        sources = [self.opening_source_id] + [x.source_record_id for x in self.invoices + self.events]
        if len(sources) != len(set(sources)):
            raise ValueError("source_record_id must be unique across the complete dataset")
        for records, field in ((self.invoices, "invoice_id"), (self.events, "event_id")):
            ids = [getattr(x, field) for x in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {field}; assign unique source identities")
        by_id = {x.invoice_id: x for x in self.invoices}
        canonical = {}
        for invoice in self.invoices:
            if invoice.issued_on > self.as_of:
                raise ValueError("Future-issued invoices are unsupported in this snapshot")
            key = invoice_key(invoice)
            if not key[1]:
                raise ValueError("Invoice number needs at least one ASCII letter or digit")
            if key in canonical:
                other = canonical[key]
                if (invoice.amount_minor, invoice.due_on, invoice.issued_on, invoice.status) != (other.amount_minor, other.due_on, other.issued_on, other.status):
                    raise ValueError("Conflicting duplicate invoice economics require manual correction")
            canonical[key] = invoice
        linked = {}
        for event in self.events:
            if event.status == "cleared" and not (self.opening_on <= event.effective_on <= self.as_of):
                raise ValueError("Cleared events must fall between opening_on and as_of inclusive")
            if event.invoice_id:
                inv = by_id.get(event.invoice_id)
                if inv is None:
                    raise ValueError("Linked invoice_id does not exist")
                if event.direction != "outflow" or event.amount_minor != inv.amount_minor:
                    raise ValueError("Linked payable event must be full-amount outflow; partial settlement unsupported")
                key = invoice_key(inv)
                if key in linked:
                    raise ValueError("Multiple events settle the same canonical invoice; would double count")
                if (inv.status == "paid") != (event.status == "cleared"):
                    raise ValueError("Paid invoices need cleared settlement; open invoices need scheduled settlement")
                linked[key] = event
        for inv in self.invoices:
            if inv.status == "paid" and invoice_key(inv) not in linked:
                raise ValueError("Paid invoice has no cleared settlement evidence")
        return self


def validated(raw) -> Dataset:
    # Revalidate dumped model too: prevents post-validation mutation bypasses.
    if isinstance(raw, Dataset):
        raw = raw.model_dump(mode="json")
    return Dataset.model_validate(raw)


def analyze_duplicates(dataset: Dataset) -> list[dict]:
    ds = validated(dataset)
    groups = defaultdict(list)
    for inv in ds.invoices:
        groups[invoice_key(inv)].append(inv)
    flags = []
    for group in groups.values():
        if len(group) > 1:
            flags.append({"risk": "DUPLICATE_EXACT", "invoice_ids": sorted(x.invoice_id for x in group), "source_ids": sorted(x.source_record_id for x in group), "execution_blocked": True})
    # Bounded at 1000 invoices; same-vendor/date/amount with different number is review-only.
    near = defaultdict(list)
    for key, group in groups.items():
        inv = group[0]
        near[(inv.vendor_id, inv.issued_on, inv.amount_minor)].append((key, group))
    for candidates in near.values():
        parents = list(range(len(candidates)))
        def root(i):
            while parents[i] != i:
                parents[i] = parents[parents[i]]
                i = parents[i]
            return i
        for i, (key, _) in enumerate(candidates):
            for j in range(i + 1, len(candidates)):
                other = candidates[j][0]
                if SequenceMatcher(None, key[1], other[1], autojunk=False).ratio() >= 0.85:
                    parents[root(j)] = root(i)
        clusters = defaultdict(list)
        for i, (_, same) in enumerate(candidates):
            clusters[root(i)].extend(same)
        for records in clusters.values():
            if len({invoice_key(x) for x in records}) > 1:
                flags.append({"risk": "DUPLICATE_POSSIBLE", "invoice_ids": sorted(x.invoice_id for x in records), "source_ids": sorted(x.source_record_id for x in records), "execution_blocked": True})
    return sorted(flags, key=lambda x: (x["risk"], x["invoice_ids"]))


def snapshot(dataset: Dataset) -> dict:
    ds = validated(dataset)
    credits = [x for x in ds.events if x.status == "cleared" and x.direction == "inflow"]
    debits = [x for x in ds.events if x.status == "cleared" and x.direction == "outflow"]
    income = sum(x.amount_minor for x in credits)
    expenses = sum(x.amount_minor for x in debits)
    return {"currency": "BDT", "as_of": ds.as_of.isoformat(), "opening_balance_minor": ds.opening_balance_minor,
            "income_minor": income, "expenses_minor": expenses, "balance_minor": ds.opening_balance_minor + income - expenses,
            "source_ids": [ds.opening_source_id] + sorted(x.source_record_id for x in credits + debits),
            "dataset_sha256": fingerprint(ds), "assumptions": ["Cash basis; cleared income/expenses are cash movements, not accrual profit", "Opening balance is start-of-day opening_on; cleared events are included through end-of-day as_of"]}


def project_cashflow(dataset: Dataset, request: ScenarioRequest) -> dict:
    ds = validated(dataset)
    request = ScenarioRequest.model_validate(request.model_dump(mode="json"))
    if request.as_of != ds.as_of:
        raise ValueError("Scenario as_of must equal the immutable snapshot as_of")
    cash = snapshot(ds)["balance_minor"]
    first = request.as_of + timedelta(days=1)
    days = defaultdict(list)
    scheduled_keys = set()
    for event in ds.events:
        if event.status != "scheduled":
            continue
        if event.invoice_id:
            invoice = next(x for x in ds.invoices if x.invoice_id == event.invoice_id)
            scheduled_keys.add(invoice_key(invoice))
        day = max(first, event.effective_on)
        if event.direction == "inflow":
            day += timedelta(days=request.delay_inflows_days)
        days[day].append((event.direction, event.amount_minor, event.source_record_id))
    canonical = {}
    for invoice in sorted(ds.invoices, key=lambda x: x.invoice_id):
        canonical.setdefault(invoice_key(invoice), invoice)
    for key, invoice in canonical.items():
        if invoice.status == "open" and key not in scheduled_keys:
            days[max(first, invoice.due_on)].append(("outflow", invoice.amount_minor, invoice.source_record_id))
    result = []
    for offset in range(1, request.horizon_days + 1):
        day = request.as_of + timedelta(days=offset)
        movements = days[day]
        incoming = sum(amount for direction, amount, _ in movements if direction == "inflow")
        outgoing = sum(amount for direction, amount, _ in movements if direction == "outflow")
        cash += incoming - outgoing
        result.append({"date": day.isoformat(), "inflow_minor": incoming, "outflow_minor": outgoing,
                       "projected_balance_minor": cash, "shortfall_minor": max(0, request.reserve_minor - cash),
                       "source_ids": sorted(source for _, _, source in movements)})
    alerts = [x["date"] for x in result if x["shortfall_minor"]]
    duplicate_flags = analyze_duplicates(ds)
    return {"currency": "BDT", "as_of": ds.as_of.isoformat(), "horizon_days": request.horizon_days,
            "reserve_minor": request.reserve_minor, "opening_balance_minor": snapshot(ds)["balance_minor"],
            "closing_balance_minor": cash, "minimum_balance_minor": min([snapshot(ds)["balance_minor"]] + [x["projected_balance_minor"] for x in result]),
            "first_shortfall_on": alerts[0] if alerts else None, "days": result, "risk_flags": duplicate_flags,
            "source_ids": sorted({ds.opening_source_id} | {s for x in result for s in x["source_ids"]} | set(snapshot(ds)["source_ids"])),
            "assumptions": ["Deterministic scenario, not a probabilistic prediction", "Daily closing balances; within-day liquidity is not modeled",
                            "Overdue open obligations and scheduled cash start on day one; only scheduled inflows shift in delayed scenario",
                            "Linked invoice/event counted once; identical canonical invoice duplicates counted once; possible duplicates both counted conservatively",
                            "Scheduled outflows assumed to occur on planned dates; no new sales, tax, interest or financing inferred"]}


class FictionalOffer(Contract):
    offer_id: RecordId
    label: Annotated[str, Field(min_length=1, max_length=100)]
    fictional: Literal[True]
    currency: Literal["BDT"]
    principal_minor: PositiveMinor
    rate_convention: Literal["flat_per_term"]
    rate_bps: Annotated[int, Field(strict=True, ge=0, le=10000)]
    upfront_fee_minor: Minor
    term_days: Annotated[int, Field(strict=True, ge=1, le=365)]
    repayment_structure: Literal["single_maturity_payment"]
    source_record_id: RecordId

    @model_validator(mode="after")
    def fee_less_than_principal(self):
        if self.upfront_fee_minor >= self.principal_minor:
            raise ValueError("Upfront fee must be less than principal")
        return self


class FinancingRequest(Contract):
    principal_minor: PositiveMinor
    repayment_capacity_minor: Minor
    capacity_source_ids: Annotated[list[RecordId], Field(min_length=1, max_length=4000)]
    offers: Annotated[list[FictionalOffer], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def comparable(self):
        if len({x.offer_id for x in self.offers}) != len(self.offers):
            raise ValueError("Duplicate offer IDs")
        if len({x.source_record_id for x in self.offers}) != len(self.offers):
            raise ValueError("Duplicate financing source IDs")
        if any(x.principal_minor != self.principal_minor for x in self.offers):
            raise ValueError("Offers must quote the requested principal")
        if len({x.term_days for x in self.offers}) != 1:
            raise ValueError("Compare equal terms only; otherwise separate scenarios required")
        return self


def compare_financing(request: FinancingRequest) -> dict:
    req = FinancingRequest.model_validate(request.model_dump(mode="json"))
    rows = []
    for offer in req.offers:
        # Integer half-up to a minor unit for a nonnegative interest numerator.
        interest = (offer.principal_minor * offer.rate_bps + 5000) // 10000
        repayment = offer.principal_minor + interest
        rows.append({"offer_id": offer.offer_id, "label": offer.label, "fictional": True, "currency": "BDT",
                     "principal_minor": offer.principal_minor, "net_proceeds_minor": offer.principal_minor - offer.upfront_fee_minor,
                     "interest_minor": interest, "upfront_fee_minor": offer.upfront_fee_minor, "total_repayment_minor": repayment,
                     "total_cost_minor": interest + offer.upfront_fee_minor, "term_days": offer.term_days,
                     "rate_bps": offer.rate_bps, "rate_convention": offer.rate_convention,
                     "repayment_structure": offer.repayment_structure,
                     "affordable": repayment <= req.repayment_capacity_minor,
                     "repayment_gap_minor": max(0, repayment - req.repayment_capacity_minor),
                     "source_ids": [offer.source_record_id] + req.capacity_source_ids})
    rows.sort(key=lambda x: (x["total_cost_minor"], x["offer_id"]))
    return {"offers": rows, "ranked_by": "total_cost_minor", "repayment_capacity_minor": req.repayment_capacity_minor,
            "assumptions": ["Fictional offers only; no lender integration or approval odds", "Flat rate for the whole term, NOT annual APR",
                            "Fee paid upfront; net proceeds = principal minus fee; total cost = repayment plus fee minus principal",
                            "Single maturity payment; interest rounded half-up to minor unit", "Affordability compares only supplied reserve-adjusted repayment capacity; not credit approval or full liquidity underwriting"]}
