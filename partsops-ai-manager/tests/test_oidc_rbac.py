"""OIDC auth policy tests: production claims, not browser headers, own the tenant boundary."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import rbac
import routers.observability as observability
from rbac import CurrentPrincipal, get_current_principal


def _configure_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "oidc")
    monkeypatch.setenv("PARTSOPS_OIDC_ISSUER", "https://sso.example.test/realms/partsops")
    monkeypatch.setenv("PARTSOPS_OIDC_AUDIENCE", "partsops-api")
    monkeypatch.delenv("PARTSOPS_ALLOW_MASTER_TOKEN_PLATFORM_ADMIN", raising=False)


def test_oidc_claims_ignore_spoofed_browser_headers(monkeypatch: pytest.MonkeyPatch):
    _configure_oidc(monkeypatch)
    monkeypatch.setattr(
        rbac,
        "_decode_oidc_token",
        lambda _: {"organization_id": "tenant-from-claim", "realm_access": {"roles": ["manager"]}},
    )

    principal = get_current_principal(
        authorization="Bearer signed-access-token",
        x_tenant_id="attacker-tenant",
        x_user_role="platform_admin",
    )

    assert principal.tenant_id == "tenant-from-claim"
    assert principal.role == "manager"
    assert principal.auth_mode == "oidc"


def test_oidc_verifies_keycloak_style_rsa_access_token(monkeypatch: pytest.MonkeyPatch):
    """Exercise the real decoder, including issuer/audience/signature validation."""
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from datetime import datetime, timedelta, timezone

    _configure_oidc(monkeypatch)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class SigningKey:
        key = private_key.public_key()

    class JwksClient:
        def get_signing_key_from_jwt(self, token: str):
            return SigningKey()

    monkeypatch.setattr(rbac, "_jwks_client", lambda _: JwksClient())
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "keycloak-user-id",
            "iss": "https://sso.example.test/realms/partsops",
            "aud": "partsops-api",
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "organization_id": "verified-tenant",
            "realm_access": {"roles": ["manager"]},
        },
        private_key,
        algorithm="RS256",
    )

    principal = get_current_principal(authorization=f"Bearer {token}")

    assert principal.tenant_id == "verified-tenant"
    assert principal.role == "manager"


def test_oidc_rejects_missing_organization_claim(monkeypatch: pytest.MonkeyPatch):
    _configure_oidc(monkeypatch)
    monkeypatch.setattr(rbac, "_decode_oidc_token", lambda _: {"realm_access": {"roles": ["manager"]}})

    with pytest.raises(HTTPException, match="organization claim") as error:
        get_current_principal(authorization="Bearer signed-access-token")
    assert error.value.status_code == 403


def test_oidc_rejects_missing_or_unsupported_role(monkeypatch: pytest.MonkeyPatch):
    _configure_oidc(monkeypatch)
    monkeypatch.setattr(
        rbac,
        "_decode_oidc_token",
        lambda _: {"organization_id": "tenant-a", "realm_access": {"roles": ["viewer"]}},
    )

    with pytest.raises(HTTPException, match="supported PartsOps role") as error:
        get_current_principal(authorization="Bearer signed-access-token")
    assert error.value.status_code == 403


def test_oidc_requires_bearer_token(monkeypatch: pytest.MonkeyPatch):
    _configure_oidc(monkeypatch)

    with pytest.raises(HTTPException, match="OIDC Authorization") as error:
        get_current_principal(authorization=None, api_token=None)
    assert error.value.status_code == 401


def test_oidc_sse_derives_tenant_from_verified_bearer_claim(monkeypatch: pytest.MonkeyPatch):
    _configure_oidc(monkeypatch)
    captured: dict[str, str | None] = {}

    def verified_principal(*, authorization: str | None = None, **_: object) -> CurrentPrincipal:
        captured["authorization"] = authorization
        return CurrentPrincipal(
            tenant_id="tenant-from-verified-sse-token",
            role="manager",
            authenticated=True,
            auth_mode="oidc",
        )

    scope = {"type": "http", "method": "GET", "path": "/api/events/stream", "headers": [(b"authorization", b"Bearer access-token")]}
    monkeypatch.setattr(observability, "get_current_principal", verified_principal)
    monkeypatch.setattr(observability, "_require_active_oidc_membership", lambda *_: None)
    response = asyncio.run(observability.sse_stream(Request(scope)))

    assert response.media_type == "text/event-stream"
    assert captured["authorization"] == "Bearer access-token"


def test_production_oidc_configuration_requires_issuer_and_audience(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "oidc")
    monkeypatch.delenv("PARTSOPS_OIDC_ISSUER", raising=False)
    monkeypatch.delenv("PARTSOPS_OIDC_AUDIENCE", raising=False)

    with pytest.raises(RuntimeError, match="PARTSOPS_OIDC_ISSUER"):
        rbac.settings.validate_auth_configuration()


def test_production_cannot_downgrade_to_legacy_auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PARTSOPS_ENV", "production")
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "legacy")

    with pytest.raises(RuntimeError, match="required when PARTSOPS_ENV=production"):
        rbac.settings.validate_auth_configuration()


def test_auth_mode_must_be_known(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "disabled")

    with pytest.raises(RuntimeError, match="must be either legacy or oidc"):
        rbac.settings.validate_auth_configuration()


def test_legacy_master_token_still_supports_local_tooling(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PARTSOPS_AUTH_MODE", "legacy")
    monkeypatch.setenv("PARTSOPS_API_TOKEN", "local-master")

    principal = get_current_principal(
        authorization="Bearer local-master",
        x_tenant_id="local-tenant",
        x_user_role="admin",
    )

    assert principal.tenant_id == "local-tenant"
    assert principal.role == "admin"
