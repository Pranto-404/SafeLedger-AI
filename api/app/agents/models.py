from typing import Annotated, Literal
from pydantic import Field, StrictBool, model_validator
from api.app.contracts import Contract, RecordId

class TaskRequest(Contract):
    task: Annotated[str,Field(min_length=1,max_length=2000)]
    invoice_id: RecordId | None = None
    allow_proposal: StrictBool = False
    external_ai_consent: StrictBool = False

    @model_validator(mode='after')
    def explicit_target(self):
        if self.allow_proposal and self.invoice_id is None:raise ValueError('Explicit invoice_id required for proposal permission')
        return self

class NoArgs(Contract):pass
class InvoiceArgs(Contract):invoice_id: RecordId
class CashArgs(Contract):
    horizon_days: Literal[7,30]
    delay_inflows_days: Annotated[int,Field(strict=True,ge=0,le=30)]

TOOLS={'get_business_snapshot':NoArgs,'analyze_invoice':InvoiceArgs,'project_cash_flow':CashArgs,'propose_payment':InvoiceArgs}

class Rationale(Contract):
    disposition: Literal['READ_ONLY','REVIEW_REQUIRED','PROPOSE_FOR_APPROVAL']
    reason_codes: Annotated[list[Literal['VERIFIED_BALANCE','INVOICE_REVIEW','DUPLICATE_BLOCKED','LIQUIDITY_RISK','FINANCING_COST','HUMAN_APPROVAL_REQUIRED','POLICY_BLOCKED']],Field(min_length=1,max_length=6)]
    fact_ids: Annotated[list[RecordId],Field(min_length=1,max_length=20)]


    @model_validator(mode='after')
    def unique_references(self):
        if len(self.fact_ids)!=len(set(self.fact_ids)) or len(self.reason_codes)!=len(set(self.reason_codes)):
            raise ValueError('Duplicate facts/reasons are not a valid rationale')
        return self
