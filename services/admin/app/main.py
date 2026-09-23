from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AsyncSessionLocal, Base, engine, get_db
from .models import RequestLog
from .schemas import OverviewResponse, RequestLogOut, TrafficResponse
from .security import get_current_user  # require_admin defined but deliberately unused

app = FastAPI(
    title="NimbusBank Admin Service",
    description="Central request-log sink and ops-traffic API. Ingests fire-and-forget log events from every other service and exposes an observability view over its own request_logs table. It never reads any other service's database.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: admin-service does NOT install the request-logging middleware itself —
# doing so would make it POST a log event to its own /ingest for every request
# (including that POST), an infinite loop. It is the sink, not a source.


def _to_out(row: RequestLog) -> RequestLogOut:
    return RequestLogOut(
        id=row.id,
        service=row.service,
        method=row.method,
        path=row.path,
        status_code=row.status_code,
        client_ip=row.client_ip,
        user_id=row.user_id,
        ts=row.ts,
    )


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["health"], summary="Liveness check")
async def health():
    return {"status": "ok"}


@app.post("/ingest", tags=["ingest"], summary="Internal request-log sink (service-to-service, no auth)")
async def ingest(request: Request, db: AsyncSession = Depends(get_db)):
    # No auth: this is an internal sink called service-to-service over the
    # docker network, not through the gateway. It must stay fast and never 500
    # on a malformed event — a bad log event should be dropped silently, never
    # turned into an error that could ripple back to a caller.
    try:
        data = await request.json()
    except Exception:
        return {"ok": False}

    if not isinstance(data, dict):
        return {"ok": False}

    try:
        row = RequestLog(
            service=str(data.get("service") or "unknown")[:40],
            method=str(data.get("method") or "")[:10],
            path=str(data.get("path") or "")[:2048],
            status_code=int(data.get("status_code") or 0),
            client_ip=(str(data["client_ip"])[:64] if data.get("client_ip") else None),
            user_id=(str(data["user_id"])[:64] if data.get("user_id") else None),
        )
        db.add(row)
        await db.commit()
    except Exception:
        return {"ok": False}

    return {"ok": True}


@app.get(
    "/admin/traffic",
    response_model=TrafficResponse,
    tags=["admin"],
    summary="Recent request logs plus simple aggregates (open observability view)",
)
async def traffic(db: AsyncSession = Depends(get_db)):
    # LAB-ONLY: this observability view has NO authentication, so you can watch
    # cross-service traffic during testing without first building an admin
    # login. This is a convenience for the lab (same open-observability stance
    # noted in the README), not a claim that dashboards should be unauthenticated
    # — it's not part of the INTENTIONALLY VULNERABLE table.
    recent_rows = (
        (await db.execute(select(RequestLog).order_by(RequestLog.id.desc()).limit(200)))
        .scalars()
        .all()
    )
    recent = [_to_out(r) for r in recent_rows]

    total = await db.scalar(select(func.count()).select_from(RequestLog)) or 0

    per_service: dict[str, int] = {}
    for svc, cnt in (
        await db.execute(select(RequestLog.service, func.count()).group_by(RequestLog.service))
    ).all():
        per_service[svc] = cnt

    # Status buckets 2xx/4xx/5xx (plus a catch-all "other") computed in SQL.
    per_status_bucket = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}
    for code, cnt in (
        await db.execute(select(RequestLog.status_code, func.count()).group_by(RequestLog.status_code))
    ).all():
        if 200 <= code < 300:
            per_status_bucket["2xx"] += cnt
        elif 300 <= code < 400:
            per_status_bucket["3xx"] += cnt
        elif 400 <= code < 500:
            per_status_bucket["4xx"] += cnt
        elif 500 <= code < 600:
            per_status_bucket["5xx"] += cnt
        else:
            per_status_bucket["other"] += cnt

    top_rows = (
        await db.execute(
            select(RequestLog.path, func.count().label("c"))
            .group_by(RequestLog.path)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    top_paths = [{"path": p, "count": c} for p, c in top_rows]

    return TrafficResponse(
        recent=recent,
        total=total,
        per_service=per_service,
        per_status_bucket=per_status_bucket,
        top_paths=top_paths,
    )


@app.get(
    "/admin/overview",
    response_model=OverviewResponse,
    tags=["admin"],
    summary="Staff traffic overview (should be admin-only)",
)
async def overview(current: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # INTENTIONALLY VULNERABLE: this is meant to be a staff-only overview, but
    # the dependency is `get_current_user`, not `require_admin` (defined right
    # in this service's security.py and simply never applied here). Any
    # authenticated *customer* reaches it — Broken Function Level Authorization
    # (API Security: BFLA). Aggregates are computed only from admin-service's
    # own request_logs table; it never reads another service's database.
    total = await db.scalar(select(func.count()).select_from(RequestLog)) or 0

    unique_users = (
        await db.scalar(
            select(func.count(func.distinct(RequestLog.user_id))).where(RequestLog.user_id.isnot(None))
        )
    ) or 0

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    last_hour = (
        await db.scalar(select(func.count()).select_from(RequestLog).where(RequestLog.ts >= one_hour_ago))
    ) or 0

    return OverviewResponse(
        total_requests=total,
        unique_users=unique_users,
        requests_last_hour=last_hour,
    )
