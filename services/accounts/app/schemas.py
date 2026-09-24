from datetime import date, datetime

from pydantic import BaseModel, Field


class AccountOut(BaseModel):
    id: int
    user_id: str
    account_number: str
    account_type: str
    balance_cents: int
    currency: str
    date_of_birth: date
    ssn_full: str
    created_at: datetime


class AccountPatchRequest(BaseModel):
    # No allowlist distinguishing "safe to edit" fields from privileged ones
    # — see the mass-assignment comment on PATCH /accounts/{id} in main.py.
    balance_cents: int | None = None
    account_type: str | None = None
    account_number: str | None = None


class LinkExternalRequest(BaseModel):
    account_id: int
    verification_url: str = Field(max_length=2048)


class ApplyTransferRequest(BaseModel):
    # amount_cents is denominated in the FROM account's currency.
    from_account_id: int
    to_account_id: int
    amount_cents: int


class ApplyTransferResponse(BaseModel):
    from_account_id: int
    from_balance_cents: int
    to_account_id: int
    to_balance_cents: int
    from_currency: str
    to_currency: str
    converted_amount_cents: int
    fx_rate: float
