"""
suspicious_bot.py — an automated client that crawls many endpoints fast.

F5 ADSP Cyber Range challenge:
    #3 Suspicious bot traffic — an automated client with an HTTP-library
       User-Agent sweeping across many endpoints.
XC signal produced:
    Bot Defense / suspicious-bot detection: a non-browser client (library UA,
    no browser fingerprint) touching a wide spread of API paths in a tight
    loop looks nothing like a human and should score as an automated bot.

Logs in once, then repeatedly GETs a broad list of endpoints — accounts list,
many account ids, cards, kyc, support tickets, transfers, and health — with an
explicit HTTP-library User-Agent (configurable).

Usage:
    python3 suspicious_bot.py                      # 3 cycles, default library UA
    python3 suspicious_bot.py --cycles 5 --delay 0.05
    python3 suspicious_bot.py --user-agent "python-requests/2.31.0"
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, SEEDED_USERS, auth_headers, login, make_client

# Honest, library-style UA — the kind of string a scripted client sends. This
# is the fingerprint the bot wants XC to notice.
DEFAULT_UA = "python-httpx/0.27 (nimbusbank-xc-bot)"


def endpoint_list(max_id: int):
    paths = [
        "/api/auth/health",
        "/api/accounts/health",
        "/api/cards/health",
        "/api/kyc/health",
        "/api/support/health",
        "/api/transfers/health",
        "/api/accounts/accounts",
        "/api/cards/cards",
        "/api/kyc/kyc/documents",
        "/api/kyc/kyc/pending",
        "/api/support/tickets",
        "/api/support/tickets/all",
    ]
    for i in range(1, max_id + 1):
        paths.append(f"/api/accounts/accounts/{i}")
        paths.append(f"/api/cards/cards/{i}")
    return paths


def main():
    ap = argparse.ArgumentParser(description="Broad endpoint-crawling suspicious bot.")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    ap.add_argument("--cycles", type=int, default=3, help="how many times to sweep the list")
    ap.add_argument("--delay", type=float, default=0.02, help="seconds between requests")
    ap.add_argument("--max-id", type=int, default=6, help="highest sequential id to enumerate")
    ap.add_argument("--user-agent", default=DEFAULT_UA,
                    help="HTTP-library User-Agent the crawler announces")
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    paths = endpoint_list(args.max_id)
    print(f"Target: {BASE_URL}  (crawling {len(paths)} endpoints x {args.cycles} cycles)")
    print(f"User-Agent: {args.user_agent}")
    print("lab-only — generating suspicious-bot / automated-client traffic\n")

    counts = {}
    total, start = 0, time.time()
    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = {**auth_headers(token), "User-Agent": args.user_agent}
        for c in range(1, args.cycles + 1):
            for p in paths:
                try:
                    r = client.get(p, headers=hdrs)
                    code = r.status_code
                except Exception:  # noqa: BLE001
                    code = "ERR"
                counts[code] = counts.get(code, 0) + 1
                total += 1
                if args.delay:
                    time.sleep(args.delay)
            print(f"  cycle {c}/{args.cycles}: swept {len(paths)} endpoints")

    elapsed = time.time() - start
    print("\n--- report ---")
    print(f"requests sent: {total} across {len(paths)} distinct endpoints in {elapsed:.2f}s")
    print(f"User-Agent announced: {args.user_agent}")
    print(f"status breakdown: {counts}")


if __name__ == "__main__":
    main()
