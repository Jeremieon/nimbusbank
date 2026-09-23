import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .cardgen import generate_card
from .config import settings
from .database import AsyncSessionLocal, Base, engine, get_db
from .models import Card
from .obslog import install_request_logging
from .schemas import CardMaskedOut, CardOut, CardPatchRequest, IssueCardRequest
from .security import fetch_jwks, get_current_user  # require_admin defined but deliberately unused
from .seed import seed_cards

app = FastAPI(
    title="NimbusBank Cards Service",
    description="Issues and manages payment cards funded by accounts. Every route below requires a bearer JWT, validated against auth-service's JWKS.",
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
# or fails a real request (see obslog.py); services keep working if admin is down.
install_request_logging(app, "cards")


def _to_out(card: Card) -> CardOut:
    return CardOut(
        id=card.id,
        user_id=str(card.user_id),
        account_id=card.account_id,
        card_number=card.card_number,
        last4=card.last4,
        expiry=card.expiry,
        cvv=card.cvv,
        card_type=card.card_type,
        status=card.status,
        spend_limit_cents=card.spend_limit_cents,
        created_at=card.created_at,
    )


def _to_masked(card: Card) -> CardMaskedOut:
    return CardMaskedOut(
        id=card.id,
        user_id=str(card.user_id),
        account_id=card.account_id,
        last4=card.last4,
        expiry=card.expiry,
        card_type=card.card_type,
        status=card.status,
        spend_limit_cents=card.spend_limit_cents,
        created_at=card.created_at,
    )


@app.on_event("startup")
async def on_startup() -> None:
    # Schema creation/evolution is owned by Alembic now (the container runs
    # `alembic upgrade head` before uvicorn starts), so startup only seeds.
    async with AsyncSessionLocal() as session:
        await seed_cards(session)

    # Best-effort warm cache so the first real request doesn't pay the JWKS
    # fetch latency.
    try:
        await fetch_jwks()
    except httpx.HTTPError:
        pass


@app.get("/health", tags=["health"], summary="Liveness check")
async def health():
    return {"status": "ok"}


@app.post(
    "/cards",
    response_model=CardOut,
    status_code=201,
    tags=["cards"],
    summary="Issue a new payment card funded by an account",
)
async def issue_card(
    payload: IssueCardRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # INTENTIONALLY VULNERABLE: no check that `account_id` belongs to
    # `current["user_id"]` (and no call to accounts-service to verify it even
    # exists). Any authenticated user can issue a card drawing on anyone else's
    # funding account (API Security: BOLA / business-logic flaw). The card is
    # owned by the caller (user_id from the token) but funded by an account
    # they don't own.
    material = generate_card()
    card = Card(
        user_id=current["user_id"],
        account_id=payload.account_id,
        card_number=material["card_number"],
        last4=material["last4"],
        expiry=material["expiry"],
        cvv=material["cvv"],
        card_type=payload.card_type,
        status="active",
        spend_limit_cents=payload.spend_limit_cents if payload.spend_limit_cents is not None else 100000,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return _to_out(card)


@app.get(
    "/cards",
    response_model=list[CardMaskedOut],
    tags=["cards"],
    summary="List the caller's own cards (correctly scoped, for contrast with the routes below)",
)
async def list_cards(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Correctly scoped to the caller, and returns the masked view (last4 only,
    # no PAN/CVV) to look bank-like — the deliberate contrast with the
    # per-id route below.
    rows = (
        (await db.execute(select(Card).where(Card.user_id == current["user_id"]).order_by(Card.id)))
        .scalars()
        .all()
    )
    return [_to_masked(c) for c in rows]


@app.get(
    "/cards/{card_id}",
    response_model=CardOut,
    tags=["cards"],
    summary="Get full card detail by id",
)
async def get_card(card_id: int, current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: no check that this card belongs to
    # `current["user_id"]`, and ids are small sequential integers, so
    # enumerating every card in the bank is a matter of walking id=1,2,3,...
    # (API Security: Broken Object Level Authorization).
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # INTENTIONALLY VULNERABLE: excessive data exposure — the FULL 16-digit PAN
    # and the CVV are returned here, even for a card the caller doesn't own.
    # The list route above masks these; this one hands over everything needed
    # to use the card (API Security: Sensitive Data Exposure + BOLA).
    return _to_out(card)


@app.patch(
    "/cards/{card_id}",
    response_model=CardOut,
    tags=["cards"],
    summary="Update mutable fields on a card",
)
async def update_card(
    card_id: int,
    payload: CardPatchRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # INTENTIONALLY VULNERABLE: mass assignment plus no ownership check. Any of
    # spend_limit_cents / status / account_id / user_id present in the body is
    # written straight onto the card — a caller can raise their own spend limit
    # arbitrarily, reassign the card to another funding account, or hand the
    # card to a different user_id entirely, on any card id (API Security: Mass
    # Assignment + BOLA).
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(card, field, value)

    await db.commit()
    await db.refresh(card)
    return _to_out(card)


@app.post(
    "/cards/{card_id}/freeze",
    response_model=CardOut,
    tags=["cards"],
    summary="Freeze a card",
)
async def freeze_card(card_id: int, current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: no ownership check — any authenticated caller
    # can freeze anyone's card by id (API Security: BOLA).
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card.status = "frozen"
    await db.commit()
    await db.refresh(card)
    return _to_out(card)


@app.post(
    "/cards/{card_id}/unfreeze",
    response_model=CardOut,
    tags=["cards"],
    summary="Unfreeze a card",
)
async def unfreeze_card(card_id: int, current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: no ownership check — any authenticated caller
    # can unfreeze anyone's card by id (API Security: BOLA).
    card = await db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    card.status = "active"
    await db.commit()
    await db.refresh(card)
    return _to_out(card)
