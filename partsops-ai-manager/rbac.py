"""
PartsOps AI Manager v3 — Role-Based Access Control (RBAC) & Multi-tenancy.

Security rule:
- Zero-trust tenant boundary: tenant_id is extracted from secure signed claims when available.
- Master API token remains supported for backward-compatible/admin tools.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, List, Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlmodel import Session, select

from database import get_session
from models import Membership, User
from settings import settings

ALLOWED_ROLES = {"admin", "manager", "finance", "platform_admin"}
DEFAULT_TENANT = "default"
DEFAULT_ROLE = "manager"


@dataclass(frozen=True)
class CurrentPrincipal:
    tenant_id: str
    role: str
    authenticated: bool
    auth_mode: str  # oidc|token|dev
    subject: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool = False


def _get_api_token() -> Optional[str]:
    token = os.getenv("PARTSOPS_API_TOKEN", "").strip()
    return token or None


def _parse_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _normalize_role(role: Optional[str]) -> str:
    normalized = (role or DEFAULT_ROLE).lower()
    if normalized not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail=f"Некорректная роль: {normalized}")
    return normalized


def create_signed_token(tenant_id: str, role: str, secret: str) -> str:
    """Generate a secure signed token encoding tenant and role claims."""
    payload = f"{tenant_id}:{role}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_signed_token(token: str, secret: str) -> Optional[tuple[str, str]]:
    """Decode and verify signed claims token."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        tenant_id, role, signature = parts
        payload = f"{tenant_id}:{role}"
        expected_sig = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(signature, expected_sig):
            return tenant_id, role
        return None
    except Exception:
        return None


def _claim_value(claims: dict[str, Any], dotted_path: str) -> Any:
    value: Any = claims
    for segment in dotted_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(segment)
    return value


def _claim_role(claims: dict[str, Any]) -> str:
    raw_role = _claim_value(claims, settings.OIDC_ROLE_CLAIM)
    if isinstance(raw_role, list):
        for role in raw_role:
            if isinstance(role, str) and role.lower() in ALLOWED_ROLES:
                return _normalize_role(role)
        raise HTTPException(
            status_code=403, detail="OIDC token has no supported PartsOps role"
        )
    if isinstance(raw_role, str):
        return _normalize_role(raw_role)
    raise HTTPException(
        status_code=403, detail="OIDC token is missing a PartsOps role claim"
    )


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str):
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError("PyJWT[crypto] is required for OIDC authentication") from exc
    return jwt.PyJWKClient(jwks_url, cache_keys=True)


def _decode_oidc_token(token: str) -> dict[str, Any]:
    """Verify Keycloak-compatible JWT signature and required standard claims."""
    try:
        import jwt
        from jwt import InvalidTokenError
    except ImportError as exc:
        raise RuntimeError("PyJWT[crypto] is required for OIDC authentication") from exc

    try:
        signing_key = _jwks_client(settings.OIDC_JWKS_URL).get_signing_key_from_jwt(
            token
        )
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.OIDC_AUDIENCE,
            issuer=settings.OIDC_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired OIDC access token"
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail="OIDC token verification failed"
        ) from exc


def _principal_from_oidc(token: str) -> CurrentPrincipal:
    claims = _decode_oidc_token(token)
    tenant_id = _claim_value(claims, settings.OIDC_TENANT_CLAIM)
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise HTTPException(
            status_code=403, detail="OIDC token is missing organization claim"
        )
    return CurrentPrincipal(
        tenant_id=tenant_id.strip(),
        role=_claim_role(claims),
        authenticated=True,
        auth_mode="oidc",
        subject=str(claims["sub"]) if claims.get("sub") is not None else None,
        email=str(claims["email"]).strip().lower() if isinstance(claims.get("email"), str) else None,
        email_verified=claims.get("email_verified") is True,
    )


