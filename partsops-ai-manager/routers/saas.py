from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from database import get_session
from rbac import (
    CurrentPrincipal,
    RoleChecker,
    get_current_principal,
    get_privileged_tenant,
)
from services.request_service import RequestService
from services.saas import (
    activate_subscription,
    get_organization_bundle,
    get_usage_summary,
    invite_member,
    list_members,
    provision_organization,
    suspend_subscription,
)

router = APIRouter(prefix="/api", tags=["SaaS"])
require_platform_admin = RoleChecker(["platform_admin"])


class InvitationPayload(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    role: str = Field(default="manager", pattern="^(admin|manager|finance)$")


class ActivateSubscriptionPayload(BaseModel):
    plan_code: str = Field(pattern="^(start|team|beta_trial)$")
    external_invoice_number: str = Field(min_length=1, max_length=128)
    external_invoice_date: str = Field(min_length=1, max_length=32)


class SuspendSubscriptionPayload(BaseModel):
    reason: Optional[str] = Field(default="", max_length=500)


class ProvisionOrganizationPayload(BaseModel):
    organization_id: str = Field(min_length=3, max_length=63)
    display_name: str = Field(min_length=1, max_length=200)
    owner_email: str = Field(min_length=3, max_length=254)


def _model(model: Any) -> dict[str, Any]:
    columns = getattr(getattr(model, "__table__", None), "columns", [])
    if columns:
        data = {column.name: getattr(model, column.name) for column in columns}
    else:
        data = model.model_dump(mode="json")
    return {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in data.items()
    }


def _subscription_response(subscription: Any) -> dict[str, Any]:
    data = _model(subscription)
    data["billing_mode"] = "manual_invoice"
    return data


@router.get("/session")
def get_session_info(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Return the server-derived operator session for the commercial cockpit."""
    bundle = get_organization_bundle(session, organization_id)
    return {
        "tenant_id": organization_id,
        "authenticated": principal.authenticated,
        "auth_mode": principal.auth_mode,
        "subject": principal.subject,
        "role": principal.role,
        "permissions": RequestService._role_permissions(principal.role),
        "organization": _model(bundle["organization"]),
    }


@router.get("/organizations/current")
def get_current_organization(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    bundle = get_organization_bundle(session, organization_id)
    return {
        "organization": _model(bundle["organization"]),
        "subscription": _subscription_response(bundle["subscription"]),
        "onboarding": _model(bundle["onboarding"]),
        "integrations": [_model(integration) for integration in bundle["integrations"]],
    }


@router.post("/organizations/current/invitations", status_code=201)
def create_invitation(
    payload: InvitationPayload,
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    if principal.role not in {"admin", "platform_admin"}:
        raise HTTPException(
            status_code=403, detail="Only organization admins can invite users"
        )
    result = invite_member(
        session,
        organization_id=organization_id,
        email=str(payload.email),
        role=payload.role,
        invited_by=f"operator:{principal.role}",
    )
    return {
        "user": _model(result["user"]),
        "membership": _model(result["membership"]),
        "delivery": {"status": "not_sent", "mode": "manual_beta"},
    }


@router.get("/organizations/current/members")
def get_current_members(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    return list_members(session, organization_id)


@router.get("/billing/subscription")
def get_current_subscription(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    bundle = get_organization_bundle(session, organization_id)
    return _subscription_response(bundle["subscription"])


@router.get("/billing/usage")
def get_current_usage(
    session: Session = Depends(get_session),
    organization_id: str = Depends(get_privileged_tenant),
):
    return get_usage_summary(session, organization_id)


@router.post("/platform/subscriptions/{organization_id}/activate")
def activate_organization_subscription(
    organization_id: str,
    payload: ActivateSubscriptionPayload,
    session: Session = Depends(get_session),
    _: str = Depends(require_platform_admin),
):
    subscription = activate_subscription(
        session,
        organization_id=organization_id,
        plan_code=payload.plan_code,
        external_invoice_number=payload.external_invoice_number,
        external_invoice_date=payload.external_invoice_date,
    )
    return _subscription_response(subscription)


@router.post("/platform/organizations", status_code=201)
def provision_managed_beta_organization(
    payload: ProvisionOrganizationPayload,
    session: Session = Depends(get_session),
    _: str = Depends(require_platform_admin),
):
    result = provision_organization(
        session,
        organization_id=payload.organization_id,
        display_name=payload.display_name,
        owner_email=payload.owner_email,
        provisioned_by="platform_admin",
    )
    return {
        "organization": _model(result["organization"]),
        "subscription": _subscription_response(
            get_organization_bundle(session, result["organization"].organization_id)[
                "subscription"
            ]
        ),
        "owner": _model(result["user"]),
        "membership": _model(result["membership"]),
        "delivery": {"status": "not_sent", "mode": "manual_beta"},
    }


@router.post("/platform/subscriptions/{organization_id}/suspend")
def suspend_organization_subscription(
    organization_id: str,
    payload: SuspendSubscriptionPayload,
    session: Session = Depends(get_session),
    _: str = Depends(require_platform_admin),
):
    subscription = suspend_subscription(
        session, organization_id=organization_id, reason=payload.reason or ""
    )
    return _subscription_response(subscription)
