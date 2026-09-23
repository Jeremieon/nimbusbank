import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class KycDocument(Base):
    __tablename__ = "kyc_documents"

    # INTENTIONALLY VULNERABLE: small sequential integer ids (not UUIDs) on
    # purpose — see the IDOR/BOLA comments on GET /kyc/{id} in main.py for why
    # that matters. Enumerating id=1..N walks every customer's KYC docs.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # References auth-service's users.id logically only — there is no foreign
    # key across services, and never will be. Each service owns its own
    # database.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # id_card / proof_of_address / selfie
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)

    # The client-supplied original filename, kept as-is for display. See the
    # path-traversal comment on POST /kyc/upload in main.py for how this same
    # untrusted value is (deliberately) used to build the on-disk path.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # pending / approved / rejected
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
