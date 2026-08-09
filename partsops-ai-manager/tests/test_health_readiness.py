"""Health live vs ready probes."""
import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("PARTSOPS_API_TOKEN", "test-token")

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_live_has_db_only_shape():
    res = client.get("/health/live")
    assert res.status_code == 200
    body = res.json()
    assert body.get("probe") == "live"
    assert "checks" in body
    assert "database" in body["checks"]
    # Live probe must not require ERP key
    assert "erp" not in body["checks"]


def test_health_alias_is_live():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body.get("probe") == "live"
    assert body.get("status") in {"healthy", "unhealthy", "degraded"}


def test_health_ready_includes_erp_key_without_secrets():
    res = client.get("/health/ready")
    assert res.status_code == 200
    body = res.json()
    assert body.get("probe") == "ready"
    checks = body.get("checks") or {}
    assert "database" in checks
    assert "erp" in checks
    assert "storage" in checks
    erp = checks["erp"]
    # Never leak credentials
    blob = str(erp).lower()
    assert "api_key" not in blob
    assert "secret" not in blob
