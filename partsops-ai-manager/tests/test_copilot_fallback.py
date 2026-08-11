"""Copilot local-fallback / prefer-local health and mode tests."""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import main
import routers.copilot as copilot_router
from database import get_session
from rbac import create_signed_token, _get_api_token
from services.hermes_transport import HermesTransportError


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    main.app.dependency_overrides[get_session] = get_session_override
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()


def make_auth_headers(tenant_id: str = "default", role: str = "manager") -> dict:
    secret = _get_api_token()
    headers = {"X-Tenant-ID": tenant_id, "X-User-Role": role}
    if secret:
        token = create_signed_token(tenant_id, role, secret)
        headers["Authorization"] = f"Bearer {token}"
    return headers


def test_health_prefer_local_mode_is_local(client: TestClient, monkeypatch):
    """COPILOT_PREFER_LOCAL=1 → health reports mode=local (Hermes not required)."""
    monkeypatch.setenv("COPILOT_PREFER_LOCAL", "1")
    monkeypatch.setenv("COPILOT_LOCAL_FALLBACK", "1")

    class FakeHermesTransport:
        """Should not be required for prefer-local path when key is weak;
        still mock so a strong key never hits the network.
        """

        async def capabilities(self):
            raise HermesTransportError("unreachable", code="HERMES_UNAVAILABLE")

    monkeypatch.setattr(copilot_router, "HermesTransport", FakeHermesTransport)

    response = client.get("/api/copilot/health", headers=make_auth_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "local"
    assert data["prefer_local"] is True
    assert data["local_fallback"] is True
    assert data["status"] == "degraded"
    assert data.get("model") == "partsops-local"
    assert "local_grounded_reply" in (data.get("capabilities") or [])


def test_check_hermes_health_async_prefer_local_unit(monkeypatch):
    """Direct unit check of check_hermes_health_async without HTTP stack."""
    monkeypatch.setenv("COPILOT_PREFER_LOCAL", "1")
    monkeypatch.setenv("COPILOT_LOCAL_FALLBACK", "1")

    class FakeHermesTransport:
        async def capabilities(self):
            return {"model": "should-not-matter", "features": {}}

    monkeypatch.setattr(copilot_router, "HermesTransport", FakeHermesTransport)

    health = asyncio.run(copilot_router.check_hermes_health_async())
    assert health["mode"] == "local"
    assert health["prefer_local"] is True
    assert health["status"] == "degraded"
