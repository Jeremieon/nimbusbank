from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from .security import hash_password

# Fixed, non-random UUIDs so accounts-service's seed data (which lives in a
# completely separate database — no cross-service DB access, ever) can
# reference the *same* user ids without either service calling the other at
# seed time. Keep this list in sync with services/accounts/app/seed.py.
SEED_USERS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "admin@nimbusbank.io",
        "full_name": "Nimbus Admin",
        "password": "admin123",
        "ssn_last4": "0000",
        "role": "admin",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "email": "alice@nimbusbank.io",
        "full_name": "Alice Nguyen",
        "password": "password123",
        "ssn_last4": "1111",
        "role": "customer",
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "email": "bob@nimbusbank.io",
        "full_name": "Bob Martinez",
        "password": "password123",
        "ssn_last4": "2222",
        "role": "customer",
    },
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "email": "carol@nimbusbank.io",
        "full_name": "Carol Odom",
        "password": "password123",
        "ssn_last4": "3333",
        "role": "customer",
    },
    {
        "id": "55555555-5555-5555-5555-555555555555",
        "email": "dave@nimbusbank.io",
        "full_name": "Dave Kowalski",
        "password": "password123",
        "ssn_last4": "4444",
        "role": "customer",
    },
]


async def seed_users(db: AsyncSession) -> None:
    count = await db.scalar(select(func.count()).select_from(User))
    if count:
        return

    for item in SEED_USERS:
        db.add(
            User(
                id=item["id"],
                email=item["email"],
                full_name=item["full_name"],
                password_hash=hash_password(item["password"]),
                ssn_last4=item["ssn_last4"],
                role=item["role"],
                is_verified=True,
            )
        )
    await db.commit()
