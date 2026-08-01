"""Commercial QuoteOps metrics derived from durable tenant data."""

from __future__ import annotations

import json

from sqlmodel import Session, select

from models import GoldenSample, PartRequest, RequestState

READY_STATES = {
    RequestState.PRICING_REVIEW,
    RequestState.APPROVED,
    RequestState.INVOICE_DRAFTED,
    RequestState.ERP_SYNCING,
    RequestState.ERP_SYNCED,
}


def _positions(request: PartRequest) -> int:
    try:
        return sum(
            1
            for item in json.loads(request.parts_json or "[]")
            if isinstance(item, dict) and item.get("name")
        )
    except json.JSONDecodeError:
        return 0


def _corrected_positions(sample: GoldenSample | None, position_count: int) -> tuple[int, bool]:
    """Return corrected positions and whether legacy attribution was absent."""
    if sample is None:
        return 0, False
    if sample.corrected_position_indexes_json is None:
        return position_count, True
    try:
        indexes = json.loads(sample.corrected_position_indexes_json)
    except json.JSONDecodeError:
        return position_count, True
    if not isinstance(indexes, list) or any(not isinstance(index, int) or index < 0 or index >= position_count for index in indexes):
        return position_count, True
    return len(set(indexes)), False


def quoteops_metrics(session: Session, organization_id: str) -> dict[str, int | float]:
    requests = session.exec(
        select(PartRequest).where(PartRequest.tenant_id == organization_id)
    ).all()
    total = automated = ready_requests = margin_violations = pending_approvals = 0
    manually_corrected = unattributed_manual_corrections = 0
    for request in requests:
        count = _positions(request)
        total += count
        if request.status in READY_STATES:
            ready_requests += 1
            sample = session.exec(
                select(GoldenSample).where(
                    GoldenSample.request_id == request.request_id,
                    GoldenSample.tenant_id == organization_id,
                )
            ).first()
            corrected, unattributed = _corrected_positions(sample, count)
            manually_corrected += corrected
            unattributed_manual_corrections += int(unattributed)
            automated += max(0, count - corrected)
        if request.margin_policy_passed is False:
            margin_violations += 1
        if request.status == RequestState.PRICING_REVIEW:
            pending_approvals += 1
    return {
        "organization_id": organization_id,
        "valid_positions": total,
        "automated_positions": automated,
        "manually_corrected_positions": manually_corrected,
        "unattributed_manual_correction_requests": unattributed_manual_corrections,
        "automation_rate": round((automated / total) * 100, 1) if total else 0.0,
        "ready_for_approval_requests": ready_requests,
        "margin_violations": margin_violations,
        "pending_approvals": pending_approvals,
    }
