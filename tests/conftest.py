"""Shared fixtures and helpers for the NimbusBank integration test suite.

These are black-box tests: they drive the LIVE stack through the Nginx gateway
(default http://localhost:80, overridable with $BASE_URL) exactly the way the
React SPA and the README curl snippets do. Nothing is imported from the
services in-process — the point is to exercise the real gateway path routing,
the real JWKS validation, and the real cross-service calls.

Gateway path convention (see frontend/src/api.js and gateway/nginx.conf):
  - auth:      /api/auth/<route>            (routes are bare)
  - accounts:  /api/accounts/accounts/...   (service routes start with /accounts)
  - transfers: /api/transfers/transfers/...
  - kyc:       /api/kyc/kyc/...
  - support:   /api/support/tickets/...     (service routes start with /tickets)
  - cards:     /api/cards/cards/...
  - admin:     /api/admin/admin/...
  - health:    /api/<svc>/health            (single segment for every service)
"""

import base64
import json
import os
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("BASE_URL", "http://localhost:80").rstrip("/")

# --------------------------------------------------------------------------
# Seeded data constants — mirror each service's app/seed.py exactly.
# --------------------------------------------------------------------------

# Fixed seeded user UUIDs (services/auth/app/seed.py::SEED_USERS).
SEEDED = {
    "admin": {"email": "admin@nimbusbank.io", "password": "admin123",
              "user_id": "11111111-1111-1111-1111-111111111111", "role": "admin"},
    "alice": {"email": "alice@nimbusbank.io", "password": "password123",
              "user_id": "22222222-2222-2222-2222-222222222222", "role": "customer"},
    "bob": {"email": "bob@nimbusbank.io", "password": "password123",
            "user_id": "33333333-3333-3333-3333-333333333333", "role": "customer"},
    "carol": {"email": "carol@nimbusbank.io", "password": "password123",
              "user_id": "44444444-4444-4444-4444-444444444444", "role": "customer"},
    "dave": {"email": "dave@nimbusbank.io", "password": "password123",
             "user_id": "55555555-5555-5555-5555-555555555555", "role": "customer"},
}

# Sequential seeded account ids (services/accounts/app/seed.py): checking, savings.
ACCOUNTS = {"admin": (1, 2), "alice": (3, 4), "bob": (5, 6), "carol": (7, 8), "dave": (9, 10)}

# Seeded cards (services/cards/app/seed.py), ids 1-4:
#   1 alice (acct 3, active), 2 bob (acct 5, frozen), 3 carol (acct 7, active), 4 dave (acct 9, frozen)
# Seeded KYC docs (services/kyc/app/seed.py), ids 1-3:
#   1 alice id_card (approved), 2 alice proof_of_address (pending), 3 bob id_card (pending)
# Seeded support tickets (services/support/app/seed.py), ids 1-2:
#   1 alice "Card declined at checkout", 2 bob "How do I enable the authenticator app?"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def make_client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=True)


def unique_email(prefix: str = "throwaway") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@nimbusbank.io"


def register_user(client, email=None, password="password123",
                  full_name="Throwaway User", ssn_last4="4242") -> dict:
    """Register a fresh customer through the gateway. Returns a dict with the
    email/password used and the created user object."""
    email = email or unique_email()
    resp = client.post("/api/auth/register", json={
        "email": email, "full_name": full_name, "password": password, "ssn_last4": ssn_last4,
    })
    assert resp.status_code == 201, f"register failed: {resp.status_code} {resp.text}"
    data = resp.json()
    return {"email": email, "password": password, "user": data["user"], "user_id": data["user"]["id"]}


def login(client, email, password):
    """The two-step OTP login dance the whole app uses:
        POST /login              -> {user_id, otp (echoed, LAB-ONLY), totp_enabled}
        POST /login/otp/verify   -> {access_token, user}
    Returns (access_token, user_dict)."""
    r1 = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r1.status_code == 200, f"login step 1 failed: {r1.status_code} {r1.text}"
    d1 = r1.json()
    r2 = client.post("/api/auth/login/otp/verify", json={"user_id": d1["user_id"], "otp": d1["otp"]})
    assert r2.status_code == 200, f"login otp verify failed: {r2.status_code} {r2.text}"
    d2 = r2.json()
    return d2["access_token"], d2["user"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def jwt_claims(token: str) -> dict:
    """Decode a JWT's claims WITHOUT verifying the signature. Test-only helper
    used to prove a claim's value (e.g. that role escalated to 'admin')."""
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client():
    c = make_client()
    yield c
    c.close()


def _seeded_fixture(client, who):
    token, user = login(client, SEEDED[who]["email"], SEEDED[who]["password"])
    return {"token": token, "user": user, "user_id": user["id"], "headers": auth_headers(token)}


@pytest.fixture(scope="session")
def alice(client):
    """Session-scoped token/headers for the seeded customer alice."""
    return _seeded_fixture(client, "alice")


@pytest.fixture(scope="session")
def bob(client):
    """Session-scoped token/headers for the seeded customer bob."""
    return _seeded_fixture(client, "bob")


@pytest.fixture
def throwaway(client):
    """A freshly-registered, logged-in throwaway customer — used for mutating
    happy-path and vuln tests so seeded data stays clean and reruns are safe."""
    reg = register_user(client)
    token, user = login(client, reg["email"], reg["password"])
    return {**reg, "token": token, "user": user, "headers": auth_headers(token)}
