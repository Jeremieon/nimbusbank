import httpx
from fastapi import Header, HTTPException
from jose import JWTError, jwt

from .config import settings

# Cached in memory after the first successful fetch. Simple process-lifetime
# cache is enough for a lab: auth-service's key only changes if its /keys
# volume is wiped, at which point restarting this service picks up the new
# JWKS.
_jwks_cache: dict | None = None


async def fetch_jwks() -> dict:
    global _jwks_cache
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(settings.auth_jwks_url)
        resp.raise_for_status()
    _jwks_cache = resp.json()
    return _jwks_cache


def _find_key(kid: str | None) -> dict | None:
    if not _jwks_cache:
        return None
    keys = _jwks_cache.get("keys", [])
    if kid:
        for key in keys:
            if key.get("kid") == kid:
                return key
    return keys[0] if keys else None


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """Validates the bearer access token's signature against auth-service's
    JWKS — but INCONSISTENTLY with the rest of NimbusBank.

    INTENTIONALLY VULNERABLE: the jwt.decode call below passes
    options={"verify_exp": False}, so this service checks the RS256 *signature*
    but NOT the `exp` claim. An access token that expired long ago is still
    accepted here, even though auth-service, accounts-service, and
    transfers-service all call jwt.decode WITHOUT that option and therefore
    reject expired tokens correctly (compare accounts/app/security.py, which is
    otherwise line-for-line identical to this file). This is the "inconsistent
    JWT validation across microservices" gap — a stolen or leaked token keeps
    working against support long after it should have died (API Security:
    Broken Authentication / improper JWT validation).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    key = _find_key(header.get("kid"))
    if key is None:
        await fetch_jwks()
        key = _find_key(header.get("kid"))
    if key is None:
        raise HTTPException(status_code=401, detail="Unable to verify token (no matching signing key)")

    try:
        # INTENTIONALLY VULNERABLE: verify_exp=False disables expiry checking.
        # Every other service in this repo omits this option (default True) and
        # rejects expired tokens.
        payload = jwt.decode(token, key, algorithms=["RS256"], options={"verify_exp": False})
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"user_id": payload["sub"], "role": payload.get("role"), "email": payload.get("email")}
