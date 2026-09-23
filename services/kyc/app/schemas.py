from datetime import datetime

from pydantic import BaseModel, Field


class KycDocumentOut(BaseModel):
    id: int
    user_id: str
    doc_type: str
    original_filename: str
    content_type: str
    stored_path: str
    size_bytes: int
    status: str
    created_at: datetime


class ReviewRequest(BaseModel):
    # No allowlist / role gate here — the BFLA gap is that any authenticated
    # customer can hit the route this feeds. See POST /kyc/{id}/review.
    status: str = Field(max_length=20)
