"""
normal_users.py — a gentle baseline of well-formed, legitimate customer traffic.

Bot / traffic scenario:   Legitimate human customers using the app normally.
F5 XC category:           Good/Human traffic (the baseline a Bot Defense policy
                          must NOT block — the "known good" your false-positive
                          rate is measured against).

Each simulated customer logs in as a seeded user (weak-OTP path), then does the
kind of thing a real person does in a session, with randomized think-time
between actions:
    - view their dashboard (list accounts)
    - open one account (GET by id)
    - list a card and their transfers
    - make a small in-house transfer between their own two accounts
    - occasionally open a support ticket

Nothing here exploits a vulnerability; it is the polite, well-shaped traffic you
want a WAF to leave alone. Every request is bounded by a short timeout and the
loop runs a fixed number of cycles, so it never runs away.

Usage:
    python3 normal_users.py                      # a few cycles across seeded users
    python3 normal_users.py --cycles 5 --users alice bob
"""

import argparse
import os
import random
import sys
import time

# Allow `python3 legit/normal_users.py` from the toolkit root: add the parent
# dir (which holds config.py) to the import path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, SEEDED_ACCOUNTS, SEEDED_USERS, auth_headers,
                    login, make_client)


def think(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


def one_session(client, who: str, think_lo: float, think_hi: float) -> int:
    """Run one realistic customer session. Returns the number of requests made."""
    creds = SEEDED_USERS[who]
    checking, savings = SEEDED_ACCOUNTS[who]
    reqs = 0

    token, user = login(client, creds["email"], creds["password"])
    reqs += 2
    hdrs = auth_headers(token)
    print(f"  [{who}] signed in as {user.get('email', creds['email'])}")

    # Dashboard: list my accounts.
    think(think_lo, think_hi)
    r = client.get("/api/accounts/accounts", headers=hdrs)
    reqs += 1
    mine = r.json() if r.status_code == 200 else []
    print(f"  [{who}] dashboard: {len(mine)} account(s)")

    # Open one account.
    think(think_lo, think_hi)
    client.get(f"/api/accounts/accounts/{checking}", headers=hdrs)
    reqs += 1

    # View my cards.
    think(think_lo, think_hi)
    client.get("/api/cards/cards", headers=hdrs)
    reqs += 1

    # List my transfers on the checking account.
    think(think_lo, think_hi)
    client.get(f"/api/transfers/transfers?account_id={checking}", headers=hdrs)
    reqs += 1

    # Make a small, well-formed in-house transfer between my own two accounts.
    think(think_lo, think_hi)
    amount = random.choice([100, 250, 500, 1000])
    tr = client.post("/api/transfers/transfers", headers=hdrs, json={
        "from_account_id": checking, "to_account_id": savings,
        "amount_cents": amount, "memo": "monthly savings top-up",
    })
    reqs += 1
    if tr.status_code in (200, 201):
        print(f"  [{who}] transferred {amount} cents {checking} -> {savings}")

    # Occasionally open a support ticket.
    if random.random() < 0.4:
        think(think_lo, think_hi)
        client.post("/api/support/tickets", headers=hdrs, json={
            "subject": "Question about my statement",
            "body": "Hi, could you help me understand a line item on my last statement?",
        })
        reqs += 1
        print(f"  [{who}] opened a support ticket")

    return reqs


def main():
    ap = argparse.ArgumentParser(description="Simulate legitimate customer traffic.")
    ap.add_argument("--cycles", type=int, default=3, help="how many passes over the user set")
    ap.add_argument("--users", nargs="+", default=["alice", "bob", "carol", "dave"],
                    help="which seeded users to drive")
    ap.add_argument("--think-lo", type=float, default=0.2, help="min think-time seconds")
    ap.add_argument("--think-hi", type=float, default=1.2, help="max think-time seconds")
    args = ap.parse_args()

    print(f"Target: {BASE_URL}  (legitimate baseline traffic)\n")
    total_reqs = 0
    start = time.time()
    with make_client() as client:
        for cycle in range(1, args.cycles + 1):
            print(f"-- cycle {cycle}/{args.cycles} --")
            for who in args.users:
                try:
                    total_reqs += one_session(client, who, args.think_lo, args.think_hi)
                except Exception as exc:  # noqa: BLE001 — keep the baseline going
                    print(f"  [{who}] session error: {exc}")

    elapsed = time.time() - start
    print(f"\nDone. {total_reqs} well-formed requests across {args.cycles} cycle(s) "
          f"in {elapsed:.1f}s.")


if __name__ == "__main__":
    main()
