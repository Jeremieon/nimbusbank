"""Happy path: registration, two-step OTP login, /me, token refresh, and the
real TOTP (authenticator-app) enroll/confirm/login flow."""

import httpx

from conftest import BASE_URL, auth_headers, login, register_user

import pyotp


def test_register_returns_verified_customer(client):
    reg = register_user(client)
    assert reg["user"]["is_verified"] is True
    assert reg["user"]["role"] == "customer"
    assert reg["user"]["email"] == reg["email"]


def test_login_otp_then_me(client):
    reg = register_user(client)
    token, user = login(client, reg["email"], reg["password"])
    assert token
    r = client.get("/api/auth/me", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == reg["email"]
    assert body["role"] == "customer"


def test_token_refresh(client):
    # Use a dedicated client so the httpOnly refresh cookie set at login is
    # unambiguous (the shared session client is reused by many logins).
    reg = register_user(client)
    with httpx.Client(base_url=BASE_URL, timeout=30.0, follow_redirects=True) as c:
        r1 = c.post("/api/auth/login", json={"email": reg["email"], "password": reg["password"]})
        d1 = r1.json()
        c.post("/api/auth/login/otp/verify", json={"user_id": d1["user_id"], "otp": d1["otp"]})
        r = c.post("/api/auth/token/refresh")
        assert r.status_code == 200
        assert r.json().get("access_token")


def test_totp_enroll_confirm_and_login(client):
    reg = register_user(client)
    token, _ = login(client, reg["email"], reg["password"])
    h = auth_headers(token)

    enroll = client.post("/api/auth/totp/enroll", headers=h)
    assert enroll.status_code == 200
    secret = enroll.json()["secret"]
    assert secret

    confirm = client.post("/api/auth/totp/confirm", headers=h,
                          json={"code": pyotp.TOTP(secret).now()})
    assert confirm.status_code == 200
    assert confirm.json()["totp_enabled"] is True

    # Login now reports totp_enabled and routes to the TOTP verify path.
    r1 = client.post("/api/auth/login", json={"email": reg["email"], "password": reg["password"]})
    assert r1.status_code == 200
    assert r1.json()["totp_enabled"] is True
    user_id = r1.json()["user_id"]

    r2 = client.post("/api/auth/login/totp/verify",
                     json={"user_id": user_id, "code": pyotp.TOTP(secret).now()})
    assert r2.status_code == 200
    assert r2.json().get("access_token")
