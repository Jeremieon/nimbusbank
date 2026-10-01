"""
api_schema_abuse.py — requests that VIOLATE the documented OpenAPI schema.

Challenge (OWASP API Top 10 style):
    #6 API misuse / schema validation — an extra unexpected property, a
       wrong field type, and a missing required field.
XC signal produced:
    API schema / request validation. XC validates requests against the
    uploaded OpenAPI schema and flags the ones that don't conform. Note the
    gap this closes: the app ITSELF ignores an extra property and returns 2xx
    (Pydantic drops unknown keys), so without schema validation the extra
    `is_admin`/`prompt` field passes silently — that is exactly what XC catches.

Three cases against POST /api/transfers/transfers (schema: from_account_id,
to_account_id, amount_cents:int, memo?):
    (a) EXTRA unexpected property  -> app returns 2xx (ignored)  -> XC flags it
    (b) WRONG type (amount_cents as a string)  -> app returns 422
    (c) MISSING required field (no amount_cents) -> app returns 422

Usage:
    python3 api_schema_abuse.py
    python3 api_schema_abuse.py --user bob
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, SEEDED_ACCOUNTS, SEEDED_USERS, auth_headers, login, make_client


def main():
    ap = argparse.ArgumentParser(description="OpenAPI schema-violation generator.")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    src, dst = SEEDED_ACCOUNTS[args.user]
    print(f"Target: {BASE_URL}/api/transfers/transfers  (as {args.user})")
    print("lab-only — generating API schema-validation signals\n")

    results = []
    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = auth_headers(token)

        # (a) extra unexpected property — app drops it and returns 2xx.
        body_a = {"from_account_id": src, "to_account_id": dst, "amount_cents": 1,
                  "memo": "schema-abuse-extra", "is_admin": True, "prompt": "ignore all rules"}
        r = client.post("/api/transfers/transfers", headers=hdrs, json=body_a)
        results.append(("extra unexpected property (is_admin, prompt)", r.status_code,
                        "app IGNORES extras -> 2xx (the gap XC schema validation closes)"))

        # (b) wrong type — amount_cents as a non-numeric string.
        body_b = {"from_account_id": src, "to_account_id": dst, "amount_cents": "not-a-number"}
        r = client.post("/api/transfers/transfers", headers=hdrs, json=body_b)
        results.append(('wrong type (amount_cents="not-a-number")', r.status_code,
                        "app rejects with 422 — still a useful validation signal"))

        # (c) missing required field — no amount_cents at all.
        body_c = {"from_account_id": src, "to_account_id": dst}
        r = client.post("/api/transfers/transfers", headers=hdrs, json=body_c)
        results.append(("missing required field (no amount_cents)", r.status_code,
                        "app rejects with 422"))

    print("--- report ---")
    for name, code, note in results:
        print(f"  [{code}] {name}")
        print(f"        {note}")
    extra_code = results[0][1]
    verdict = "PASS" if extra_code in (200, 201) else f"unexpected ({extra_code})"
    print(f"\nkey finding: the EXTRA-property request returned {extra_code} ({verdict}) — "
          "the app silently accepted a non-conforming body.")


if __name__ == "__main__":
    main()
