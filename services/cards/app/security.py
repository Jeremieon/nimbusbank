import httpx
from fastapi import Depends, Header, HTTPException
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
    """Validates the bearer access token's signature AND expiry against
    auth-service's JWKS — the correct check (this is deliberately NOT the
    broken verify_exp=False variant support-service uses).

    Note what this does NOT do: it only proves the token is genuine and
    unexpired. It says nothing about whether the caller is *allowed* to touch
    the resource they're requesting — see the BOLA gaps in main.py.
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
        payload = jwt.decode(token, key, algorithms=["RS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"user_id": payload["sub"], "role": payload.get("role"), "email": payload.get("email")}


async def require_admin(current: dict = Depends(get_current_user)) -> dict:
    """A real role check, defined and ready to use — and then, deliberately,
    never applied to any route in this service's main.py. Same "defined-but-not-
    applied" pattern as transfers-service: read it next to the card routes and
    the missing guard is obvious (API Security: Broken Function Level
    Authorization)."""
    if current.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current
