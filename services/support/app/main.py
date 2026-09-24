import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, Base, engine, get_db
from .models import Message, Ticket
from .obslog import install_request_logging
from .schemas import (
    CreateTicketRequest,
    MessageOut,
    PostMessageRequest,
    TicketDetailOut,
    TicketOut,
)
from .security import fetch_jwks, get_current_user
from .seed import seed_tickets

app = FastAPI(
    title="NimbusBank Support Service",
    description="Owns support tickets and their message threads. Every route below requires a bearer JWT, validated against auth-service's JWKS — but note this service deliberately skips expiry validation (see security.py).",
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
install_request_logging(app, "support")


def _ticket_out(ticket: Ticket) -> TicketOut:
    return TicketOut(
        id=ticket.id,
        user_id=str(ticket.user_id),
        subject=ticket.subject,
        status=ticket.status,
        created_at=ticket.created_at,
    )


def _message_out(msg: Message) -> MessageOut:
    return MessageOut(
        id=msg.id,
        ticket_id=msg.ticket_id,
        sender=msg.sender,
        body=msg.body,
        created_at=msg.created_at,
    )


@app.on_event("startup")
async def on_startup() -> None:
    # Schema creation/evolution is owned by Alembic now (the container runs
    # `alembic upgrade head` before uvicorn starts), so startup only seeds.
    async with AsyncSessionLocal() as session:
        await seed_tickets(session)

    try:
        await fetch_jwks()
    except httpx.HTTPError:
        pass


@app.get("/health", tags=["health"], summary="Liveness check")
async def health():
    return {"status": "ok"}


@app.post(
    "/tickets",
    response_model=TicketDetailOut,
    status_code=201,
    tags=["support"],
    summary="Open a support ticket with a first message",
)
async def create_ticket(
    payload: CreateTicketRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ticket = Ticket(user_id=current["user_id"], subject=payload.subject, status="open")
    db.add(ticket)
    await db.flush()
    first = Message(ticket_id=ticket.id, sender="customer", body=payload.body)
    db.add(first)
    await db.commit()
    await db.refresh(ticket)
    await db.refresh(first)
    return TicketDetailOut(**_ticket_out(ticket).model_dump(), messages=[_message_out(first)])


@app.get(
    "/tickets",
    response_model=list[TicketOut],
    tags=["support"],
    summary="List the caller's own tickets (correctly scoped, for contrast with the routes below)",
)
async def list_my_tickets(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        (await db.execute(
            select(Ticket).where(Ticket.user_id == current["user_id"]).order_by(Ticket.created_at.desc())
        ))
        .scalars()
        .all()
    )
    return [_ticket_out(t) for t in rows]


# Registered BEFORE "/tickets/{ticket_id}" so this literal path is never
# mistaken for an int path param.
@app.get(
    "/tickets/all",
    response_model=list[TicketOut],
    tags=["support"],
    summary="Agent console: list every ticket across all users",
)
async def list_all_tickets(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: this is meant to be an agent / admin console,
    # but there is no role check — it's guarded only by `get_current_user`, so
    # any authenticated customer can list every other customer's tickets (API
    # Security: Broken Function Level Authorization + IDOR at scale).
    rows = (
        (await db.execute(select(Ticket).order_by(Ticket.created_at.desc())))
        .scalars()
        .all()
    )
    return [_ticket_out(t) for t in rows]


@app.get(
    "/tickets/{ticket_id}",
    response_model=TicketDetailOut,
    tags=["support"],
    summary="Get a ticket and its full message thread",
)
async def get_ticket(ticket_id: int, current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: IDOR — no check that this ticket belongs to
    # `current["user_id"]`, and ids are small sequential integers, so any
    # authenticated user can read any customer's ticket and its messages by
    # walking id=1,2,3,... (API Security: Broken Object Level Authorization).
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msgs = (
        (await db.execute(
            select(Message).where(Message.ticket_id == ticket_id).order_by(Message.created_at.asc())
        ))
        .scalars()
        .all()
    )
    return TicketDetailOut(**_ticket_out(ticket).model_dump(), messages=[_message_out(m) for m in msgs])


@app.post(
    "/tickets/{ticket_id}/messages",
    response_model=MessageOut,
    status_code=201,
    tags=["support"],
    summary="Append a message to a ticket thread",
)
async def post_message(
    ticket_id: int,
    payload: PostMessageRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # INTENTIONALLY VULNERABLE: no ownership check on which ticket you may post
    # to — any authenticated user can append a message to anyone's ticket
    # (IDOR write). And `body` is stored EXACTLY as submitted; the agent
    # console later renders it as raw HTML (dangerouslySetInnerHTML), so a
    # `<script>` / `<img onerror=...>` payload planted here fires in the
    # agent's browser — stored XSS / formjacking (see models.py and
    # frontend/src/pages/AgentConsole.jsx).
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    msg = Message(ticket_id=ticket_id, sender=payload.sender, body=payload.body)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return _message_out(msg)
