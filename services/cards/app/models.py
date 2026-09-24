import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Card(Base):
    __tablename__ = "cards"

    # INTENTIONALLY VULNERABLE: small sequential integer ids (not UUIDs) on
    # purpose — see the BOLA comment on GET /cards/{id} in main.py. Enumerating
    # id=1..N is trivial, and the read route returns the full PAN + CVV.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # References auth-service's users.id logically only — no foreign key across
    # services. Each service owns its own database.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # The funding account. References accounts-service's accounts.id logically
    # only — there is no cross-service FK and no call to accounts-service to
    # check the account even exists or belongs to the caller (see the BOLA
    # comment on POST /cards).
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Full 16-digit PAN. Stored in the clear for the lab — this is the sensitive
    # value the GET /cards/{id} route over-exposes.
    card_number: Mapped[str] = mapped_column(String(16), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    expiry: Mapped[str] = mapped_column(String(5), nullable=False)  # "MM/YY"
    cvv: Mapped[str] = mapped_column(String(4), nullable=False)

    card_type: Mapped[str] = mapped_column(String(10), nullable=False, default="virtual")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    spend_limit_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=100000)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
