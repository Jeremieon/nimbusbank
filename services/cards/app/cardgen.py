import random
from datetime import datetime, timedelta, timezone


def generate_card() -> dict:
    """Generate a fresh set of card material for issuance/seeding: a Visa-style
    PAN ("4" + 15 random digits), a 3-digit CVV, an expiry ~3 years out in
    "MM/YY" form, and last4 derived from the PAN. Fake data for the lab only."""
    pan = "4" + "".join(random.choices("0123456789", k=15))
    cvv = "".join(random.choices("0123456789", k=3))
    expiry_dt = datetime.now(timezone.utc) + timedelta(days=365 * 3)
    return {
        "card_number": pan,
        "last4": pan[-4:],
        "cvv": cvv,
        "expiry": expiry_dt.strftime("%m/%y"),
    }
