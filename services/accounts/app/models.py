import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Account(Base):
    __tablename__ = "accounts"

    # INTENTIONALLY VULNERABLE: small sequential integer ids (not UUIDs) on
    # purpose — see the BOLA comment on GET /accounts/{id} in main.py for why
    # that matters. Enumerating id=1..N is trivial.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # References auth-service's users.id logically only — there is no
    # foreign key across services, and never will be. Each service owns its
    # own database.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    account_number: Mapped[str] = mapped_column(String(34), unique=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    balance_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)

    # Fake full SSN for demo purposes only — never enter a real one here.
    ssn_full: Mapped[str] = mapped_column(String(11), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
