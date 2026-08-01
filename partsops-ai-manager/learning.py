"""
PartsOps AI Manager v3 — Learning Loop Layer
Implements the Golden Dataset and system accuracy tracking.
"""
from sqlmodel import Session, select
from models import GoldenSample, PartRequest, EventType
from event_store import emit_event
import uuid
import json


def save_manual_correction(
    session: Session,
    request_id: str,
    tenant_id: str,
    source_text: str,
    corrected_parts_json: str,
    correction_reason_tags: list[str],
    user_id: str,
    corrected_vehicle_json: str = None,
    corrected_position_indexes: list[int] | None = None,
) -> GoldenSample:
    """
    Saves a manager-approved manual correction to the Golden Dataset.
    Emits an event to the Event Store.
    """
    sample_id = f"GLD-{str(uuid.uuid4())[:8].upper()}"

    # Check if a sample for this request already exists
    existing = session.exec(
        select(GoldenSample).where(GoldenSample.request_id == request_id)
    ).first()

    if existing:
        existing.corrected_parts_json = corrected_parts_json
        existing.corrected_vehicle_json = corrected_vehicle_json
        existing.corrected_position_indexes_json = (
            json.dumps(sorted(set(corrected_position_indexes)))
            if corrected_position_indexes is not None
            else None
        )
        existing.correction_reason_tags = json.dumps(correction_reason_tags, ensure_ascii=False)
        existing.approved_by = user_id
        session.add(existing)
        session.commit()
        session.refresh(existing)
        sample = existing
    else:
        sample = GoldenSample(
            sample_id=sample_id,
            tenant_id=tenant_id,
            request_id=request_id,
            source_text=source_text,
            corrected_parts_json=corrected_parts_json,
            corrected_vehicle_json=corrected_vehicle_json,
            corrected_position_indexes_json=(
                json.dumps(sorted(set(corrected_position_indexes)))
                if corrected_position_indexes is not None
                else None
            ),
            correction_reason_tags=json.dumps(correction_reason_tags, ensure_ascii=False),
            approved_by=user_id,
            model_version="meta/llama-3.1-70b-instruct",
            prompt_version="v3.1",
        )
        session.add(sample)
        session.commit()
        session.refresh(sample)

    emit_event(
        session, request_id, EventType.GOLDEN_SAMPLE_CREATED,
        actor_type="user", actor_id=user_id,
        payload={
            "sample_id": sample.sample_id,
            "correction_reason_tags": correction_reason_tags
        },
    )

    return sample


def calculate_system_accuracy(session: Session, tenant_id: str) -> dict:
    """
    Calculates the accuracy metric:
    Percentage of requests processed without manual correction.
    """
    # 1. Total closed or paid requests
    total_requests_query = select(PartRequest).where(
        PartRequest.tenant_id == tenant_id,
        PartRequest.status.in_(["PAID", "CLOSED", "FULFILLED", "PURCHASE_ORDERED", "SENT_TO_CLIENT"])
    )
    total_requests = len(session.exec(total_requests_query).all())

    if total_requests == 0:
        return {"accuracy_percent": 100.0, "total_requests": 0, "manual_corrections": 0}

    # 2. Total requests that have a golden sample (i.e. manual correction)
    corrected_query = select(GoldenSample).where(GoldenSample.tenant_id == tenant_id)
    all_corrected = session.exec(corrected_query).all()
    
    # Only count corrections for requests that are in the "completed" states above
    corrected_request_ids = set(c.request_id for c in all_corrected)
    
    completed_corrected = 0
    for req in session.exec(total_requests_query).all():
        if req.request_id in corrected_request_ids:
            completed_corrected += 1

    accuracy = max(0.0, ((total_requests - completed_corrected) / total_requests) * 100.0)

    # 3. Aggregate top tags
    tag_counts = {}
    for c in all_corrected:
        if c.correction_reason_tags:
            tags = json.loads(c.correction_reason_tags)
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1

    top_reasons = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "accuracy_percent": round(accuracy, 1),
        "total_requests": total_requests,
        "manual_corrections": completed_corrected,
        "top_correction_reasons": top_reasons,
    }
