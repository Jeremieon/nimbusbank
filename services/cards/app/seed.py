from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .cardgen import generate_card
from .models import Card

# Same fixed user UUIDs as services/auth/app/seed.py, and the sequential
# account ids accounts-service's own seed produces (3-4 = alice, 5-6 = bob,
# 7-8 = carol, 9-10 = dave). One virtual card per seeded customer, funded by
# their checking account (ids 3, 5, 7, 9). A couple start frozen for variety.
# Cards land at sequential ids 1-4, so BOLA by walking id=1..N is trivial.
SEED_CARDS = [
    {"user_id": "22222222-2222-2222-2222-222222222222", "account_id": 3, "status": "active"},   # alice
    {"user_id": "33333333-3333-3333-3333-333333333333", "account_id": 5, "status": "frozen"},   # bob
    {"user_id": "44444444-4444-4444-4444-444444444444", "account_id": 7, "status": "active"},   # carol
    {"user_id": "55555555-5555-5555-5555-555555555555", "account_id": 9, "status": "frozen"},   # dave
]


async def seed_cards(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(Card))
    if count:
        return

    for item in SEED_CARDS:
        material = generate_card()
        db.add(
            Card(
                user_id=item["user_id"],
                account_id=item["account_id"],
                card_number=material["card_number"],
                last4=material["last4"],
                expiry=material["expiry"],
                cvv=material["cvv"],
                card_type="virtual",
                status=item["status"],
                spend_limit_cents=100000,
            )
        )
    await db.commit()
