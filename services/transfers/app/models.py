from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # References accounts-service's accounts.id logically only — no foreign
    # key across services, and no call to accounts-service to check either
    # id is real. Each service owns its own database.
    from_account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    to_account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    # INTENTIONALLY VULNERABLE: stored exactly as submitted, no HTML-escaping
    # expectation. The frontend renders this with dangerouslySetInnerHTML in
    # the transaction history view instead of plain text interpolation, so a
    # `<script>`/`<img onerror=...>` payload here actually executes in the
    # browser — stored XSS (OWASP Top 10 / F5 XC WAF category).
    memo: Mapped[str] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
