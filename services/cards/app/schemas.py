from datetime import datetime

from pydantic import BaseModel, Field


class IssueCardRequest(BaseModel):
    account_id: int
    card_type: str = Field(default="virtual")
    spend_limit_cents: int | None = None


class CardPatchRequest(BaseModel):
    # No allowlist distinguishing "safe to edit" fields from privileged ones —
    # spend_limit_cents, status, account_id and even user_id can all be
    # mass-assigned. See the mass-assignment comment on PATCH /cards/{id}.
    spend_limit_cents: int | None = None
    status: str | None = None
    account_id: int | None = None
    user_id: str | None = None


class CardOut(BaseModel):
    # Full detail, including the PAN + CVV. Returned by GET /cards/{id} — the
    # excessive-data-exposure sink for this service.
    id: int
    user_id: str
    account_id: int
    card_number: str
    last4: str
    expiry: str
    cvv: str
    card_type: str
    status: str
    spend_limit_cents: int
    created_at: datetime


class CardMaskedOut(BaseModel):
    # Bank-like masked view used by GET /cards (the caller's own cards): only
    # last4, no PAN and no CVV.
    id: int
    user_id: str
    account_id: int
    last4: str
    expiry: str
    card_type: str
    status: str
    spend_limit_cents: int
    created_at: datetime
