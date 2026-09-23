import base64
import io
import random
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, Base, engine, get_db
from .models import OtpCode, User
from .obslog import install_request_logging
from .schemas import (
    LoginRequest,
    LoginResponse,
    OtpVerifyRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    TotpConfirmRequest,
    TotpEnrollResponse,
    TotpStatusResponse,
    TotpVerifyRequest,
    UserOut,
)
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    ensure_keys,
    get_current_user,
    get_jwks,
    hash_password,
    verify_password,
)
from .seed import seed_users

app = FastAPI(
    title="NimbusBank Auth Service",
    description="Owns user identity: registration, login, OTP second factor, and JWT/JWKS issuance for the rest of NimbusBank.",
    version="0.1.0",
)

# Only matters for local `npm run dev` against services running outside
# docker-compose. In docker-compose, the gateway makes frontend + all three
# services same-origin, so the browser never triggers a CORS check at all.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fire-and-forget request logging to admin-service's /ingest sink. Never blocks
# or fails a real request (see obslog.py); this service keeps working if admin
# is down.
install_request_logging(app, "auth")

REFRESH_COOKIE_NAME = "refresh_token"


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


def _set_refresh_cookie(response: Response, user_id: str) -> None:
    token = create_refresh_token(user_id=user_id)
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt_refresh_expire_days * 24 * 60 * 60,
    )


@app.on_event("startup")
async def on_startup() -> None:
    ensure_keys()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_users(session)


@app.get("/health", tags=["health"], summary="Liveness check")
async def health():
    return {"status": "ok"}


@app.get(
    "/.well-known/jwks.json",
    tags=["jwks"],
    summary="Public JWKS used by every other service (and F5 XC) to validate access tokens",
)
async def jwks():
    return get_jwks()


@app.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
    summary="Create a new customer account",
)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # INTENTIONALLY VULNERABLE: instant verified account creation with no
    # proof of identity — no email confirmation link, no CAPTCHA, no
    # per-IP/per-device signup limit. is_verified is True the moment this
    # request completes, which is exactly what makes fake-account farming
    # worth a bot's time (F5 XC Bot Protection: Fake Accounts).
    user = User(
        id=uuid.uuid4(),
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        ssn_last4=payload.ssn_last4,
        role="customer",
        is_verified=True,
    )
    db.add(user)
    await db.commit()

    return RegisterResponse(user=_to_user_out(user), message="Account created and verified.")


@app.post(
    "/login",
    response_model=LoginResponse,
    tags=["auth"],
    summary="Step 1 of login: verify email/password and issue an OTP challenge",
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))

    if not user:
        # INTENTIONALLY VULNERABLE: a distinct "no such user" response lets a
        # bot enumerate which emails have accounts before spending effort
        # guessing passwords for them (account enumeration).
        raise HTTPException(status_code=404, detail="No account with that email")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect password")

    # INTENTIONALLY VULNERABLE: no rate limiting, no failed-attempt counter,
    # no account lockout, no CAPTCHA challenge, no device/IP risk scoring on
    # this endpoint. A bot can retry it as fast as the network allows
    # (credential stuffing, F5 XC Bot Protection).
    code = f"{random.randint(0, 9999):04d}"
    otp = OtpCode(
        user_id=user.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes),
    )
    db.add(otp)
    await db.commit()

    return LoginResponse(
        otp_required=True,
        user_id=str(user.id),
        otp=code,
        totp_enabled=user.totp_enabled,
    )


