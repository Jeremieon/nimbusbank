from datetime import datetime

from pydantic import BaseModel, Field


class TransferRequest(BaseModel):
    from_account_id: int
    to_account_id: int

    # INTENTIONALLY VULNERABLE: no ge=0 constraint and no maximum — negative
    # amounts and absurdly large ones both pass validation. See the comment
    # on POST /transfers in main.py.
    amount_cents: int
    memo: str | None = Field(default=None, max_length=2000)

    # Optional. amount_cents is denominated in the source account's currency;
    # transfers-service doesn't know that currency without asking accounts-
    # service, so this is filled in from apply-transfer's response after the
    # fact rather than trusted from the client.
    currency: str | None = Field(default=None, max_length=3)


class TransferOut(BaseModel):
    id: int
    from_account_id: int
    to_account_id: int
    amount_cents: int
    currency: str | None = None
    to_amount_cents: int | None = None
    to_currency: str | None = None
    fx_rate: float | None = None
    memo: str | None
    status: str
    created_at: datetime


class AdminOverrideRequest(BaseModel):
    transfer_id: int
    new_status: str = Field(max_length=20)
