from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Transfer

# References the sequential ids accounts-service's own seed produces (see
# services/accounts/app/seed.py): 1-2 = admin, 3-4 = alice, 5-6 = bob,
# 7-8 = carol, 9-10 = dave. Only correct against a freshly-seeded accounts
# database — good enough to give the transaction history view some rows on
# first load.
SEED_TRANSFERS = [
    {"from_account_id": 3, "to_account_id": 5, "amount_cents": 4500, "memo": "Dinner split"},
    {"from_account_id": 5, "to_account_id": 3, "amount_cents": 2000, "memo": "Concert tickets"},
    {"from_account_id": 7, "to_account_id": 9, "amount_cents": 120000, "memo": "Rent - September"},
]


async def seed_transfers(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(Transfer))
    if count:
        return

    for item in SEED_TRANSFERS:
        db.add(
            Transfer(
                from_account_id=item["from_account_id"],
                to_account_id=item["to_account_id"],
                amount_cents=item["amount_cents"],
                memo=item["memo"],
                status="completed",
            )
        )
    await db.commit()
