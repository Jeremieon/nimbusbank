import os

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import KycDocument

# Same fixed user ids as services/auth/app/seed.py's SEED_USERS — kept in sync
# by hand since these are separate databases with no cross-service access.
# A few pending/approved documents across a couple of customers so the
# compliance "pending" view and the IDOR download work out of the box.
#
# Inserted in this exact order so ids land sequentially at 1..N: easy to demo
# the KYC IDOR by walking id=1,2,3,... while logged in as any one user.
SEED_DOCUMENTS = [
    # Alice Nguyen
    {"user_id": "22222222-2222-2222-2222-222222222222", "doc_type": "id_card",
     "original_filename": "alice_passport.txt", "content_type": "text/plain",
     "status": "approved", "body": "PASSPORT — Alice Nguyen — No. X1234567 — DOB 1990-07-24"},
    {"user_id": "22222222-2222-2222-2222-222222222222", "doc_type": "proof_of_address",
     "original_filename": "alice_utility_bill.txt", "content_type": "text/plain",
     "status": "pending", "body": "UTILITY BILL — Alice Nguyen — 42 Cloud St — balance due $88.10"},
    # Bob Martinez
    {"user_id": "33333333-3333-3333-3333-333333333333", "doc_type": "id_card",
     "original_filename": "bob_drivers_license.txt", "content_type": "text/plain",
     "status": "pending", "body": "DRIVER LICENSE — Bob Martinez — No. D9988776 — DOB 1988-11-02"},
]


async def seed_documents(db: AsyncSession, upload_dir: str) -> None:
    count = await db.scalar(select(func.count()).select_from(KycDocument))
    if count:
        return

    for item in SEED_DOCUMENTS:
        # Write a tiny placeholder file so the download route serves something
        # real on a fresh database.
        stored_name = f"seed_{item['user_id'][:8]}_{item['original_filename']}"
        stored_path = os.path.join(upload_dir, stored_name)
        with open(stored_path, "w") as f:
            f.write(item["body"])
        size_bytes = os.path.getsize(stored_path)

        db.add(
            KycDocument(
                user_id=item["user_id"],
                doc_type=item["doc_type"],
                original_filename=item["original_filename"],
                content_type=item["content_type"],
                stored_path=stored_path,
                size_bytes=size_bytes,
                status=item["status"],
            )
        )
    await db.commit()
