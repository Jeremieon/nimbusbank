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


class TransferOut(BaseModel):
    id: int
    from_account_id: int
    to_account_id: int
    amount_cents: int
    memo: str | None
    status: str
    created_at: datetime


class AdminOverrideRequest(BaseModel):
    transfer_id: int
    new_status: str = Field(max_length=20)
