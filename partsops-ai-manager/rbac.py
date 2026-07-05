"""
PartsOps AI Manager v3 — Role-Based Access Control (RBAC) & Multi-tenancy.

Security rule:
- X-Tenant-ID and X-User-Role are trusted only with a valid Bearer token.
- When PARTSOPS_API_TOKEN is not configured, the app runs in local-dev mode.
"""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Optional, List

from fastapi import Header, HTTPException, Depends


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


def _is_authenticated(authorization: Optional[str]) -> bool:
    expected = _get_api_token()
    provided = _parse_bearer_token(authorization)
    return bool(expected and provided and hmac.compare_digest(provided, expected))


def _normalize_role(role: Optional[str]) -> str:
    normalized = (role or DEFAULT_ROLE).lower()
    if normalized not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail=f"Некорректная роль: {normalized}")
    return normalized


def get_current_principal(
    x_tenant_id: Optional[str] = Header(default=DEFAULT_TENANT),
    x_user_role: Optional[str] = Header(default=DEFAULT_ROLE),
    authorization: Optional[str] = Header(default=None),
) -> CurrentPrincipal:
    """
    Resolve request principal.

    In production-like mode (PARTSOPS_API_TOKEN set), tenant and role headers are
    accepted only after token validation. This prevents trivial tenant/role spoofing.
    In local dev/test mode (no token), headers remain usable for demos.
    """
    token_configured = _get_api_token() is not None
    authenticated = _is_authenticated(authorization)

    if token_configured and not authenticated:
        # Keep unauthenticated reads inside default tenant and lowest operational role.
        return CurrentPrincipal(
            tenant_id=DEFAULT_TENANT,
            role=DEFAULT_ROLE,
            authenticated=False,
            auth_mode="token",
        )

    return CurrentPrincipal(
        tenant_id=(x_tenant_id or DEFAULT_TENANT),
        role=_normalize_role(x_user_role),
        authenticated=authenticated,
        auth_mode="token" if token_configured else "dev",
    )


def require_privileged_access(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> bool:
    """Require authentication when PARTSOPS_API_TOKEN is configured."""
    if principal.auth_mode == "token" and not principal.authenticated:
        raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer <PARTS...KEN>")
    return True


def get_privileged_tenant(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> str:
    """Return the safe tenant for the current request."""
    return principal.tenant_id


def get_current_tenant(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> str:
    return principal.tenant_id


def get_current_role(
    principal: CurrentPrincipal = Depends(get_current_principal),
) -> str:
    if principal.auth_mode == "token" and not principal.authenticated:
        raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer <PARTS...KEN>")
    return principal.role


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, principal: CurrentPrincipal = Depends(get_current_principal)) -> str:
        if principal.auth_mode == "token" and not principal.authenticated:
            raise HTTPException(status_code=401, detail="Требуется Authorization: Bearer <PARTS...KEN>")
        if principal.role not in self.allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Операция не разрешена для роли: {principal.role}. Требуется одна из: {self.allowed_roles}",
            )
        return principal.role
