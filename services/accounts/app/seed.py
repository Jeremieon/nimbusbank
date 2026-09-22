from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Account

# Same fixed ids as services/auth/app/seed.py's SEED_USERS — kept in sync by
# hand since these are two separate databases with no cross-service access.
# Two accounts each (checking + savings), inserted in this exact order so
# ids land sequentially at 1-10: easy to demo BOLA by walking id=1..10 while
# logged in as any one of these users.
SEED_ACCOUNTS = [
    # Nimbus Admin
    {"user_id": "11111111-1111-1111-1111-111111111111", "account_number": "NB-1000-0001", "account_type": "checking",
     "balance_cents": 542_311, "dob": date(1985, 3, 12), "ssn_full": "123-45-6789"},
    {"user_id": "11111111-1111-1111-1111-111111111111", "account_number": "NB-1000-0002", "account_type": "savings",
     "balance_cents": 1_200_000, "dob": date(1985, 3, 12), "ssn_full": "123-45-6789"},
    # Alice Nguyen
    {"user_id": "22222222-2222-2222-2222-222222222222", "account_number": "NB-2000-0001", "account_type": "checking",
     "balance_cents": 184_522, "dob": date(1990, 7, 24), "ssn_full": "234-56-7890"},
    {"user_id": "22222222-2222-2222-2222-222222222222", "account_number": "NB-2000-0002", "account_type": "savings",
     "balance_cents": 950_000, "dob": date(1990, 7, 24), "ssn_full": "234-56-7890"},
    # Bob Martinez
    {"user_id": "33333333-3333-3333-3333-333333333333", "account_number": "NB-3000-0001", "account_type": "checking",
     "balance_cents": 67_140, "dob": date(1988, 11, 2), "ssn_full": "345-67-8901"},
    {"user_id": "33333333-3333-3333-3333-333333333333", "account_number": "NB-3000-0002", "account_type": "savings",
     "balance_cents": 302_218, "dob": date(1988, 11, 2), "ssn_full": "345-67-8901"},
    # Carol Odom
    {"user_id": "44444444-4444-4444-4444-444444444444", "account_number": "NB-4000-0001", "account_type": "checking",
     "balance_cents": 998_431, "dob": date(1979, 5, 30), "ssn_full": "456-78-9012"},
    {"user_id": "44444444-4444-4444-4444-444444444444", "account_number": "NB-4000-0002", "account_type": "savings",
     "balance_cents": 4_500_000, "dob": date(1979, 5, 30), "ssn_full": "456-78-9012"},
    # Dave Kowalski
    {"user_id": "55555555-5555-5555-5555-555555555555", "account_number": "NB-5000-0001", "account_type": "checking",
     "balance_cents": 12_045, "dob": date(1995, 1, 18), "ssn_full": "567-89-0123"},
    {"user_id": "55555555-5555-5555-5555-555555555555", "account_number": "NB-5000-0002", "account_type": "savings",
     "balance_cents": 88_760, "dob": date(1995, 1, 18), "ssn_full": "567-89-0123"},
]


async def seed_accounts(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(Account))
    if count:
        return

    for item in SEED_ACCOUNTS:
        db.add(
            Account(
                user_id=item["user_id"],
                account_number=item["account_number"],
                account_type=item["account_type"],
                balance_cents=item["balance_cents"],
                currency="USD",
                date_of_birth=item["dob"],
                ssn_full=item["ssn_full"],
            )
        )
    await db.commit()