def get_current_principal(
    x_tenant_id: Optional[str] = Header(default=None),
    x_user_role: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    tenant_id: Optional[str] = Query(default=None),
    user_role: Optional[str] = Query(default=None),
    api_token: Optional[str] = Query(default=None, alias="token"),
) -> CurrentPrincipal:
    """
    Resolve request principal with zero-trust boundary check.
    """
    provided_tenant = x_tenant_id or tenant_id or DEFAULT_TENANT
    provided_role = x_user_role or user_role or DEFAULT_ROLE
    provided_token = _parse_bearer_token(authorization) or api_token

    if settings.AUTH_MODE == "oidc":
        if not provided_token:
            raise HTTPException(
                status_code=401, detail="OIDC Authorization: Bearer token is required"
            )
        if (
            settings.ALLOW_MASTER_TOKEN_PLATFORM_ADMIN
            and _get_api_token()
            and hmac.compare_digest(provided_token, _get_api_token() or "")
        ):
            return CurrentPrincipal(
                tenant_id=DEFAULT_TENANT,
                role="platform_admin",
                authenticated=True,
                auth_mode="token",
            )
        return _principal_from_oidc(provided_token)

    token_configured = _get_api_token() is not None

    if token_configured:
        if not provided_token:
            # Keep unauthenticated reads inside default tenant and lowest operational role.
            return CurrentPrincipal(
                tenant_id=DEFAULT_TENANT,
                role=DEFAULT_ROLE,
                authenticated=False,
                auth_mode="token",
            )

        secret = _get_api_token()

        # 1. First priority: verify as a secure signed token
        claims = verify_signed_token(provided_token, secret)
        if claims:
            tenant_id_claim, role_claim = claims
            return CurrentPrincipal(
                tenant_id=tenant_id_claim,
                role=_normalize_role(role_claim),
                authenticated=True,
                auth_mode="token",
            )

        # 2. Second priority: master token fallback (backward compatibility)
        if hmac.compare_digest(provided_token, secret):
            return CurrentPrincipal(
                tenant_id=provided_tenant,
                role=_normalize_role(provided_role),
                authenticated=True,
                auth_mode="token",
            )

        raise HTTPException(status_code=403, detail="Неверная подпись токена")

    # Local dev mode (no token configured on server)
    return CurrentPrincipal(
        tenant_id=provided_tenant,
        role=_normalize_role(provided_role),
        authenticated=False,
        auth_mode="dev",
    )


def require_privileged_access(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> bool:
    """Require authentication when PARTSOPS_API_TOKEN is configured."""
    if principal.auth_mode == "token" and not principal.authenticated:
        raise HTTPException(
            status_code=401, detail="Требуется Authorization: Bearer ***"
        )
    return True


def _require_active_oidc_membership(session: Session, principal: CurrentPrincipal) -> None:
    if principal.auth_mode != "oidc":
        return
    if not principal.subject:
        raise HTTPException(status_code=403, detail="OIDC token is missing subject")

    user = session.exec(
        select(User).where(User.external_subject == principal.subject)
    ).first()
    if user is None and principal.email and principal.email_verified:
        # A managed beta invitation is activated only after the verified IdP
        # email proves ownership; arbitrary OIDC claims cannot create users.
        user = session.exec(select(User).where(User.email == principal.email)).first()
        if user and user.status == "invited":
            user.external_subject = principal.subject
            user.identity_provider = "oidc"
            user.status = "active"
            session.add(user)
            session.flush()
    if user is None or user.status != "active":
        raise HTTPException(status_code=403, detail="OIDC user is not an active PartsOps member")

    membership = session.exec(
        select(Membership).where(
            Membership.organization_id == principal.tenant_id,
            Membership.user_id == user.user_id,
        )
    ).first()
    if membership is None or membership.status not in {"active", "invited"}:
        raise HTTPException(status_code=403, detail="OIDC user has no active organization membership")
    if membership.status == "invited":
        membership.status = "active"
        session.add(membership)
        session.flush()
    if membership.role != principal.role:
        raise HTTPException(status_code=403, detail="OIDC role does not match organization membership")


def get_privileged_tenant(
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_session),
) -> str:
    """Return the safe tenant for the current request."""
    # Ensure unauthenticated token access is blocked for privileged endpoints
    if principal.auth_mode == "token" and not principal.authenticated:
        raise HTTPException(
            status_code=401, detail="Требуется Authorization: Bearer ***"
        )
    _require_active_oidc_membership(session, principal)
    return principal.tenant_id


def get_current_tenant(
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_session),
) -> str:
    return get_privileged_tenant(principal, session)


def get_current_role(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> str:
    if principal.auth_mode == "token" and not principal.authenticated:
        raise HTTPException(
            status_code=401, detail="Требуется Authorization: Bearer ***"
        )
    return principal.role


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(
        self, principal: CurrentPrincipal = Depends(get_current_principal)
    ) -> str:
        if principal.auth_mode == "token" and not principal.authenticated:
            raise HTTPException(
                status_code=401, detail="Требуется Authorization: Bearer ***"
            )
        if principal.role not in self.allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Операция не разрешена для роли: {principal.role}. Требуется одна из: {self.allowed_roles}",
            )
        return principal.role
