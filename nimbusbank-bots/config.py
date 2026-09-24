"""
Shared configuration + helpers for the NimbusBank bot / traffic toolkit.

Everything here targets the LOCAL NimbusBank lab through the Nginx gateway.
Override the base URL with the NIMBUS_URL environment variable (e.g. set it to
http://gateway:80 when running inside the compose network).

Gateway path convention (see ../frontend/src/api.js and gateway/nginx.conf):
  - auth:      /api/auth/<route>            (routes are bare)
  - accounts:  /api/accounts/accounts/...   (service routes start with /accounts)
  - transfers: /api/transfers/transfers/...
  - kyc:       /api/kyc/kyc/...
  - support:   /api/support/tickets/...     (service routes start with /tickets)
  - cards:     /api/cards/cards/...
  - admin:     /api/admin/admin/...
  - health:    /api/<svc>/health            (single segment for every service)
"""

import os

import httpx

# --------------------------------------------------------------------------
# Target + knobs
# --------------------------------------------------------------------------

# Base URL of the gateway. Default is the local lab; override with NIMBUS_URL.
BASE_URL = os.environ.get("NIMBUS_URL", "http://localhost:80").rstrip("/")

# Short per-request timeout so a bot never hangs on a slow/blocked request.
HTTP_TIMEOUT = float(os.environ.get("NIMBUS_TIMEOUT", "8.0"))

# Default concurrency / rate knob shared by the load-ish scripts. Kept modest
# so nothing wedges a laptop; every script also exposes its own --concurrency.
DEFAULT_CONCURRENCY = int(os.environ.get("NIMBUS_CONCURRENCY", "8"))

# A plain, honest-looking client UA. The point of this lab is NOT evasion — the
# bots announce themselves as scripts so you can watch them land on the Ops
# console and, later, see what a WAF/Bot Defense in front of the app does.
USER_AGENT = os.environ.get("NIMBUS_UA", "nimbusbank-bots/1.0 (+lab-only)")

# --------------------------------------------------------------------------
# Seeded lab credentials (services/*/app/seed.py). Lab-only, never secret.
# --------------------------------------------------------------------------

SEEDED_USERS = {
    "admin": {"email": "admin@nimbusbank.io", "password": "admin123", "role": "admin"},
    "alice": {"email": "alice@nimbusbank.io", "password": "password123", "role": "customer"},
    "bob": {"email": "bob@nimbusbank.io", "password": "password123", "role": "customer"},
    "carol": {"email": "carol@nimbusbank.io", "password": "password123", "role": "customer"},
    "dave": {"email": "dave@nimbusbank.io", "password": "password123", "role": "customer"},
}

# Sequential seeded account ids (checking, savings) per user, ids 1-10.
SEEDED_ACCOUNTS = {"admin": (1, 2), "alice": (3, 4), "bob": (5, 6), "carol": (7, 8), "dave": (9, 10)}

# A tiny built-in sample password list. This is NOT a leaked-credentials dump —
# it is a handful of obvious guesses. Point scripts at your own file with a flag.
SAMPLE_PASSWORDS = [
    "password123",
    "admin123",
    "password",
    "123456",
    "letmein",
    "qwerty",
    "welcome1",
    "changeme",
]


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------

def make_client(**kwargs) -> httpx.Client:
    """A pre-configured httpx.Client pointed at the gateway with a short
    timeout and a small connection pool (laptop-safe concurrency)."""
    limits = httpx.Limits(max_connections=DEFAULT_CONCURRENCY * 2,
                          max_keepalive_connections=DEFAULT_CONCURRENCY)
    return httpx.Client(
        base_url=BASE_URL,
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        limits=limits,
        follow_redirects=True,
        **kwargs,
    )


class LoginError(RuntimeError):
    pass


def login(client: httpx.Client, email: str, password: str) -> tuple[str, dict]:
    """The two-step OTP login dance the whole app uses:

        POST /api/auth/login            -> {user_id, otp (echoed, LAB-ONLY), totp_enabled}
        POST /api/auth/login/otp/verify -> {access_token, user}

    Returns (access_token, user_dict). Raises LoginError on any failure.

    Note the LAB-ONLY convenience the /login response exposes: the 4-digit OTP
    is echoed straight back, so a bot never needs a second channel to complete
    the second factor. (A seeded user on the weak OTP path; TOTP users are not
    handled here.)
    """
    r1 = client.post("/api/auth/login", json={"email": email, "password": password})
    if r1.status_code != 200:
        raise LoginError(f"login step 1 failed for {email}: {r1.status_code} {r1.text[:120]}")
    d1 = r1.json()
    if d1.get("totp_enabled"):
        raise LoginError(f"{email} has TOTP enabled; this helper only drives the weak OTP path")
    r2 = client.post("/api/auth/login/otp/verify",
                     json={"user_id": d1["user_id"], "otp": d1["otp"]})
    if r2.status_code != 200:
        raise LoginError(f"otp verify failed for {email}: {r2.status_code} {r2.text[:120]}")
    d2 = r2.json()
    return d2["access_token"], d2.get("user", {})


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client: httpx.Client, email: str, password: str = "password123",
             full_name: str = "Throwaway User", ssn_last4: str = "4242") -> dict:
    """Register a fresh (instantly-verified) customer. Returns the response JSON."""
    r = client.post("/api/auth/register", json={
        "email": email, "full_name": full_name, "password": password, "ssn_last4": ssn_last4,
    })
    if r.status_code != 201:
        raise LoginError(f"register failed for {email}: {r.status_code} {r.text[:120]}")
    return r.json()
