"""Executes safe Contract Operations agent roles from the automation runner."""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import HTTPException
from sqlmodel import Session, select

from app.automation.context import AutomationContext
from app.automation.events import append_request_event
from models import ContractExport, EventType, PartRequest, RequestState
from services.contract_operations import evaluate_policy, export_contract, get_control_plane

logger = logging.getLogger("automation.jobs.contract_orchestrate")


def _role(name: str, status: str, detail: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"role": name, "status": status, "detail": detail, "result": result or {}}


def _request_ids(session: Session, context: AutomationContext) -> list[str]:
    if context.request_id:
        return [context.request_id]
    payload_ids = context.payload.get("request_ids") or []
    if payload_ids:
        return [str(item) for item in payload_ids]
    rows = session.exec(select(PartRequest).where(
        PartRequest.tenant_id == context.tenant_id,
        PartRequest.source == "contract_operations",
    )).all()
    return [row.request_id for row in rows]


def _export_exists(session: Session, request_id: str, tenant_id: str) -> bool:
    return bool(session.exec(select(ContractExport).where(
        ContractExport.request_id == request_id,
        ContractExport.tenant_id == tenant_id,
        ContractExport.diff_status == "validated",
    )).first())


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    request_ids = _request_ids(session, context)
    if context.dry_run:
        return {"ok": True, "dry_run": True, "requests": len(request_ids), "roles": []}

    processed: list[dict[str, Any]] = []
    for request_id in request_ids:
        req = session.exec(select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == context.tenant_id,
        )).first()
        if not req:
            processed.append({"request_id": request_id, "ok": False, "roles": [_role("contract_lookup", "blocked", "request not found")]})
            continue

        roles: list[dict[str, Any]] = []
        control = get_control_plane(session, request_id, context.tenant_id)
        roles.append(_role("contract_audit_agent", "completed", "control-plane audit and coverage synchronized",
                           {"requirements": len(control["requirements"]), "open_gaps": control["metrics"]["quality"]["open_gaps"]}))

        workflow_stage = control["workflow"]["current_stage"]
        if control["metrics"]["evidence"]["required_source_coverage_percent"] == 100.0:
            roles.append(_role("market_evidence_agent", "completed", "all required marketplace sources are present"))
        else:
            roles.append(_role("market_evidence_agent", "blocked", "price evidence is incomplete"))

        if req.status == RequestState.OFFER_RANKING:
            try:
                result = evaluate_policy(session, request_id, context.tenant_id, context.actor_id)
                roles.append(_role("pricing_policy_agent", "completed", "policy evaluation executed", result))
            except HTTPException as exc:
                roles.append(_role("pricing_policy_agent", "blocked", str(exc.detail)))
        elif req.status in {RequestState.PRICING_REVIEW, RequestState.READY_FOR_APPROVAL, RequestState.APPROVED,
                            RequestState.ERP_SYNCING, RequestState.INVOICE_DRAFTED, RequestState.SENT_TO_CLIENT,
                            RequestState.PAID, RequestState.PURCHASE_ORDERED, RequestState.FULFILLED,
                            RequestState.CLOSED}:
            roles.append(_role("pricing_policy_agent", "completed", f"already past policy stage: {req.status}"))
        else:
            roles.append(_role("pricing_policy_agent", "blocked", f"requires OFFER_RANKING, got {req.status}"))

        session.refresh(req)
        if context.payload.get("generate_export") is True:
            if req.status == RequestState.APPROVED:
                try:
                    result = export_contract(session, request_id, context.tenant_id, context.actor_id)
                    roles.append(_role("client_export_agent", "completed", "validated client/internal export generated",
                                       {"export_id": result["export_id"], "registry_hash": result["registry_hash"]}))
                except HTTPException as exc:
                    roles.append(_role("client_export_agent", "blocked", str(exc.detail)))
            elif _export_exists(session, request_id, context.tenant_id):
                roles.append(_role("client_export_agent", "completed", "validated export already exists"))
            else:
                roles.append(_role("client_export_agent", "blocked", f"requires APPROVED request, got {req.status}"))
        else:
            roles.append(_role("client_export_agent", "waiting", "generate_export flag is false"))

        control = get_control_plane(session, request_id, context.tenant_id)
        roles.append(_role("workflow_supervisor_agent", "completed", "workflow state inspected",
                           {"stage": control["workflow"]["current_stage"], "blocked": control["workflow"]["blocked"]}))
        append_request_event(
            session=session,
            request_id=request_id,
            tenant_id=context.tenant_id,
            event_type="CONTRACT_AGENT_ORCHESTRATED",
            actor_type="automation",
            actor_id=context.actor_id,
            payload={"roles": roles, "initial_workflow_stage": workflow_stage,
                     "final_workflow_stage": control["workflow"]["current_stage"]},
        )
        processed.append({"request_id": request_id, "ok": True, "roles": roles})

    completed_roles = sum(1 for item in processed for role in item["roles"] if role["status"] == "completed")
    blocked_roles = sum(1 for item in processed for role in item["roles"] if role["status"] == "blocked")
    return {"ok": True, "processed": len(processed), "completed_roles": completed_roles,
            "blocked_roles": blocked_roles, "requests": processed}
