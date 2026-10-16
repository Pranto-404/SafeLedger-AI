"""V1 contracts. Strict integers are minor units; no client authority fields."""
from datetime import date
from enum import Enum
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Minor = Annotated[int, Field(strict=True, ge=0, le=10**12)]
PositiveMinor = Annotated[int, Field(strict=True, gt=0, le=10**12)]
RecordId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")]

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class InvoiceInput(Contract):
    source_record_id: RecordId
    invoice_id: RecordId
    vendor_id: RecordId
    invoice_number: Annotated[str, Field(min_length=1, max_length=80)]
    issued_on: date
    due_on: date
    amount_minor: PositiveMinor
    currency: Literal["BDT"]
    memo: Annotated[str, Field(max_length=2000)] = ""

    @model_validator(mode="after")
    def valid_dates(self):
        if self.due_on < self.issued_on:
            raise ValueError("due_on must be on or after issued_on")
        return self

class CashEventInput(Contract):
    source_record_id: RecordId
    event_id: RecordId
    direction: Literal["inflow", "outflow"]
    status: Literal["cleared", "scheduled"]
    effective_on: date
    amount_minor: PositiveMinor
    currency: Literal["BDT"]

class ImportRequest(Contract):
    invoices: Annotated[list[InvoiceInput], Field(max_length=1000)]
    events: Annotated[list[CashEventInput], Field(max_length=2000)]

class ScenarioRequest(Contract):
    as_of: date
    horizon_days: Literal[7, 30]
    reserve_minor: Minor
    delay_inflows_days: Annotated[int, Field(strict=True, ge=0, le=30)] = 0

class ProposalRequest(Contract):
    invoice_id: RecordId

class ApprovalRequest(Contract):
    proposal_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    decision: Literal["approve", "reject"]

class ProposalState(str, Enum):
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DENIED = "DENIED"

class AgentToolCall(Contract):
    # Deliberately no approval, execution, arbitrary code or SQL tool.
    tool: Literal["get_business_snapshot", "analyze_invoice", "project_cash_flow", "compare_financing", "propose_payment"]
    # Tool-specific argument dispatch and provenance validation are M3 work.
    # This outer envelope is not sufficient to authorize a tool invocation.
    arguments: dict
