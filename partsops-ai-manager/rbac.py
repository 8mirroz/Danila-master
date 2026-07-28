"""
PartsOps AI Manager v3 — Role-Based Access Control (RBAC) & Multi-tenancy.

Security rule:
- Zero-trust tenant boundary: tenant_id is extracted from secure signed claims when available.
- Master API token remains supported for backward-compatible/admin tools.
"""
from __future__ import annotations
import hmac
import hashlib
import os
from dataclasses import dataclass
from typing import Optional, List
from fastapi import Header, HTTPException, Depends, Query

ALLOWED_ROLES = {"admin", "manager", "finance"}
DEFAULT_TENANT = "default"
DEFAULT_ROLE = "manager"

@dataclass(frozen=True)
class CurrentPrincipal:
    tenant_id: str
    role: str
    authenticated: bool
    auth_mode: str  # token|dev


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
        expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_sig):
            return tenant_id, role
        return None
    except Exception:
        return None


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
        raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer ***")
    return True


def get_privileged_tenant(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> str:
    """Return the safe tenant for the current request."""
    # Ensure unauthenticated token access is blocked for privileged endpoints
    if principal.auth_mode == "token" and not principal.authenticated:
        raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer ***")
    return principal.tenant_id


def get_current_tenant(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> str:
    return principal.tenant_id


def get_current_role(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> str:
    if principal.auth_mode == "token" and not principal.authenticated:
        raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer ***")
    return principal.role


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, principal: CurrentPrincipal = Depends(get_current_principal)) -> str:
        if principal.auth_mode == "token" and not principal.authenticated:
            raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer ***")
        if principal.role not in self.allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Операция не разрешена для роли: {principal.role}. Требуется одна из: {self.allowed_roles}",
            )
        return principal.role
