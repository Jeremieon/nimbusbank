import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Test-data only — never enter a real SSN into this lab app.
    ssn_last4: Mapped[str] = mapped_column(String(4), nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False, default="customer")

    # Real TOTP (Google Authenticator / RFC 6238) second factor, offered
    # alongside — never replacing — the weak echoed 4-digit OTP. A user opts
    # in via the Security page: /totp/enroll stores a secret with
    # totp_enabled still False, and /totp/confirm flips it True once they
    # prove they can generate a valid code. Seeded users stay on the weak-OTP
    # path (totp_enabled False) so existing demos/curl keep working.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # INTENTIONALLY VULNERABLE: always True the instant /register completes —
    # see the comment in main.py's register() for the F5 XC mapping.
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class OtpCode(Base):
    """Server-side OTP storage for the login second factor. A real table
    instead of an in-memory dict so it survives a worker restart during a
    demo — LAB-ONLY convenience, not a security property."""

    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(4), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PasswordResetToken(Base):
    """Server-side storage for a "forgot password" reset token.

    INTENTIONALLY VULNERABLE: the token stored here is a SHORT, guessable
    6-digit numeric string (see main.py's /password/forgot) — the same weak
    keyspace as the login OTP, deliberately bruteforceable. It's stored in
    plaintext and not bound to any session or device, so anyone who can guess
    (or is handed, via the LAB-ONLY echo) a live token for a known email can
    reset that account's password."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(12), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
