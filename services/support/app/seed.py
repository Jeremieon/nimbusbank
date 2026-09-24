from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Message, Ticket

# Same fixed user ids as services/auth/app/seed.py's SEED_USERS — kept in sync
# by hand since these are separate databases with no cross-service access. A
# couple of tickets with messages so the customer view and the agent console
# aren't empty on first load. Inserted in this order so ticket ids land
# sequentially at 1..N — easy to demo the IDOR by walking id=1,2,3,....
SEED_TICKETS = [
    {
        "user_id": "22222222-2222-2222-2222-222222222222",  # alice
        "subject": "Card declined at checkout",
        "status": "open",
        "messages": [
            {"sender": "customer", "body": "My card was declined at the grocery store this morning."},
            {"sender": "agent", "body": "Thanks Alice — I can see a temporary hold. I've cleared it now."},
        ],
    },
    {
        "user_id": "33333333-3333-3333-3333-333333333333",  # bob
        "subject": "How do I enable the authenticator app?",
        "status": "open",
        "messages": [
            {"sender": "customer", "body": "I want to turn on 2FA. Where is that setting?"},
        ],
    },
]


async def seed_tickets(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(Ticket))
    if count:
        return

    for item in SEED_TICKETS:
        ticket = Ticket(
            user_id=item["user_id"],
            subject=item["subject"],
            status=item["status"],
        )
        db.add(ticket)
        await db.flush()  # assign ticket.id before adding its messages
        for msg in item["messages"]:
            db.add(Message(ticket_id=ticket.id, sender=msg["sender"], body=msg["body"]))
    await db.commit()
