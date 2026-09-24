"""Happy path: every service exposes a healthy /health through the gateway."""

import pytest

SERVICES = ["auth", "accounts", "transfers", "kyc", "support", "cards", "admin"]


@pytest.mark.parametrize("svc", SERVICES)
def test_service_health_via_gateway(client, svc):
    r = client.get(f"/api/{svc}/health")
    assert r.status_code == 200, f"{svc} health returned {r.status_code}"
    assert r.json().get("status") == "ok"
