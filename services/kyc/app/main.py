import os

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, Base, engine, get_db
from .models import KycDocument
from .obslog import install_request_logging
from .schemas import KycDocumentOut, ReviewRequest
from .security import fetch_jwks, get_current_user  # require_admin defined but deliberately unused
from .seed import seed_documents

app = FastAPI(
    title="NimbusBank KYC Service",
    description="Owns customer identity documents (Know Your Customer). Every route below requires a bearer JWT, validated against auth-service's JWKS.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fire-and-forget request logging to admin-service's /ingest sink. Never blocks
# or fails a real request (see obslog.py); this service keeps working if admin
# is down.
install_request_logging(app, "kyc")

# Uploaded KYC files land here. Created at startup.
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")


def _to_out(doc: KycDocument) -> KycDocumentOut:
    return KycDocumentOut(
        id=doc.id,
        user_id=str(doc.user_id),
        doc_type=doc.doc_type,
        original_filename=doc.original_filename,
        content_type=doc.content_type,
        stored_path=doc.stored_path,
        size_bytes=doc.size_bytes,
        status=doc.status,
        created_at=doc.created_at,
    )


@app.on_event("startup")
async def on_startup() -> None:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_documents(session, UPLOAD_DIR)

    # Best-effort warm cache so the first real request doesn't pay the JWKS
    # fetch latency. depends_on: condition: service_healthy on auth means
    # this should always succeed, but a lab shouldn't crash-loop over it.
    try:
        await fetch_jwks()
    except httpx.HTTPError:
        pass


@app.get("/health", tags=["health"], summary="Liveness check")
async def health():
    return {"status": "ok"}


@app.post(
    "/kyc/upload",
    response_model=KycDocumentOut,
    status_code=201,
    tags=["kyc"],
    summary="Upload a KYC identity document (multipart file upload)",
)
async def upload_document(
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # INTENTIONALLY VULNERABLE: no file-type / extension allowlist, no
    # content-type check, no magic-byte inspection, and no malware scan — any
    # file at all (an executable, a shell script, an EICAR test file) is
    # accepted and stored (API Security / WAF: Malicious File Upload).
    #
    # INTENTIONALLY VULNERABLE: the uploaded file's own client-supplied
    # filename is joined onto UPLOAD_DIR with NO sanitization — no
    # os.path.basename(), no "../" rejection, no allowlist. A filename like
    # "../../evil.sh" escapes UPLOAD_DIR and writes elsewhere on the
    # filesystem (Path Traversal on write).
    stored_path = os.path.join(UPLOAD_DIR, file.filename)

    # INTENTIONALLY VULNERABLE: no size cap — the entire body is read into
    # memory and written to disk regardless of how large it is (DoS surface).
    contents = await file.read()
    os.makedirs(os.path.dirname(stored_path) or UPLOAD_DIR, exist_ok=True)
    with open(stored_path, "wb") as f:
        f.write(contents)

    doc = KycDocument(
        user_id=current["user_id"],
        doc_type=doc_type,
        original_filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        stored_path=stored_path,
        size_bytes=len(contents),
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _to_out(doc)


@app.get(
    "/kyc/documents",
    response_model=list[KycDocumentOut],
    tags=["kyc"],
    summary="List the caller's own KYC documents (correctly scoped, for contrast with the routes below)",
)
async def list_documents(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        (await db.execute(select(KycDocument).where(KycDocument.user_id == current["user_id"])))
        .scalars()
        .all()
    )
    return [_to_out(d) for d in rows]


# Registered BEFORE "/kyc/{document_id}" so this literal path is never mistaken
# for an int path param.
@app.get(
    "/kyc/pending",
    response_model=list[KycDocumentOut],
    tags=["kyc"],
    summary="Compliance queue: list every user's pending KYC documents",
)
async def list_pending(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: this is meant to be a compliance-officer / admin
    # view, but the dependency is `get_current_user`, not `require_admin`
    # (defined right in this service's security.py and simply never imported
    # here). Any authenticated customer can enumerate every other customer's
    # identity documents — names, document types, filenames (API Security:
    # Broken Function Level Authorization + Sensitive Data / PII exposure).
    rows = (
        (await db.execute(select(KycDocument).where(KycDocument.status == "pending")))
        .scalars()
        .all()
    )
    return [_to_out(d) for d in rows]


@app.get(
    "/kyc/{document_id}",
    response_model=KycDocumentOut,
    tags=["kyc"],
    summary="Get KYC document metadata by id",
)
async def get_document(document_id: int, current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: IDOR / BOLA — no check that this document
    # belongs to `current["user_id"]`, and ids are small sequential integers,
    # so any authenticated user can read any customer's KYC metadata by
    # walking id=1,2,3,... (API Security: Broken Object Level Authorization).
    doc = await db.get(KycDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _to_out(doc)


@app.get(
    "/kyc/{document_id}/download",
    tags=["kyc"],
    summary="Download the stored KYC file",
)
async def download_document(document_id: int, current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: IDOR — no ownership check, same as above, so
    # any authenticated user can pull down any customer's raw identity
    # document. It also streams back whatever was uploaded, including malware
    # that the upload route never scanned (API Security: BOLA + Malicious File
    # download).
    doc = await db.get(KycDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not os.path.exists(doc.stored_path):
        raise HTTPException(status_code=404, detail="Stored file missing")
    return FileResponse(
        doc.stored_path,
        media_type=doc.content_type,
        filename=doc.original_filename,
    )


@app.post(
    "/kyc/{document_id}/review",
    response_model=KycDocumentOut,
    tags=["kyc"],
    summary="Compliance action: approve or reject a KYC document",
)
async def review_document(
    document_id: int,
    payload: ReviewRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # INTENTIONALLY VULNERABLE: BFLA — meant to be a compliance-officer action,
    # but guarded only by `get_current_user`, not `require_admin`. Any
    # authenticated customer can approve or reject anyone's KYC (API Security:
    # Broken Function Level Authorization). No ownership check either.
    doc = await db.get(KycDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = payload.status
    await db.commit()
    await db.refresh(doc)
    return _to_out(doc)
