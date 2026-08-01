"""Commercial SaaS foundation for managed QuoteOps beta."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from models import (
    IntegrationConnection,
    Membership,
    OnboardingState,
    Organization,
    PartRequest,
    Subscription,
    UsageEvent,
    User,
)

VALID_SUBSCRIPTION_STATUSES = {"trial", "active", "past_due", "suspended", "canceled"}
VALID_USAGE_EVENT = "valid_rfq_position"

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "beta_trial": {"positions": 100, "feeds": 5, "users": 3},
    "start": {"positions": 500, "feeds": 5, "users": 3},
    "team": {"positions": 2000, "feeds": 25, "users": 10},
}

ORGANIZATION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,62}$")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _limits_for_plan(plan_code: str) -> dict[str, int]:
    return PLAN_LIMITS.get(plan_code, PLAN_LIMITS["start"])


def ensure_organization(
    session: Session, organization_id: str, *, display_name: Optional[str] = None
) -> Organization:
    organization = session.exec(
        select(Organization).where(Organization.organization_id == organization_id)
    ).first()
    if organization:
        return organization

    now = _now()
    organization = Organization(
        organization_id=organization_id,
        display_name=display_name or organization_id,
        created_at=now,
        updated_at=now,
    )
    session.add(organization)
    session.commit()
    session.refresh(organization)
    ensure_onboarding_state(session, organization_id)
    ensure_subscription(session, organization_id)
    return organization


def ensure_onboarding_state(session: Session, organization_id: str) -> OnboardingState:
    state = session.exec(
        select(OnboardingState).where(
            OnboardingState.organization_id == organization_id
        )
    ).first()
    if state:
        return state

    now = _now()
    state = OnboardingState(
        organization_id=organization_id,
        checklist_json=_json_dump(
            [
                "import_supplier_feed",
                "configure_pricing_policy",
                "process_first_rfq",
                "export_first_quote",
            ]
        ),
        completed_steps_json=_json_dump([]),
        created_at=now,
        updated_at=now,
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def ensure_subscription(session: Session, organization_id: str) -> Subscription:
    subscription = session.exec(
        select(Subscription).where(Subscription.organization_id == organization_id)
    ).first()
    if subscription:
        return subscription

    now = _now()
    limits = _limits_for_plan("beta_trial")
    subscription = Subscription(
        organization_id=organization_id,
        status="trial",
        plan_code="beta_trial",
        position_limit=limits["positions"],
        supplier_feed_limit=limits["feeds"],
        user_limit=limits["users"],
        trial_started_at=now,
        current_period_start=now,
        current_period_end=now + timedelta(days=14),
        created_at=now,
        updated_at=now,
    )
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return subscription


def get_organization_bundle(session: Session, organization_id: str) -> dict[str, Any]:
    organization = ensure_organization(session, organization_id)
    subscription = ensure_subscription(session, organization_id)
    onboarding = ensure_onboarding_state(session, organization_id)
    integrations = session.exec(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id
        )
    ).all()
    return {
        "organization": organization,
        "subscription": subscription,
        "onboarding": onboarding,
        "integrations": integrations,
    }


def mark_onboarding_step(
    session: Session, organization_id: str, step: str
) -> OnboardingState:
    state = ensure_onboarding_state(session, organization_id)
    try:
        completed = json.loads(state.completed_steps_json or "[]")
    except json.JSONDecodeError:
        completed = []
    if step not in completed:
        completed.append(step)
    now = _now()
    state.completed_steps_json = _json_dump(completed)
    state.status = (
        "completed"
        if set(completed) >= set(json.loads(state.checklist_json or "[]"))
        else "in_progress"
    )
    state.first_rfq_processed_at = state.first_rfq_processed_at or (
        now if step == "process_first_rfq" else None
    )
    state.updated_at = now
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def invite_member(
    session: Session,
    *,
    organization_id: str,
    email: str,
    role: str,
    invited_by: str,
) -> dict[str, Any]:
    ensure_organization(session, organization_id)
    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(status_code=422, detail="Valid email is required")
    if role not in {"admin", "manager", "finance"}:
        raise HTTPException(status_code=422, detail="Unsupported member role")

    existing_user = session.exec(
        select(User).where(User.email == normalized_email)
    ).first()
    membership = (
        session.exec(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == existing_user.user_id,
            )
        ).first()
        if existing_user
        else None
    )
    if membership is None:
        # Serialize new invitations for one organization in PostgreSQL so two
        # concurrent requests cannot both pass the seat-limit check.
        ensure_subscription(session, organization_id)
        subscription = session.exec(
            select(Subscription)
            .where(Subscription.organization_id == organization_id)
            .with_for_update()
        ).one()
        member_count = session.exec(
            select(func.count()).select_from(Membership).where(
                Membership.organization_id == organization_id,
                Membership.status.in_(["active", "invited"]),
            )
        ).one()
        if member_count >= subscription.user_limit:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "USER_QUOTA_EXHAUSTED",
                    "message": "User limit reached for the current subscription",
                    "user_limit": subscription.user_limit,
                },
            )

    now = _now()
    user = existing_user or User(
        user_id=f"user_{uuid.uuid4().hex[:12]}",
        email=normalized_email,
        display_name=normalized_email.split("@")[0],
        status="invited",
        created_at=now,
        updated_at=now,
    )
    if not existing_user:
        session.add(user)
        session.commit()
        session.refresh(user)

    if membership is None:
        membership = Membership(
            organization_id=organization_id,
            user_id=user.user_id,
            role=role,
            status="invited",
            invited_by=invited_by,
            invited_at=now,
            created_at=now,
            updated_at=now,
        )
    else:
        membership.role = role
        membership.status = (
            "invited" if membership.status == "disabled" else membership.status
        )
        membership.invited_by = membership.invited_by or invited_by
        membership.invited_at = membership.invited_at or now
        membership.updated_at = now
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return {"user": user, "membership": membership}


def provision_organization(
    session: Session,
    *,
    organization_id: str,
    display_name: str,
    owner_email: str,
    provisioned_by: str,
) -> dict[str, Any]:
    """Provision a managed-beta tenant and its first administrator invitation.

    This is intentionally platform-only: an OIDC claim alone must never create
    an organization. Repeating the request is safe and returns the existing
    organization and invitation.
    """
    normalized_id = organization_id.strip().lower()
    if not ORGANIZATION_ID_PATTERN.fullmatch(normalized_id):
        raise HTTPException(
            status_code=422,
            detail="organization_id must be a 3-63 character lowercase slug",
        )
    normalized_name = display_name.strip()
    if not normalized_name:
        raise HTTPException(status_code=422, detail="display_name is required")

    organization = ensure_organization(
        session, normalized_id, display_name=normalized_name
    )
    invitation = invite_member(
        session,
        organization_id=normalized_id,
        email=owner_email,
        role="admin",
        invited_by=provisioned_by,
    )
    return {"organization": organization, **invitation}


def list_members(session: Session, organization_id: str) -> list[dict[str, Any]]:
    memberships = session.exec(
        select(Membership).where(Membership.organization_id == organization_id)
    ).all()
    result = []
    for membership in memberships:
        user = session.exec(
            select(User).where(User.user_id == membership.user_id)
        ).first()
        if user:
            result.append(
                {
                    "user_id": user.user_id,
                    "email": user.email,
                    "display_name": user.display_name,
                    "role": membership.role,
                    "status": membership.status,
                }
            )
    return result


def activate_subscription(
    session: Session,
    *,
    organization_id: str,
    plan_code: str,
    external_invoice_number: str,
    external_invoice_date: str,
) -> Subscription:
    ensure_organization(session, organization_id)
    if plan_code not in PLAN_LIMITS:
        raise HTTPException(status_code=422, detail="Unsupported plan_code")
    invoice_number = external_invoice_number.strip()
    invoice_date = external_invoice_date.strip()
    if not invoice_number or not invoice_date:
        raise HTTPException(
            status_code=422, detail="external invoice number and date are required"
        )

    subscription = ensure_subscription(session, organization_id)
    limits = _limits_for_plan(plan_code)
    now = _now()
    subscription.status = "active"
    subscription.plan_code = plan_code
    subscription.position_limit = limits["positions"]
    subscription.supplier_feed_limit = limits["feeds"]
    subscription.user_limit = limits["users"]
    subscription.external_invoice_number = invoice_number
    subscription.external_invoice_date = invoice_date
    subscription.activated_at = subscription.activated_at or now
    subscription.suspended_at = None
    subscription.current_period_start = subscription.current_period_start or now
    subscription.current_period_end = now + timedelta(days=30)
    subscription.updated_at = now
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return subscription


def suspend_subscription(
    session: Session, *, organization_id: str, reason: str = ""
) -> Subscription:
    ensure_organization(session, organization_id)
    subscription = ensure_subscription(session, organization_id)
    now = _now()
    subscription.status = "suspended"
    subscription.suspended_at = now
    subscription.updated_at = now
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return subscription


def get_usage_summary(session: Session, organization_id: str) -> dict[str, Any]:
    ensure_organization(session, organization_id)
    subscription = ensure_subscription(session, organization_id)
    events = session.exec(
        select(UsageEvent).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.event_type == VALID_USAGE_EVENT,
        )
    ).all()
    used_positions = sum(max(0, event.quantity) for event in events)
    remaining = max(0, subscription.position_limit - used_positions)
    return {
        "organization_id": organization_id,
        "plan_code": subscription.plan_code,
        "subscription_status": subscription.status,
        "position_limit": subscription.position_limit,
        "positions_used": used_positions,
        "positions_remaining": remaining,
        "usage_event_count": len(events),
        "current_period_start": subscription.current_period_start.isoformat()
        if subscription.current_period_start
        else None,
        "current_period_end": subscription.current_period_end.isoformat()
        if subscription.current_period_end
        else None,
    }


def count_valid_request_positions(request: PartRequest) -> int:
    try:
        parts = json.loads(request.parts_json or "[]")
    except json.JSONDecodeError:
        return 0
    if not isinstance(parts, list):
        return 0
    return sum(1 for item in parts if isinstance(item, dict) and any(item.values()))


def assert_pipeline_quota_available(
    session: Session, *, organization_id: str, request: PartRequest
) -> int:
    ensure_organization(session, organization_id)
    subscription = ensure_subscription(session, organization_id)
    now = _now()
    if subscription.status not in {"trial", "active"}:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "SUBSCRIPTION_INACTIVE",
                "subscription_status": subscription.status,
            },
        )
    if (
        subscription.status == "trial"
        and subscription.current_period_end
        and subscription.current_period_end < now
    ):
        raise HTTPException(
            status_code=402,
            detail={
                "code": "TRIAL_EXPIRED",
                "current_period_end": subscription.current_period_end.isoformat(),
            },
        )

    idempotency_key = usage_idempotency_key(request.request_id)
    existing = session.exec(
        select(UsageEvent).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.idempotency_key == idempotency_key,
        )
    ).first()
    if existing:
        return 0

    position_count = count_valid_request_positions(request)
    used = get_usage_summary(session, organization_id)["positions_used"]
    if used + position_count > subscription.position_limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "POSITION_QUOTA_EXHAUSTED",
                "position_limit": subscription.position_limit,
                "positions_used": used,
                "positions_requested": position_count,
            },
        )
    return position_count


def reserve_pipeline_usage(
    session: Session, *, organization_id: str, request: PartRequest, run_id: str
) -> int:
    """Reserve billable positions atomically with pipeline enqueueing.

    PostgreSQL locks the subscription row so concurrent requests for one organization
    cannot both observe the same remaining quota. The caller owns the transaction.
    """
    ensure_organization(session, organization_id)
    subscription = session.exec(
        select(Subscription)
        .where(Subscription.organization_id == organization_id)
        .with_for_update()
    ).one()
    now = _now()
    if subscription.status not in {"trial", "active"}:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "SUBSCRIPTION_INACTIVE",
                "subscription_status": subscription.status,
            },
        )
    if (
        subscription.status == "trial"
        and subscription.current_period_end
        and subscription.current_period_end < now
    ):
        raise HTTPException(
            status_code=402,
            detail={
                "code": "TRIAL_EXPIRED",
                "current_period_end": subscription.current_period_end.isoformat(),
            },
        )
    key = usage_idempotency_key(request.request_id)
    existing = session.exec(
        select(UsageEvent).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.idempotency_key == key,
        )
    ).first()
    if existing:
        return 0
    quantity = count_valid_request_positions(request)
    used = session.exec(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.event_type == VALID_USAGE_EVENT,
        )
    ).one()
    if int(used or 0) + quantity > subscription.position_limit:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "POSITION_QUOTA_EXHAUSTED",
                "position_limit": subscription.position_limit,
                "positions_used": int(used or 0),
                "positions_requested": quantity,
            },
        )
    if quantity:
        session.add(
            UsageEvent(
                organization_id=organization_id,
                request_id=request.request_id,
                event_type=VALID_USAGE_EVENT,
                quantity=quantity,
                idempotency_key=key,
                source="pipeline",
                metadata_json=_json_dump({"run_id": run_id}),
                occurred_at=now,
            )
        )
        session.flush()
    return quantity


def usage_idempotency_key(request_id: str) -> str:
    return f"pipeline:{request_id}:valid-rfq-positions"


def record_pipeline_usage(
    session: Session,
    *,
    organization_id: str,
    request_id: str,
    quantity: int,
    run_id: str,
) -> Optional[UsageEvent]:
    if quantity <= 0:
        return None
    idempotency_key = usage_idempotency_key(request_id)
    existing = session.exec(
        select(UsageEvent).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.idempotency_key == idempotency_key,
        )
    ).first()
    if existing:
        return existing
    event = UsageEvent(
        organization_id=organization_id,
        request_id=request_id,
        event_type=VALID_USAGE_EVENT,
        quantity=quantity,
        idempotency_key=idempotency_key,
        source="pipeline",
        metadata_json=_json_dump({"run_id": run_id}),
        occurred_at=_now(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
