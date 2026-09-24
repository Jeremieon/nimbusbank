from datetime import datetime

from pydantic import BaseModel


class RequestLogOut(BaseModel):
    id: int
    service: str
    method: str
    path: str
    status_code: int
    client_ip: str | None
    user_id: str | None
    ts: datetime


class TrafficResponse(BaseModel):
    recent: list[RequestLogOut]
    total: int
    per_service: dict[str, int]
    per_status_bucket: dict[str, int]
    top_paths: list[dict]


class OverviewResponse(BaseModel):
    total_requests: int
    unique_users: int
    requests_last_hour: int
