import os

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, Base, engine, get_db
from .fx import convert
from .models import Account
from .obslog import install_request_logging
from .schemas import (
    AccountOut,
    AccountPatchRequest,
    ApplyTransferRequest,
    ApplyTransferResponse,
    LinkExternalRequest,
)
from .security import fetch_jwks, get_current_user
from .seed import seed_accounts

app = FastAPI(
    title="NimbusBank Accounts Service",
    description="Owns account balances and statements. Every route below requires a bearer JWT, validated against auth-service's JWKS.",
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
install_request_logging(app, "accounts")

STATEMENTS_DIR = os.path.join(os.path.dirname(__file__), "statements")


def _to_out(account: Account) -> AccountOut:
    return AccountOut(
        id=account.id,
        user_id=str(account.user_id),
        account_number=account.account_number,
        account_type=account.account_type,
        balance_cents=account.balance_cents,
        currency=account.currency,
        date_of_birth=account.date_of_birth,
        ssn_full=account.ssn_full,
        created_at=account.created_at,
    )


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_accounts(session)

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


# Registered BEFORE the "/accounts/{account_id}" route below so its distinct
# "/internal/..." prefix is never mistaken for an int path param. This is the
# single place in NimbusBank where money actually moves and currency actually
# converts — transfers-service records a row then calls this over the docker
# network (http://accounts:8000/internal/apply-transfer).
@app.post(
    "/internal/apply-transfer",
    response_model=ApplyTransferResponse,
    tags=["internal"],
    summary="Debit the source account and credit the destination, converting currency via the FX table",
)
async def apply_transfer(payload: ApplyTransferRequest, db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: this endpoint is called service-to-service and
    # inherits the same no-ownership-check stance as the rest of accounts-
    # service. It never verifies that whoever triggered the upstream transfer
    # owns from_account_id — a real transfer that actually drains someone
    # else's account is exactly what makes the BOLA demo on POST /transfers
    # land (API Security: BOLA). There is also NO floor on the resulting
    # balance: it is allowed to go negative, matching the no-validation intent
    # on amount elsewhere.
    src = await db.get(Account, payload.from_account_id)
    dst = await db.get(Account, payload.to_account_id)
    if not src or not dst:
        raise HTTPException(status_code=404, detail="Source or destination account not found")

    converted_amount_cents, fx_rate = convert(payload.amount_cents, src.currency, dst.currency)

    # Debit source in its own currency, credit destination the converted
    # amount, commit atomically. No balance floor — negatives are allowed.
    src.balance_cents = src.balance_cents - payload.amount_cents
    dst.balance_cents = dst.balance_cents + converted_amount_cents
    await db.commit()
    await db.refresh(src)
    await db.refresh(dst)

    return ApplyTransferResponse(
        from_account_id=src.id,
        from_balance_cents=src.balance_cents,
        to_account_id=dst.id,
        to_balance_cents=dst.balance_cents,
        from_currency=src.currency,
        to_currency=dst.currency,
        converted_amount_cents=converted_amount_cents,
        fx_rate=fx_rate,
    )


@app.get(
    "/accounts",
    response_model=list[AccountOut],
    tags=["accounts"],
    summary="List the caller's own accounts (correctly scoped, for contrast with the routes below)",
)
async def list_accounts(current=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        (await db.execute(select(Account).where(Account.user_id == current["user_id"])))
        .scalars()
        .all()
    )
    return [_to_out(a) for a in rows]


@app.get(
    "/accounts/search",
    response_model=list[AccountOut],
    tags=["accounts"],
    summary="Search accounts by account number or type",
)
async def search_accounts(
    q: str = Query(min_length=1, max_length=200),
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # INTENTIONALLY VULNERABLE: the search term is spliced directly into the
    # SQL string via an f-string instead of a bound parameter — classic SQL
    # injection (OWASP Top 10 / F5 XC WAF: SQL Injection). Try
    # q=' OR '1'='1 or a UNION-based probe.
    query = text(
        f"SELECT id, user_id, account_number, account_type, balance_cents, currency, "
        f"date_of_birth, ssn_full, created_at FROM accounts "
        f"WHERE account_number ILIKE '%{q}%' OR account_type ILIKE '%{q}%'"
    )
    result = await db.execute(query)
    rows = result.mappings().all()
    return [AccountOut(**{**dict(row), "user_id": str(row["user_id"])}) for row in rows]


@app.get(
    "/accounts/{account_id}",
    response_model=AccountOut,
    tags=["accounts"],
    summary="Get full account detail by id",
)
async def get_account(account_id: int, current=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: no check that this account belongs to
    # `current["user_id"]`, and ids are small sequential integers, so
    # enumerating every account in the bank is a matter of walking
    # id=1,2,3,... (API Security: Broken Object Level Authorization).
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # INTENTIONALLY VULNERABLE: excessive data exposure — full SSN and date
    # of birth are returned here even though the frontend only ever shows
    # the last 4 of the SSN (API Security: Sensitive Data Exposure).
    return _to_out(account)


@app.patch(
    "/accounts/{account_id}",
    response_model=AccountOut,
    tags=["accounts"],
    summary="Update mutable fields on an account",
)
async def update_account(
    account_id: int,
    payload: AccountPatchRequest,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # INTENTIONALLY VULNERABLE: mass assignment on a privileged field
    # (balance_cents) plus no ownership check — any authenticated caller can
    # set *any* account's balance to whatever they like (API Security: Mass
    # Assignment / Excessive Data Exposure combined with BOLA).
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)
    return _to_out(account)


@app.get(
    "/accounts/{account_id}/statement",
    tags=["accounts"],
    summary="Download a plaintext/CSV account statement",
)
async def get_statement(
    account_id: int,
    file: str = Query(default="statement.csv"),
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # INTENTIONALLY VULNERABLE: `file` is joined onto STATEMENTS_DIR with no
    # sanitization at all — no os.path.basename(), no rejection of "..", no
    # allowlist of filenames. A value like
    # file=../../../../../../etc/hostname escapes the statements/ directory
    # entirely (API Security / WAF: Path Traversal). Kept safe-to-demo by
    # only ever reading files that already exist inside this container.
    path = os.path.join(STATEMENTS_DIR, file)
    try:
        with open(path, "r") as f:
            content = f.read()
    except OSError:
        raise HTTPException(status_code=404, detail="Statement file not found")

    return PlainTextResponse(content)


@app.post(
    "/accounts/link-external",
    tags=["accounts"],
    summary="Verify and link an external bank account by fetching a verification URL",
)
async def link_external_account(payload: LinkExternalRequest, current=Depends(get_current_user)):
    # INTENTIONALLY VULNERABLE: the server makes an outbound request to a
    # fully attacker-controlled URL, with no allowlist and no block on
    # internal/private addresses (127.0.0.1, 169.254.169.254, other
    # docker-internal hostnames, ...). Response status and a body snippet are
    # reflected straight back to the caller, which also makes this endpoint
    # useful for scanning internal services from outside (API Security / WAF:
    # Server-Side Request Forgery). Timeout kept short so a bad target can't
    # hang the service.
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(payload.verification_url)
        return {
            "account_id": payload.account_id,
            "requested_url": payload.verification_url,
            "status_code": resp.status_code,
            "body_snippet": resp.text[:500],
        }
    except httpx.HTTPError as exc:
        return {
            "account_id": payload.account_id,
            "requested_url": payload.verification_url,
            "error": str(exc),
        }
