from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, select

from database import engine
from main import app
from models import Membership, PartRequest, RequestState, Subscription, UsageEvent, User
from rbac import CurrentPrincipal, get_privileged_tenant
from services.saas import mark_onboarding_step


client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-saas", "X-User-Role": "admin"}
PLATFORM_HEADERS = {
    "Authorization": "Bearer test-token",
    "X-Tenant-ID": "platform",
    "X-User-Role": "platform_admin",
}


@pytest.fixture(autouse=True)
def clean_database():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def _seed_request(request_id: str = "REQ-SAAS-1", *, tenant_id: str = "tenant-saas", parts: int = 1) -> None:
    payload = [{"name": f"Фильтр {idx}", "quantity": 1} for idx in range(parts)]
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id=request_id,
                tenant_id=tenant_id,
                source="manual",
                status=RequestState.PART_EXTRACTION,
                customer_name="ООО SaaS",
                parts_json=json.dumps(payload, ensure_ascii=False),
            )
        )
        session.commit()


def test_current_organization_bootstraps_trial_subscription():
    response = client.get("/api/organizations/current", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["organization"]["organization_id"] == "tenant-saas"
    assert payload["subscription"]["status"] == "trial"
    assert payload["subscription"]["position_limit"] == 100
    assert payload["onboarding"]["status"] == "not_started"

    usage = client.get("/api/billing/usage", headers=AUTH_HEADERS)
    assert usage.status_code == 200
    assert usage.json()["positions_used"] == 0


def test_session_is_derived_from_the_authenticated_principal():
    response = client.get("/api/session", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["auth_mode"] == "token"
    assert payload["subject"] is None
    assert payload["role"] == "admin"
    assert payload["tenant_id"] == "tenant-saas"
    assert payload["permissions"]["can_approve_pricing"] is True
    assert payload["organization"]["organization_id"] == "tenant-saas"


def test_oidc_tenant_access_requires_active_membership(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "oidc")
    principal = CurrentPrincipal(
        tenant_id="tenant-saas",
        role="manager",
        authenticated=True,
        auth_mode="oidc",
        subject="keycloak-subject-1",
    )
    with Session(engine) as session:
        session.add(
            User(
                user_id="user-oidc-1",
                email="buyer@example.com",
                external_subject="keycloak-subject-1",
                identity_provider="oidc",
                status="active",
            )
        )
        session.add(
            Membership(
                organization_id="tenant-saas",
                user_id="user-oidc-1",
                role="manager",
                status="active",
            )
        )
        session.commit()
        assert get_privileged_tenant(principal, session) == "tenant-saas"


def test_oidc_tenant_access_rejects_user_without_membership(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "oidc")
    principal = CurrentPrincipal(
        tenant_id="tenant-saas",
        role="manager",
        authenticated=True,
        auth_mode="oidc",
        subject="keycloak-subject-orphan",
    )
    with Session(engine) as session:
        session.add(
            User(
                user_id="user-oidc-orphan",
                email="orphan@example.com",
                external_subject="keycloak-subject-orphan",
                identity_provider="oidc",
                status="active",
            )
        )
        session.commit()
        with pytest.raises(Exception, match="organization membership"):
            get_privileged_tenant(principal, session)


def test_verified_oidc_email_activates_existing_invitation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "oidc")
    principal = CurrentPrincipal(
        tenant_id="tenant-saas",
        role="manager",
        authenticated=True,
        auth_mode="oidc",
        subject="keycloak-invited-subject",
        email="buyer@example.com",
        email_verified=True,
    )
    with Session(engine) as session:
        session.add(User(user_id="user-invited", email="buyer@example.com", status="invited"))
        session.add(
            Membership(
                organization_id="tenant-saas",
                user_id="user-invited",
                role="manager",
                status="invited",
            )
        )
        session.commit()
        assert get_privileged_tenant(principal, session) == "tenant-saas"
        user = session.exec(select(User).where(User.user_id == "user-invited")).one()
        membership = session.exec(select(Membership).where(Membership.user_id == "user-invited")).one()
        assert user.external_subject == "keycloak-invited-subject"
        assert user.status == "active"
        assert membership.status == "active"


def test_onboarding_step_is_idempotent_and_tracks_first_rfq():
    with Session(engine) as session:
        state = mark_onboarding_step(session, "tenant-saas", "process_first_rfq")
        repeated = mark_onboarding_step(session, "tenant-saas", "process_first_rfq")
        assert state.status == "in_progress"
        assert repeated.first_rfq_processed_at is not None
        assert json.loads(repeated.completed_steps_json) == ["process_first_rfq"]


def test_admin_can_invite_member_without_sending_email():
    response = client.post(
        "/api/organizations/current/invitations",
        json={"email": "buyer@example.com", "role": "manager"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"] == "buyer@example.com"
    assert payload["membership"]["status"] == "invited"
    assert payload["delivery"] == {"status": "not_sent", "mode": "manual_beta"}
    members = client.get("/api/organizations/current/members", headers=AUTH_HEADERS)
    assert members.status_code == 200
    assert members.json() == [{"user_id": payload["user"]["user_id"], "email": "buyer@example.com", "display_name": "buyer", "role": "manager", "status": "invited"}]


def test_platform_admin_activates_subscription_idempotently():
    first = client.post(
        "/api/platform/subscriptions/tenant-saas/activate",
        json={
            "plan_code": "team",
            "external_invoice_number": "INV-42",
            "external_invoice_date": "2026-07-31",
        },
        headers=PLATFORM_HEADERS,
    )
    second = client.post(
        "/api/platform/subscriptions/tenant-saas/activate",
        json={
            "plan_code": "team",
            "external_invoice_number": "INV-42",
            "external_invoice_date": "2026-07-31",
        },
        headers=PLATFORM_HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "active"
    assert second.json()["position_limit"] == 2000


def test_pipeline_run_records_valid_position_usage_once():
    _seed_request(parts=2)

    first = client.post(
        "/api/requests/REQ-SAAS-1/pipeline-runs",
        json={"requested_lane": "matching"},
        headers=AUTH_HEADERS,
    )
    second = client.post(
        "/api/requests/REQ-SAAS-1/pipeline-runs",
        json={"requested_lane": "matching"},
        headers=AUTH_HEADERS,
    )

    assert first.status_code == 202
    assert second.status_code == 200
    usage = client.get("/api/billing/usage", headers=AUTH_HEADERS)
    assert usage.json()["positions_used"] == 2
    with Session(engine) as session:
        events = session.exec(select(UsageEvent)).all()
    assert len(events) == 1


def test_pipeline_run_blocks_when_position_quota_is_exhausted():
    _seed_request(parts=2)
    with Session(engine) as session:
        session.add(
            Subscription(
                organization_id="tenant-saas",
                status="active",
                plan_code="start",
                position_limit=1,
                supplier_feed_limit=5,
                user_limit=3,
            )
        )
        session.commit()

    response = client.post(
        "/api/requests/REQ-SAAS-1/pipeline-runs",
        json={"requested_lane": "matching"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "POSITION_QUOTA_EXHAUSTED"
