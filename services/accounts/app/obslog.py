import asyncio

import httpx
from jose import jwt

from .config import settings


def _extract_user_id(authorization: str | None) -> str | None:
    """Best-effort read of the bearer token's `sub`, purely as an observability
    label on the request log. Decoded WITHOUT signature or expiry verification
    on purpose — this is never an auth decision (real auth still happens in
    security.py's get_current_user) and it must never raise."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        return jwt.get_unverified_claims(token).get("sub")
    except Exception:
        return None


async def _post_log(payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(settings.admin_ingest_url, json=payload)
    except Exception:
        # Fire-and-forget: the admin sink being down, slow, or unreachable must
        # never surface to the real request. Swallow everything.
        pass


def install_request_logging(app, service_name: str) -> None:
    """Adds an HTTP middleware that, after the response is produced, fires a
    fire-and-forget log event to admin-service's /ingest sink. It NEVER blocks
    or fails the real request: the POST is scheduled with asyncio.create_task
    (not awaited) and every error is swallowed, so services keep working
    normally even when admin-service is down."""

    @app.middleware("http")
    async def _request_logger(request, call_next):
        response = await call_next(request)
        try:
            client_ip = request.headers.get("x-forwarded-for") or (
                request.client.host if request.client else None
            )
            payload = {
                "service": service_name,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "client_ip": client_ip,
                "user_id": _extract_user_id(request.headers.get("authorization")),
            }
            asyncio.create_task(_post_log(payload))
        except Exception:
            pass
        return response
