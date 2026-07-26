from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models import ContractPosition, AnalogCandidate, OEMCandidate, PriceEvidence, RequestState, PartRequest
from services.analog_resolver import (
    detect_oem_unavailability,
    evaluate_analog_risk,
    rank_and_select_analogs,
    classify_brand_tier,
)

router = APIRouter(prefix="/api/contracts", tags=["Analogs"])


class SelectAnalogRequest(BaseModel):
    candidate_id: str
    reviewer_comment: Optional[str] = None
    actor: str = "operator"


@router.get("/{request_id}/analogs-report")
def get_contract_analogs_report(
    request_id: str,
    tenant_id: str = Query("tenant-a"),
    session: Session = Depends(get_session)
) -> dict[str, Any]:
    """
    Generate complete analogs and fallback availability report for a contract request.
    """
    positions = session.exec(
        select(ContractPosition).where(
            ContractPosition.request_id == request_id,
            ContractPosition.tenant_id == tenant_id,
        )
    ).all()

    if not positions:
        raise HTTPException(status_code=404, detail="Request positions not found")

    report_positions = []
    total_positions = len(positions)
    positions_with_analogs = 0

    for pos in positions:
        # Check OEM candidates & evidence
        oem_candidates = session.exec(
            select(OEMCandidate).where(
                OEMCandidate.position_id == pos.position_id,
                OEMCandidate.tenant_id == tenant_id,
            )
        ).all()

        oem_evidence = session.exec(
            select(PriceEvidence).where(
                PriceEvidence.position_id == pos.position_id,
                PriceEvidence.tenant_id == tenant_id,
            )
        ).all()

        oem_status = detect_oem_unavailability(oem_evidence, oem_candidates)
        
        # Rank analogs
        ranked_analogs = rank_and_select_analogs(
            session=session,
            position_id=pos.position_id,
            tenant_id=tenant_id,
            is_safety_related=pos.safety_related
        )

        if ranked_analogs:
            positions_with_analogs += 1

        selected_analog = next((a for a in ranked_analogs if a["manual_review_status"] == "approved"), None)
        top_recommendation = ranked_analogs[0] if ranked_analogs else None

        report_positions.append({
            "position_id": pos.position_id,
            "part_number": pos.part_number,
            "description": pos.description,
            "quantity": pos.quantity,
            "safety_related": pos.safety_related,
            "oem_unavailability": oem_status,
            "ranked_analogs": ranked_analogs,
            "selected_analog": selected_analog,
            "top_recommendation": top_recommendation,
        })

    return {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "total_positions": total_positions,
        "positions_with_analogs": positions_with_analogs,
        "positions": report_positions,
    }


@router.post("/{request_id}/positions/{position_id}/resolve-analogs")
def resolve_position_analogs(
    request_id: str,
    position_id: str,
    tenant_id: str = Query("tenant-a"),
    session: Session = Depends(get_session)
) -> dict[str, Any]:
    """
    Force re-evaluation and ranking of analogs for a given contract position.
    """
    pos = session.exec(
        select(ContractPosition).where(
            ContractPosition.position_id == position_id,
            ContractPosition.request_id == request_id,
            ContractPosition.tenant_id == tenant_id,
        )
    ).first()

    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    ranked = rank_and_select_analogs(
        session=session,
        position_id=position_id,
        tenant_id=tenant_id,
        is_safety_related=pos.safety_related
    )

    return {
        "request_id": request_id,
        "position_id": position_id,
        "safety_related": pos.safety_related,
        "analogs": ranked,
    }


@router.post("/{request_id}/positions/{position_id}/select-analog")
def select_position_analog(
    request_id: str,
    position_id: str,
    payload: SelectAnalogRequest,
    tenant_id: str = Query("tenant-a"),
    session: Session = Depends(get_session)
) -> dict[str, Any]:
    """
    Approve and lock a specific analog candidate as the chosen replacement for a position.
    """
    pos = session.exec(
        select(ContractPosition).where(
            ContractPosition.position_id == position_id,
            ContractPosition.request_id == request_id,
            ContractPosition.tenant_id == tenant_id,
        )
    ).first()

    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")

    target_candidate = session.exec(
        select(AnalogCandidate).where(
            AnalogCandidate.candidate_id == payload.candidate_id,
            AnalogCandidate.position_id == position_id,
            AnalogCandidate.tenant_id == tenant_id,
        )
    ).first()

    if not target_candidate:
        raise HTTPException(status_code=404, detail="Analog candidate not found")

    # Reset all other analogs for this position to pending
    all_analogs = session.exec(
        select(AnalogCandidate).where(
            AnalogCandidate.position_id == position_id,
            AnalogCandidate.tenant_id == tenant_id,
        )
    ).all()

    for a in all_analogs:
        if a.candidate_id == payload.candidate_id:
            a.manual_review_status = "approved"
            a.rejection_reason = None
        else:
            a.manual_review_status = "rejected"
            a.rejection_reason = f"Replaced by chosen analog {target_candidate.article} ({target_candidate.brand})"
        session.add(a)

    pos.change_reason = f"Analog {target_candidate.article} ({target_candidate.brand}) selected by {payload.actor}"
    session.add(pos)
    session.commit()

    return {
        "status": "success",
        "position_id": position_id,
        "selected_analog": {
            "candidate_id": target_candidate.candidate_id,
            "article": target_candidate.article,
            "brand": target_candidate.brand,
            "quality_tier": target_candidate.quality_tier,
            "risk_score": target_candidate.risk_score,
            "review_status": target_candidate.manual_review_status,
        }
    }
