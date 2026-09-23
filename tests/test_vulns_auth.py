"""LOCK-IN: auth-service intentional gaps. Each test asserts a known-vulnerable
behavior still holds, so a future refactor that accidentally 'fixes' it fails
loudly. Docstrings map each test to its README INTENTIONALLY VULNERABLE row.
"""

import re

from conftest import SEEDED, auth_headers, jwt_claims, login, register_user, unique_email


def test_login_enumeration_unknown_email_404_vs_wrong_password_401(client):
    """README: 'no such user' 404 vs 'wrong password' 401 lets a bot enumerate
    which emails have accounts (Bot Protection: account enumeration)."""
    unknown = client.post("/api/auth/login",
                          json={"email": unique_email("nobody"), "password": "whatever12"})
    assert unknown.status_code == 404

    wrong = client.post("/api/auth/login",
                        json={"email": SEEDED["alice"]["email"], "password": "wrong-password"})
    assert wrong.status_code == 401
    # The two distinct codes are the whole enumeration oracle.
    assert unknown.status_code != wrong.status_code


def test_login_echoes_otp_in_body(client):
    """README (LAB-ONLY convenience, but locked in as behavior): /login returns
    the 4-digit OTP straight in the response body."""
    r = client.post("/api/auth/login",
                    json={"email": SEEDED["alice"]["email"], "password": SEEDED["alice"]["password"]})
    assert r.status_code == 200
    otp = r.json().get("otp")
    assert otp is not None and re.fullmatch(r"\d{4}", otp), f"OTP not echoed: {r.json()}"


def test_register_instant_verified_no_confirmation(client):
    """README: instant verified account with no email confirmation / CAPTCHA /
    signup limit (Bot Protection: Fake Accounts)."""
    reg = register_user(client)
    assert reg["user"]["is_verified"] is True


def test_patch_me_privilege_escalation_customer_to_admin(client):
    """README: mass assignment -> privilege escalation. PATCH /me applies any
    field with no allowlist, so a customer sets role:'admin' on their own row,
    and their next minted token carries role:'admin'."""
    reg = register_user(client)
    token, _ = login(client, reg["email"], reg["password"])
    h = auth_headers(token)

    assert client.get("/api/auth/me", headers=h).json()["role"] == "customer"

    patch = client.patch("/api/auth/me", headers=h, json={"role": "admin"})
    assert patch.status_code == 200
    assert patch.json()["role"] == "admin"

    # The row is genuinely admin now...
    assert client.get("/api/auth/me", headers=h).json()["role"] == "admin"
    # ...and the escalation propagates into a freshly minted access token.
    token2, _ = login(client, reg["email"], reg["password"])
    assert jwt_claims(token2)["role"] == "admin"


def test_change_password_without_current_password(client):
    """README: POST /password/change accepts current_password but never checks
    it (Broken Authentication / insufficient verification)."""
    reg = register_user(client)
    token, _ = login(client, reg["email"], reg["password"])

    r = client.post("/api/auth/password/change", headers=auth_headers(token),
                    json={"current_password": "totally-wrong", "new_password": "changed12345"})
    assert r.status_code == 200

    # The wrong current_password was ignored: the new password now works.
    new_token, _ = login(client, reg["email"], "changed12345")
    assert new_token


def test_password_reset_token_leaked_enumerates_and_resets(client):
    """README: /password/forgot echoes a short 6-digit token for a KNOWN email
    (200) but returns a distinct 404 for an unknown one (enumeration), and
    /password/reset accepts that token with no attempt cap."""
    reg = register_user(client)

    forgot = client.post("/api/auth/password/forgot", json={"email": reg["email"]})
    assert forgot.status_code == 200
    reset_token = forgot.json()["reset_token"]
    assert re.fullmatch(r"\d{6}", reset_token), f"token not a leaked 6-digit code: {reset_token}"

    unknown = client.post("/api/auth/password/forgot", json={"email": unique_email("nobody")})
    assert unknown.status_code == 404  # distinct response -> enumeration

    reset = client.post("/api/auth/password/reset",
                        json={"token": reset_token, "new_password": "brandnew12345"})
    assert reset.status_code == 200

    new_token, _ = login(client, reg["email"], "brandnew12345")
    assert new_token
