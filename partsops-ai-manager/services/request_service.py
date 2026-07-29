from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from agents import process_intake_request
from database import engine
from event_store import emit_event, emit_state_change, get_events, verify_event_chain
from learning import save_manual_correction
from pii import mask_email, mask_name, mask_phone, mask_vin, secure_pre_parse
from models import (
    AnalogCandidate,
    ContractPosition,
    ERPSyncLog,
    EventType,
    OEMCandidate,
    PartRequest,
    PriceEvidence,
    RequestState,
)
from suppliers import Invoice, SupplierCatalogItem
from state_machine import validate_transition
from policy_engine import EvidenceGates
from pricing import PricingContext, check_margin_guard, compute_price
from matcher import match_part_from_db

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _json_load(raw_value: Optional[str], default: Any) -> Any:
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return default

def _find_request_by_tenant(session: Session, request_id: str, tenant_id: str) -> PartRequest | None:
    return session.exec(
        select(PartRequest).where(
            PartRequest.request_id == request_id,
            PartRequest.tenant_id == tenant_id,
        )
    ).first()

def _build_pricing_context(req: PartRequest, session: Session):
    parts = _json_load(req.parts_json, [])
    selected_matches = _json_load(req.match_evidence_json, {})
    if not isinstance(selected_matches, dict):
        selected_matches = {}
    # Pricing policy is server-owned. Operator supplied pricing knobs are not
    # accepted here: a client must never be able to silently change margin or
    # logistics evidence by changing a request body.
    logistics_cost = 0.0
    urgency_level = "normal"
    target_margin_override = None

    line_items: list[dict[str, Any]] = []
    margin_violations: list[str] = []
    purchase_total = 0.0
    reliability_scores: list[float] = []
    item_matches: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for part in parts:
        part_name = str(part.get("name", "")).strip()
        if not part_name or part_name == "Неизвестная деталь":
            continue
        selected = selected_matches.get(part_name)
        if isinstance(selected, dict):
            selected_catalog_id = str((selected.get("item") or {}).get("catalog_id") or "").strip()
            if not selected_catalog_id:
                raise HTTPException(status_code=422, detail=f"Выбранный оффер для '{part_name}' повреждён")
            matches = [
                match for match in match_part_from_db(part_name, session, threshold=0.0, limit=25, tenant_id=req.tenant_id)
                if match.get("item", {}).get("catalog_id") == selected_catalog_id
            ]
            if not matches:
                raise HTTPException(status_code=422, detail=f"Выбранный оффер для '{part_name}' больше недоступен")
        else:
            matches = match_part_from_db(part_name, session, threshold=50.0, limit=1, tenant_id=req.tenant_id)
        if not matches:
            continue
        best = matches[0]
        qty = max(1, int(part.get("quantity", 1) or 1))
        purchase_price = float(best["item"]["price"])
        purchase_total += purchase_price * qty
        reliability_scores.append(float(best["supplier"]["reliability_score"]))
        item_matches.append((part, best))

    if not item_matches:
        raise HTTPException(status_code=422, detail="Нет подходящих позиций для расчета цены")

    supplier_reliability = min(reliability_scores) if reliability_scores else 1.0
    pricing_result = compute_price(
        PricingContext(
            purchase_price=purchase_total,
            logistics_cost=logistics_cost,
            urgency_level=urgency_level,
            supplier_reliability_score=supplier_reliability,
            target_margin_override=float(target_margin_override) if target_margin_override is not None else None,
        )
    )

    for part, best in item_matches:
        qty = max(1, int(part.get("quantity", 1) or 1))
        purchase_price = float(best["item"]["price"])
        sale_price = round(purchase_price * (1 + pricing_result.margin_rate), 2)
        margin_check = check_margin_guard(purchase_price, sale_price, policy_key="default")
        if not margin_check["passed"]:
            margin_violations.append(f"{part.get('name', '')}: {margin_check['violation']}")
        line_items.append(
            {
                "part_name": best["item"]["name"],
                "oem_number": best["item"]["oem_number"],
                "brand": best["item"]["brand"],
                "supplier": best["supplier"]["name"],
                "supplier_id": best["supplier"]["supplier_id"],
                "purchase_price": purchase_price,
                "sale_price": sale_price,
                "quantity": qty,
                "line_total": round(sale_price * qty, 2),
                "match_score": best["score"],
                "margin": margin_check["margin"],
                "margin_ok": margin_check["passed"],
            }
        )

    if logistics_cost > 0:
        logistics_sale_price = round(logistics_cost * (1 + pricing_result.margin_rate), 2)
        line_items.append(
            {
                "part_name": "Логистика",
                "oem_number": "",
                "brand": "",
                "supplier": "PartsOps",
                "supplier_id": "LOGISTICS",
                "purchase_price": logistics_cost,
                "sale_price": logistics_sale_price,
                "quantity": 1,
                "line_total": logistics_sale_price,
                "match_score": 100.0,
                "margin": pricing_result.margin_rate,
                "margin_ok": True,
            }
        )

    return line_items, pricing_result, margin_violations