@app.post(
    "/login/otp/verify",
    response_model=TokenResponse,
    tags=["auth"],
    summary="Step 2 of login: verify the OTP and issue an access token + refresh cookie",
)
async def verify_otp(payload: OtpVerifyRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        user_id = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # INTENTIONALLY VULNERABLE: no rate limit or attempt cap on OTP guesses.
    # A 4-digit code is only 10,000 possibilities — trivially bruteforceable
    # in a short demo run against this endpoint with nothing throttling it
    # (F5 XC Bot Protection: OTP Bruteforce).
    otp_row = await db.scalar(
        select(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.code == payload.otp, OtpCode.consumed.is_(False))
        .order_by(OtpCode.created_at.desc())
    )

    if not otp_row or otp_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    otp_row.consumed = True
    await db.commit()

    access_token = create_access_token(user_id=str(user.id), role=user.role, email=user.email)
    _set_refresh_cookie(response, str(user.id))

    return TokenResponse(access_token=access_token, user=_to_user_out(user))


@app.post(
    "/login/totp/verify",
    response_model=TokenResponse,
    tags=["auth"],
    summary="Step 2 (TOTP path): verify a 6-digit authenticator code and issue tokens",
)
async def verify_totp_login(
    payload: TotpVerifyRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    """The real-second-factor counterpart to /login/otp/verify. A user who
    enrolled an authenticator app (totp_enabled True) lands here instead of
    the weak echoed-OTP path, and on success gets the exact same access token
    + refresh cookie. The weak path is deliberately left fully intact for
    everyone who hasn't enrolled."""
    try:
        user_id = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="TOTP is not enabled for this user")

    if not pyotp.TOTP(user.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid authenticator code")

    access_token = create_access_token(user_id=str(user.id), role=user.role, email=user.email)
    _set_refresh_cookie(response, str(user.id))

    return TokenResponse(access_token=access_token, user=_to_user_out(user))


@app.get(
    "/totp/status",
    response_model=TotpStatusResponse,
    tags=["totp"],
    summary="Whether the current user has a confirmed authenticator app",
)
async def totp_status(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uuid.UUID(current["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return TotpStatusResponse(totp_enabled=user.totp_enabled)


@app.post(
    "/totp/enroll",
    response_model=TotpEnrollResponse,
    tags=["totp"],
    summary="Begin authenticator-app enrollment: generate a secret + QR (stays unconfirmed until /totp/confirm)",
)
async def totp_enroll(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uuid.UUID(current["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Reuse an existing (as-yet-unconfirmed) secret rather than churning it on
    # every page load; only generate a fresh one if none is stored.
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        # totp_enabled stays False until /totp/confirm proves possession.
        await db.commit()

    otpauth_uri = pyotp.totp.TOTP(user.totp_secret).provisioning_uri(
        name=user.email, issuer_name="NimbusBank"
    )

    img = qrcode.make(otpauth_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_png_base64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return TotpEnrollResponse(
        secret=user.totp_secret,
        otpauth_uri=otpauth_uri,
        qr_png_base64=qr_png_base64,
    )


@app.post(
    "/totp/confirm",
    tags=["totp"],
    summary="Confirm authenticator enrollment by submitting a valid 6-digit code",
)
async def totp_confirm(
    payload: TotpConfirmRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, uuid.UUID(current["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Start enrollment with /totp/enroll first")

    if not pyotp.TOTP(user.totp_secret).verify(payload.code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid authenticator code")

    user.totp_enabled = True
    await db.commit()
    return {"totp_enabled": True, "message": "Authenticator app enabled."}


@app.post(
    "/totp/disable",
    tags=["totp"],
    summary="Disable the authenticator app and clear its secret",
)
async def totp_disable(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uuid.UUID(current["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    user.totp_secret = None
    user.totp_enabled = False
    await db.commit()
    return {"totp_enabled": False, "message": "Authenticator app disabled."}


@app.post(
    "/token/refresh",
    response_model=RefreshResponse,
    tags=["auth"],
    summary="Exchange the httpOnly refresh cookie for a new access token",
)
async def refresh(refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME), db: AsyncSession = Depends(get_db)):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh cookie")

    payload = decode_token(refresh_token, expected_type="refresh")
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user_id=str(user.id), role=user.role, email=user.email)
    return RefreshResponse(access_token=access_token)


@app.get("/me", response_model=UserOut, tags=["auth"], summary="Current authenticated user's profile")
async def me(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uuid.UUID(current["user_id"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return _to_user_out(user)
