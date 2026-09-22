import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, Base, engine, get_db
from .models import Transfer
from .schemas import AdminOverrideRequest, TransferOut, TransferRequest
from .security import fetch_jwks, get_current_user, require_admin
from .seed import seed_transfers

app = FastAPI(
    title="NimbusBank Transfers Service",
    description="Owns money-movement records. Every route requires a bearer JWT, validated against auth-service's JWKS.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_out(transfer: Transfer) -> TransferOut:
    return TransferOut(
        id=transfer.id,
        from_account_id=transfer.from_account_id,
        to_account_id=transfer.to_account_id,
        amount_cents=transfer.amount_cents,
        memo=transfer.memo,
        status=transfer.status,
        created_at=transfer.created_at,
    )


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_transfers(session)

    try:
        await fetch_jwks()
    except httpx.HTTPError:
        pass


@app.get("/health", tags=["health"], summary="Liveness check")
async def health():
    return {"status": "ok"}


@app.post(
    "/transfers",
    response_model=TransferOut,
    status_code=201,
    tags=["transfers"],
    summary="Record a money transfer between two accounts",
)
async def create_transfer(
    payload: TransferRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Simplification, not a vulnerability: this service only records the
    # transfer row. It does not call accounts-service to actually debit/
    # credit balances — wiring that up end-to-end is out of scope for v1.
    #
    # INTENTIONALLY VULNERABLE: no check that `from_account_id` belongs to
    # `current["user_id"]` — any authenticated user can record a transfer
    # moving funds out of any account (BOLA / business-logic flaw).
    #
    # INTENTIONALLY VULNERABLE: no minimum/maximum on amount_cents (negative
    # values are accepted), no daily limit, and no rate limiting on repeated
    # calls to this endpoint.
    transfer = Transfer(
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
        amount_cents=payload.amount_cents,
        memo=payload.memo,
        status="completed",
    )
    db.add(transfer)
    await db.commit()
    await db.refresh(transfer)
    return _to_out(transfer)


@app.get(
    "/transfers",
    response_model=list[TransferOut],
    tags=["transfers"],
    summary="List transfers touching a given account",
)
async def list_transfers(
    account_id: int = Query(...),
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # INTENTIONALLY VULNERABLE: BOLA, same pattern as POST /transfers above —
    # no check that `account_id` belongs to the caller before returning
    # every transfer that touches it (which also serves back every `memo`,
    # including any XSS payload stored in one — see models.py).
    stmt = (
        select(Transfer)
        .where(or_(Transfer.from_account_id == account_id, Transfer.to_account_id == account_id))
        .order_by(Transfer.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_out(t) for t in rows]


@app.post(
    "/transfers/admin-override",
    tags=["transfers"],
    summary="Admin-only: force a transfer's status",
)
async def admin_override(
    payload: AdminOverrideRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # INTENTIONALLY VULNERABLE: this is meant to be admin-only, but the
    # dependency above is `get_current_user`, not `require_admin` (defined
    # right in this service's security.py, and simply never imported here).
    # get_current_user only proves the caller presented *a* valid JWT — it
    # says nothing about their role. Any authenticated customer can flip any
    # transfer's status (API Security: Broken Function Level Authorization).
    transfer = await db.get(Transfer, payload.transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")

    transfer.status = payload.new_status
    await db.commit()
    return {"id": transfer.id, "status": transfer.status}
