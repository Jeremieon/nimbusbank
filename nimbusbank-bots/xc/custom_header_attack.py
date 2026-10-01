"""
custom_header_attack.py — a "zero-day" delivered via a custom request header.

F5 ADSP Cyber Range challenge:
    #4 Zero-day via a custom request header — requests carrying a specific
       custom header (name + value) a Service Policy would match, plus a
       "re-engineered" variant that renames the header to evade a narrow rule.
XC signal produced:
    Service Policy custom-header match: a rule keyed on header name+value fires
    on every request that carries it. The --rename variant (X-Test1 -> X-Test2)
    shows why a value/name-pinned rule is brittle — rename the header and the
    same payload sails past, which is the lesson to practise mitigating.

Usage:
    python3 custom_header_attack.py                       # X-Test1: <sig>, 20 reqs
    python3 custom_header_attack.py --rename               # re-engineered: X-Test2
    python3 custom_header_attack.py --header X-Foo --value bar --count 50
    python3 custom_header_attack.py --path /api/accounts/accounts
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, make_client

DEFAULT_HEADER = "X-Test1"
RENAMED_HEADER = "X-Test2"
# A signature-like value a Service Policy would be written to match on.
DEFAULT_VALUE = "zeroday-sig-7f3a9c"


def main():
    ap = argparse.ArgumentParser(description="Custom-header zero-day signal generator.")
    ap.add_argument("--path", default="/api/auth/health",
                    help="target path (default is an open health route so no auth is needed)")
    ap.add_argument("--header", default=DEFAULT_HEADER, help="custom header NAME")
    ap.add_argument("--value", default=DEFAULT_VALUE, help="custom header VALUE")
    ap.add_argument("--rename", action="store_true",
                    help=f"re-engineered variant: rename the header to {RENAMED_HEADER}")
    ap.add_argument("--count", type=int, default=20, help="number of requests to send")
    ap.add_argument("--delay", type=float, default=0.02)
    args = ap.parse_args()

    header_name = RENAMED_HEADER if args.rename else args.header
    variant = "re-engineered (renamed header)" if args.rename else "original"

    print(f"Target: {BASE_URL}{args.path}")
    print(f"variant: {variant}")
    print(f"custom header: {header_name}: {args.value}")
    print(f"lab-only — generating a Service-Policy custom-header match x{args.count}\n")

    counts = {}
    start = time.time()
    with make_client() as client:
        for i in range(args.count):
            try:
                r = client.get(args.path, headers={header_name: args.value})
                code = r.status_code
            except Exception:  # noqa: BLE001
                code = "ERR"
            counts[code] = counts.get(code, 0) + 1
            if args.delay:
                time.sleep(args.delay)

    print("--- report ---")
    print(f"requests sent: {args.count} in {time.time() - start:.2f}s")
    print(f"header carried on every request: {header_name}: {args.value}")
    print(f"status breakdown: {counts}")
    if not args.rename:
        print("tip: re-run with --rename to fire the re-engineered variant "
              f"({RENAMED_HEADER}) and see a name-pinned policy miss it.")


if __name__ == "__main__":
    main()
