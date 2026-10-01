"""
shadow_api.py — traffic to undocumented endpoints absent from the schema.

F5 ADSP Cyber Range challenge:
    #8 API discovery — traffic to a shadow/undocumented endpoint that is NOT
       in the service's OpenAPI schema.
XC signal produced:
    API Discovery. XC learns the real API surface from observed traffic and
    compares it to the uploaded schema; an endpoint it sees but that the schema
    never declared is flagged as a shadow / undocumented API.

The shadow routes (added in the app with include_in_schema=False, so they are
served but never appear in /openapi.json):
    GET  /api/accounts/legacy/export     — dumps every account incl. full SSN
    POST /api/accounts/legacy/orders      — echoes a body whose `amount` is a
                                            string (an undocumented field type)

This script generates traffic to both AND verifies they are genuinely absent
from /api/accounts/openapi.json.

Usage:
    python3 shadow_api.py                 # 5 hits each
    python3 shadow_api.py --count 10
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, make_client

SHADOW_PATHS = ["/legacy/export", "/legacy/orders"]


def main():
    ap = argparse.ArgumentParser(description="Shadow / undocumented API traffic generator.")
    ap.add_argument("--count", type=int, default=5, help="requests to each shadow endpoint")
    args = ap.parse_args()

    print(f"Target: {BASE_URL}/api/accounts  (shadow endpoints, no auth required)")
    print("lab-only — generating API-discovery traffic to undocumented routes\n")

    export_codes, orders_codes = {}, {}
    with make_client() as client:
        for _ in range(args.count):
            r = client.get("/api/accounts/legacy/export")
            export_codes[r.status_code] = export_codes.get(r.status_code, 0) + 1
            # amount deliberately a STRING — an undocumented field type.
            r = client.post("/api/accounts/legacy/orders",
                            json={"account_id": 3, "amount": "250.00", "symbol": "NMBS"})
            orders_codes[r.status_code] = orders_codes.get(r.status_code, 0) + 1

        # Sample one of each so the report proves they're live.
        exp = client.get("/api/accounts/legacy/export")
        exp_n = len(exp.json()) if exp.status_code == 200 else 0
        order = client.post("/api/accounts/legacy/orders",
                            json={"account_id": 3, "amount": "250.00", "symbol": "NMBS"})
        order_body = order.json() if order.status_code == 200 else {}

        # Verify the routes are NOT in the documented schema.
        schema = client.get("/api/accounts/openapi.json")
        schema_text = schema.text
        absent = {p: (p not in schema_text) for p in SHADOW_PATHS}

    print("--- report ---")
    print(f"GET  /legacy/export   x{args.count}: {export_codes}  "
          f"(sample returned {exp_n} accounts)")
    print(f"POST /legacy/orders   x{args.count}: {orders_codes}  "
          f"(sample id={order_body.get('id')}, amount={order_body.get('amount')!r} "
          f"type={type(order_body.get('amount')).__name__})")
    print("\nshadow verification against /api/accounts/openapi.json:")
    for p, is_absent in absent.items():
        print(f"  {p}: {'ABSENT from schema (shadow ✓)' if is_absent else 'PRESENT (not shadow!)'}")
    if all(absent.values()):
        print("\nboth endpoints are reachable yet undocumented — classic shadow APIs "
              "for XC API-discovery to flag.")


if __name__ == "__main__":
    main()
