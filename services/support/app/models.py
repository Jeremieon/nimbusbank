import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    # INTENTIONALLY VULNERABLE: small sequential integer ids (not UUIDs) on
    # purpose — see the IDOR comments on GET /tickets/{id} in main.py.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # References auth-service's users.id logically only — no foreign key across
    # services. Each service owns its own database.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)

    # open / closed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    ticket_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # "customer" | "agent"
    sender: Mapped[str] = mapped_column(String(20), nullable=False)

    # INTENTIONALLY VULNERABLE: stored exactly as submitted, no HTML-escaping
    # expectation. The agent console (frontend/src/pages/AgentConsole.jsx)
    # renders this with dangerouslySetInnerHTML instead of plain text, so a
    # `<script>` / `<img onerror=...>` payload here actually executes in a
    # support agent's browser — stored XSS / formjacking (OWASP Top 10 / F5 XC
    # WAF category). Same pattern as transfers-service's `memo`.
    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