class RequestService:
    OFFER_SELECTION_ALLOWED_STATES = {
        RequestState.MATCHING,
        RequestState.SUPPLIER_SEARCH,
        RequestState.OFFER_RANKING,
        RequestState.PRICING_REVIEW,
    }
    INTERNAL_ONLY_STATES = {
        RequestState.INVOICE_DRAFTED,
        RequestState.ERP_SYNCING,
        RequestState.ERP_SYNCED,
        RequestState.ERP_SYNC_FAILED,
    }

    @staticmethod
    def _role_permissions(role: str) -> dict[str, bool]:
        return {
            "can_manage_matching": role in {"manager", "admin"},
            "can_approve_pricing": role in {"finance", "admin"},
            "can_create_invoice": role in {"finance", "admin"},
            "can_sync_erp": role == "admin",
            "can_retry_pipeline": role == "admin",
        }

    @staticmethod
    def _allowed_actions(req: PartRequest, role: str, session: Session) -> list[dict[str, Any]]:
        permissions = RequestService._role_permissions(role)
        actions: list[dict[str, Any]] = []
        from state_machine import get_allowed_next
        for target in get_allowed_next(req.status):
            if target in RequestService.INTERNAL_ONLY_STATES:
                continue
            transition_check = validate_transition(req.status, target, req.model_dump(), strict_invariants=True)
            if not transition_check["allowed"]:
                continue
            required = "can_manage_matching"
            if target == RequestState.APPROVED:
                required = "can_approve_pricing"
            elif target == RequestState.ERP_SYNCING:
                required = "can_sync_erp"
            if permissions.get(required, False):
                actions.append({"id": f"transition:{target}", "kind": "transition", "target_state": target})
        if permissions["can_manage_matching"] and req.status in RequestService.OFFER_SELECTION_ALLOWED_STATES:
            actions.append({"id": "select_offer", "kind": "select_offer"})
        if (
            req.status == RequestState.APPROVED
            and permissions["can_create_invoice"]
            and req.pricing_evidence_json
            and req.margin_policy_passed is True
            and req.erp_quotation_ref
        ):
            actions.append({"id": "create_invoice", "kind": "create_invoice"})
        invoice = session.exec(
            select(Invoice).where(
                Invoice.request_id == req.request_id,
                Invoice.tenant_id == req.tenant_id,
            ).order_by(Invoice.created_at.desc())
        ).first()
        pricing_evidence = _json_load(req.pricing_evidence_json, {})
        has_approved_offer_snapshot = isinstance(pricing_evidence, dict) and bool(
            pricing_evidence.get("approved_offer_snapshot")
        )
        if (
            req.status in {RequestState.INVOICE_DRAFTED, RequestState.ERP_SYNC_FAILED}
            and permissions["can_sync_erp"]
            and invoice
            and has_approved_offer_snapshot
        ):
            actions.append({"id": "sync_to_erp", "kind": "sync_to_erp", "endpoint": f"/api/erp/sync/{req.request_id}"})
        return actions

    @staticmethod
    def get_workspace(session: Session, request_id: str, tenant_id: str, role: str) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        parts = _json_load(req.parts_json, [])
        selections = _json_load(req.match_evidence_json, {})
        positions = session.exec(select(ContractPosition).where(
            ContractPosition.request_id == request_id,
            ContractPosition.tenant_id == tenant_id,
        ).order_by(ContractPosition.line_no)).all()
        evidence = session.exec(select(PriceEvidence).where(
            PriceEvidence.request_id == request_id,
            PriceEvidence.tenant_id == tenant_id,
        )).all()
        oem_candidates = session.exec(select(OEMCandidate).where(
            OEMCandidate.request_id == request_id,
            OEMCandidate.tenant_id == tenant_id,
        )).all()
        analog_candidates = session.exec(select(AnalogCandidate).where(
            AnalogCandidate.request_id == request_id,
            AnalogCandidate.tenant_id == tenant_id,
        )).all()
        invoice = session.exec(select(Invoice).where(
            Invoice.request_id == request_id,
            Invoice.tenant_id == tenant_id,
        ).order_by(Invoice.created_at.desc())).first()
        sync = session.exec(select(ERPSyncLog).where(
            ERPSyncLog.request_id == request_id,
            ERPSyncLog.tenant_id == tenant_id,
        ).order_by(ERPSyncLog.created_at.desc())).first()
        gates = RequestService.get_request_gates(session, request_id, tenant_id)["gates"]
        blockers = [
            {"code": name, "message": value.get("reason", name)}
            for name, value in gates.items()
            if isinstance(value, dict) and not value.get("passed", value.get("ok", False))
        ]
        return {
            "request": {
                "request_id": req.request_id, "status": req.status, "priority": req.priority,
                "source": req.source, "customer_name": req.customer_name,
                "parts": parts, "updated_at": req.updated_at.isoformat() if req.updated_at else None,
            },
            "positions": [
                {"position_id": p.position_id, "part_number": p.part_number, "description": p.description,
                 "quantity": p.quantity, "selected_evidence_id": p.selected_evidence_id,
                 "review_status": p.review_status, "blocking_status": p.blocking_status,
                 "blocking_error_code": p.blocking_error_code}
                for p in positions
            ],
            "candidates": {
                "selected_offers": selections if isinstance(selections, dict) else {},
                "oem": [{"candidate_id": item.candidate_id, "position_id": item.position_id,
                         "verification_status": item.verification_status} for item in oem_candidates],
                "analogs": [{"candidate_id": item.candidate_id, "position_id": item.position_id,
                             "verification_status": item.verification_status} for item in analog_candidates],
            },
            "pricing": {"evidence_available": bool(req.pricing_evidence_json),
                        "evidence": _json_load(req.pricing_evidence_json, None),
                        "margin_policy_passed": req.margin_policy_passed,
                        "evidence_count": len(evidence)},
            "approval": {"status": "approved" if req.status in {RequestState.APPROVED, RequestState.INVOICE_DRAFTED} else "pending"},
            "invoice": {"status": (invoice.status.lower() if invoice else "missing"),
                        "invoice_ref": req.erp_invoice_ref or (invoice.invoice_number if invoice else None)},
            "erp": {"status": sync.status.lower() if sync else "not_synced",
                    "sync_id": sync.sync_id if sync else None,
                    "last_error": sync.last_error if sync else None},
            "gates": gates,
            "blockers": blockers,
            "principal_permissions": RequestService._role_permissions(role),
            "allowed_actions": RequestService._allowed_actions(req, role, session),
            "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        }

    @staticmethod
    def get_selected_matches(session: Session, request_id: str, tenant_id: str) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        selections = _json_load(req.match_evidence_json, {})
        return {
            "request_id": request_id,
            "selections": selections if isinstance(selections, dict) else {},
        }

    @staticmethod
    def select_match(
        session: Session,
        request_id: str,
        tenant_id: str,
        part_name: str,
        offer: dict[str, Any],
        actor_id: str,
    ) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        if req.status not in RequestService.OFFER_SELECTION_ALLOWED_STATES:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OFFER_SELECTION_NOT_ALLOWED",
                    "request_status": req.status,
                    "allowed_statuses": sorted(RequestService.OFFER_SELECTION_ALLOWED_STATES),
                },
            )
        normalized_part = part_name.strip()
        request_part_names = {
            str(part.get("name", "")).strip()
            for part in _json_load(req.parts_json, [])
            if isinstance(part, dict)
        }
        if normalized_part not in request_part_names:
            raise HTTPException(
                status_code=422,
                detail={"code": "OFFER_DOES_NOT_BELONG_TO_REQUEST", "part_name": normalized_part},
            )
        catalog_id = str((offer.get("item") or {}).get("catalog_id") or "").strip()
        if not normalized_part or not catalog_id:
            raise HTTPException(status_code=422, detail="part_name and offer.item.catalog_id are required")
        catalog_item = session.exec(
            select(SupplierCatalogItem).where(
                SupplierCatalogItem.catalog_id == catalog_id,
                SupplierCatalogItem.tenant_id == tenant_id,
            )
        ).first()
        if not catalog_item:
            raise HTTPException(status_code=422, detail="Selected catalog offer is not available for this tenant")

        selections = _json_load(req.match_evidence_json, {})
        if not isinstance(selections, dict):
            selections = {}
        selections[normalized_part] = offer
        req.match_evidence_json = json.dumps(selections, ensure_ascii=False, default=str)
        req.updated_at = _utcnow()
        session.add(req)
        emit_event(
            session=session,
            request_id=request_id,
            event_type=EventType.OFFER_RECEIVED,
            actor_type="user",
            actor_id=actor_id,
            payload={"part_name": normalized_part, "catalog_id": catalog_id, "supplier_id": catalog_item.supplier_id},
            tenant_id=tenant_id,
            commit=False,
        )
        session.commit()
        session.refresh(req)
        return {"request_id": request_id, "part_name": normalized_part, "offer": offer, "selections": selections}

    @staticmethod
    def preview_pricing(
        session: Session,
        request_id: str,
        tenant_id: str,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")

        if body and any(key in body for key in ("logistics_cost", "urgency_level", "margin_override", "target_margin_override")):
            raise HTTPException(status_code=422, detail="Pricing policy is managed by the backend and cannot be overridden by the client")
        line_items, pricing_result, margin_violations = _build_pricing_context(req, session)
        return {
            "request_id": request_id,
            "request_status": req.status,
            "pricing": {
                **asdict(pricing_result),
                "line_items": line_items,
                "margin_violations": margin_violations,
            },
        }

    @staticmethod
    def get_requests(session: Session, tenant_id: str) -> list[PartRequest]:
        return session.exec(
            select(PartRequest).where(PartRequest.tenant_id == tenant_id).order_by(PartRequest.created_at.desc())
        ).all()

    @staticmethod
    def create_request(
        tenant_id: str,
        payload_data: dict[str, Any],
        x_idempotency_key: Optional[str] = None
    ) -> dict[str, Any]:
        # 1. READ/Idempotency check - short lived transaction (Rule R7 compliance)
        if x_idempotency_key:
            with Session(engine) as check_session:
                existing = check_session.exec(
                    select(PartRequest).where(
                        PartRequest.idempotency_key == x_idempotency_key,
                        PartRequest.tenant_id == tenant_id,
                    )
                ).first()
                if existing:
                    emit_event(
                        session=check_session,
                        request_id=existing.request_id,
                        event_type=EventType.IDEMPOTENCY_HIT,
                        payload={"idempotency_key": x_idempotency_key},
                        tenant_id=tenant_id,
                    )
                    # Convert object to dict to avoid detached session issues
                    return {
                        "request": {
                            "request_id": existing.request_id,
                            "status": existing.status,
                            "priority": existing.priority,
                            "source": existing.source,
                            "customer_name": existing.customer_name,
                            "customer_phone_masked": existing.customer_phone_masked,
                            "customer_email_masked": existing.customer_email_masked,
                            "vehicle_vin_masked": existing.vehicle_vin_masked,
                            "created_at": existing.created_at.isoformat() if existing.created_at else None,
                        },
                        "agent_trace": None,
                        "idempotent": True,
                    }

        # 2. RUN LLM / EXTERNAL CALLS - outside of active db transaction (Rule R7 compliance)
        pre_parse = secure_pre_parse(payload_data["text"])
        agent_result = process_intake_request(pre_parse["masked_text"], vehicle_context=pre_parse["vehicle_context"])

        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        status = RequestState.PART_EXTRACTION if agent_result["validation_status"] == "PASSED" else RequestState.NEEDS_CLARIFICATION
        
        vehicle_vin = payload_data.get("vehicle_vin")
        final_vin = mask_vin(vehicle_vin) if vehicle_vin else None
        if not final_vin and agent_result.get("vehicle_vin"):
            final_vin = mask_vin(agent_result["vehicle_vin"])

        customer_name = payload_data.get("customer_name", "Unknown")
        customer_phone = payload_data.get("customer_phone")
        customer_email = payload_data.get("customer_email")

        # 3. WRITE - write results in a new transaction
        with Session(engine) as write_session:
            new_request = PartRequest(
                request_id=request_id,
                tenant_id=tenant_id,
                idempotency_key=x_idempotency_key,
                source=payload_data["source"],
                status=status,
                priority=payload_data.get("priority", "normal"),
                customer_name=mask_name(customer_name) if customer_name else customer_name,
                customer_phone_masked=mask_phone(customer_phone) if customer_phone else None,
                customer_email_masked=mask_email(customer_email) if customer_email else None,
                vehicle_vin_masked=final_vin,
                vehicle_make=agent_result.get("vehicle_make"),
                vehicle_model=agent_result.get("vehicle_model"),
                vehicle_year=agent_result.get("vehicle_year"),
                parts_json=json.dumps(agent_result.get("extracted_parts", []), ensure_ascii=False, default=str),
                pricing_evidence_json=json.dumps(agent_result.get("pricing_evidence", {}), ensure_ascii=False, default=str)
                if agent_result.get("pricing_evidence")
                else None,
            )
            write_session.add(new_request)
            write_session.flush()

            emit_event(
                session=write_session,
                request_id=request_id,
                event_type=EventType.REQUEST_RECEIVED,
                actor_type="system",
                payload={"source": payload_data["source"], "priority": payload_data.get("priority", "normal"), "has_vin": bool(vehicle_vin)},
                tenant_id=tenant_id,
                commit=False,
            )
            emit_event(
                session=write_session,
                request_id=request_id,
                event_type=EventType.PART_INTENT_EXTRACTED,
                actor_type="agent",
                actor_id="parts_extractor",
                payload={
                    "parts_count": len(agent_result.get("extracted_parts", [])),
                    "validation_status": agent_result["validation_status"],
                },
                tenant_id=tenant_id,
                commit=False,
            )
            emit_state_change(
                session=write_session,
                request_id=request_id,
                from_state="NEW",
                to_state=status,
                reason=f"Agent validation: {agent_result['validation_status']}",
                tenant_id=tenant_id,
                commit=False,
            )
            write_session.commit()
            write_session.refresh(new_request)

            return {
                "request": {
                    "request_id": new_request.request_id,
                    "status": new_request.status,
                    "priority": new_request.priority,
                    "source": new_request.source,
                    "customer_name": new_request.customer_name,
                    "customer_phone_masked": new_request.customer_phone_masked,
                    "customer_email_masked": new_request.customer_email_masked,
                    "vehicle_vin_masked": new_request.vehicle_vin_masked,
                    "created_at": new_request.created_at.isoformat(),
                },
                "agent_trace": agent_result,
                "idempotent": False,
            }

    @staticmethod
    def get_request(session: Session, request_id: str, tenant_id: str) -> PartRequest:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        return req

    @staticmethod
    def transition_state(
        session: Session,
        request_id: str,
        tenant_id: str,
        target_state: str,
        reason: str,
        actor_id: str = "system"
    ) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")

        return RequestService._apply_transition(
            session=session,
            req=req,
            target_state=target_state,
            actor_id=actor_id,
            actor_type="user",
            reason=reason,
            commit=True,
        )

    @staticmethod
    def _apply_transition(
        session: Session,
        req: PartRequest,
        target_state: str,
        actor_id: str,
        actor_type: str,
        reason: str,
        commit: bool,
    ) -> dict[str, Any]:
        """The only lifecycle mutation path used by production commands."""
        result = validate_transition(req.status, target_state, req.model_dump(), strict_invariants=True)
        if not result["allowed"]:
            raise HTTPException(status_code=409, detail={
                "code": "INVALID_LIFECYCLE_TRANSITION",
                "reason": result["reason"],
                "violations": result.get("violations", []),
            })

        old_state = req.status
        req.status = target_state
        req.updated_at = _utcnow()
        session.add(req)
        emit_state_change(
            session=session,
            request_id=req.request_id,
            from_state=old_state,
            to_state=target_state,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            tenant_id=req.tenant_id,
            commit=False,
        )
        if commit:
            session.commit()
            session.refresh(req)
        return {"request_id": req.request_id, "old_state": old_state, "new_state": target_state}

    @staticmethod
    def create_manual_correction(
        session: Session,
        request_id: str,
        tenant_id: str,
        payload_data: dict[str, Any]
    ) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        sample = save_manual_correction(
            session=session,
            request_id=request_id,
            tenant_id=tenant_id,
            source_text=payload_data["source_text"],
            corrected_parts_json=payload_data["corrected_parts_json"],
            correction_reason_tags=payload_data.get("correction_reason_tags", []),
            user_id="admin",
            corrected_vehicle_json=payload_data.get("corrected_vehicle_json"),
        )
        return {"status": "saved", "sample_id": sample.sample_id}

    @staticmethod
    def get_request_gates(session: Session, request_id: str, tenant_id: str) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        payload_to_check = {
            "customer_name": req.customer_name,
            "customer_phone_masked": req.customer_phone_masked,
            "customer_email_masked": req.customer_email_masked,
            "vehicle_vin_masked": req.vehicle_vin_masked,
            "parts": _json_load(req.parts_json, []),
        }
        gates = {
            "PII_SAFE": EvidenceGates.gate_pii_safe(payload_to_check),
            "EVENT_CHAIN_VALID": EvidenceGates.gate_event_chain_valid(request_id, session, tenant_id),
            "MATCH_CONFIDENCE": EvidenceGates.gate_match_confidence(req),
            "PRICING_POLICY": EvidenceGates.gate_pricing_policy(req),
            "OPERATOR_APPROVAL": EvidenceGates.gate_operator_approval(request_id, session, tenant_id),
            "DELIVERY_SAFE": EvidenceGates.gate_delivery_safe(payload_to_check),
            "ERP_SYNC_VALID": EvidenceGates.gate_erp_sync_valid(req),
        }
        return {"request_id": request_id, "gates": gates}

    @staticmethod
    def get_request_events(session: Session, request_id: str, tenant_id: str) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        events = get_events(request_id, session, tenant_id=req.tenant_id)
        if not events:
            raise HTTPException(status_code=404, detail="No events found for this request")
        return {
            "request_id": request_id,
            "total_events": len(events),
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "actor_type": event.actor_type,
                    "actor_id": event.actor_id,
                    "occurred_at": event.occurred_at.isoformat(),
                    "payload": _json_load(event.payload_json, {}),
                    "event_hash": f"{event.event_hash[:8]}..." if event.event_hash else None,
                }
                for event in events
            ],
        }

    @staticmethod
    def audit_event_chain(session: Session, request_id: str, tenant_id: str) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")
        return verify_event_chain(request_id, session, tenant_id=req.tenant_id)

    @staticmethod
    def generate_invoice(
        session: Session,
        request_id: str,
        tenant_id: str,
        body: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        req = _find_request_by_tenant(session, request_id, tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Request not found")

        existing_invoice = session.exec(
            select(Invoice).where(
                Invoice.request_id == request_id,
                Invoice.tenant_id == tenant_id,
            ).order_by(Invoice.created_at.desc())
        ).first()
        if existing_invoice:
            return {
                "status": "DRAFT_CREATED",
                "idempotent": True,
                "invoice": {
                    "invoice_number": existing_invoice.invoice_number,
                    "request_id": request_id,
                    "items": _json_load(existing_invoice.items_json, []),
                    "subtotal": existing_invoice.subtotal,
                    "tax": existing_invoice.tax,
                    "total": existing_invoice.total,
                    "currency": "RUB",
                },
            }
        if req.status != RequestState.APPROVED:
            raise HTTPException(status_code=422, detail="Invoice generation requires APPROVED request status")

        if not req.pricing_evidence_json or req.margin_policy_passed is not True:
            raise HTTPException(status_code=422, detail="Invoice generation requires approved pricing evidence")
        if not req.erp_quotation_ref:
            raise HTTPException(status_code=422, detail="Invoice generation requires an ERP quotation reference")

        selected_offers = _json_load(req.match_evidence_json, {})
        required_part_names = {
            str(part.get("name", "")).strip()
            for part in _json_load(req.parts_json, [])
            if isinstance(part, dict) and str(part.get("name", "")).strip()
        }
        if not isinstance(selected_offers, dict) or not required_part_names.issubset(set(selected_offers)):
            raise HTTPException(status_code=422, detail={"code": "INVOICE_SELECTED_OFFER_REQUIRED"})

        if body and any(key in body for key in ("logistics_cost", "urgency_level", "margin_override", "target_margin_override")):
            raise HTTPException(status_code=422, detail="Pricing policy is managed by the backend and cannot be overridden by the client")
        line_items, pricing_result, margin_violations = _build_pricing_context(req, session)
        if margin_violations or not pricing_result.margin_policy_passed:
            raise HTTPException(status_code=422, detail="Invoice generation blocked by pricing policy")
        subtotal = round(sum(item["line_total"] for item in line_items), 2)
        invoice = Invoice(
            tenant_id=tenant_id,
            invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
            request_id=request_id,
            supplier_id=line_items[0]["supplier_id"] if line_items else "",
            customer_name=req.customer_name or "",
            items_json=json.dumps(line_items, ensure_ascii=False, default=str),
            subtotal=round(pricing_result.subtotal_before_tax, 2),
            tax=pricing_result.tax_amount,
            total=pricing_result.client_price,
            status="DRAFT",
            created_at=_utcnow(),
        )
        pricing_evidence = _json_load(req.pricing_evidence_json, {})
        if not isinstance(pricing_evidence, dict):
            pricing_evidence = {}
        pricing_evidence["approved_offer_snapshot"] = selected_offers
        pricing_evidence["approved_at"] = _utcnow().isoformat()
        req.pricing_evidence_json = json.dumps(pricing_evidence, ensure_ascii=False, default=str)
        session.add(invoice)
        req.erp_invoice_ref = invoice.invoice_number
        session.add(req)
        emit_event(
            session=session,
            request_id=request_id,
            event_type=EventType.ERP_DOCUMENT_CREATED,
            actor_type="system",
            actor_id="pricing_engine",
            payload={"invoice_number": invoice.invoice_number, "line_items": len(line_items), "subtotal": subtotal},
            tenant_id=tenant_id,
            commit=False,
        )
        RequestService._apply_transition(
            session=session,
            req=req,
            target_state=RequestState.INVOICE_DRAFTED,
            actor_type="system",
            actor_id="pricing_engine",
            reason="Invoice draft created",
            commit=False,
        )
        session.commit()
        session.refresh(invoice)
        return {
            "status": "DRAFT_CREATED",
            "invoice": {
                "invoice_number": invoice.invoice_number,
                "request_id": request_id,
                "items": line_items,
                "subtotal": invoice.subtotal,
                "tax": invoice.tax,
                "total": invoice.total,
                "currency": pricing_result.currency,
            },
            "pricing": {
                "margin_rate": pricing_result.margin_rate,
                "margin_amount": pricing_result.margin_amount,
                "violations": margin_violations,
                "warnings": pricing_result.warnings,
            },
        }
