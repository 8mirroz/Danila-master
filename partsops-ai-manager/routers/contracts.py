from __future__ import annotations

from typing import Any
import csv
import io
import uuid
from datetime import datetime, timezone
from io import BytesIO
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select, col

from database import get_session
from rbac import get_privileged_tenant
from app.automation.context import AutomationContext
from app.automation.runner import run_job
from services.contract_crawler_adapter import normalize_uploaded_crawler_payload
from services.contract_operations import (advance_contract_workflow, approve_client_export, approve_contract, archive_contract,
                                          authorize_purchase,
                                          collect_evidence, create_contract, evaluate_policy,
                                          export_contract, get_control_plane, list_contract_exceptions,
                                          record_purchase, register_analog_candidate, register_oem_candidate,
                                          review_position, update_contract_exception, verify_receipt)
from models import AnalogCandidate, CompatibilityEvidence, ContractPosition, OEMCandidate, PriceEvidence
from models import EventType, UploadArtifact
from app.automation.storage import storage
from event_store import emit_event

router = APIRouter(prefix="/api/contracts", tags=["Contract Operations"])


class ContractCreate(BaseModel):
    contract_ref: str = "2026.170160"
    positions: list[dict[str, Any]] = Field(min_length=1)
    actor_id: str = "operator"


class EvidenceBatch(BaseModel):
    rows: list[dict[str, Any]] = Field(min_length=1)
    actor_id: str = "crawler"


class ReviewPayload(BaseModel):
    evidence_id: str
    actor_id: str = "operator"
    comment: str | None = None


class ClientApprovalPayload(BaseModel):
    export_id: str
    actor_id: str = "customer"
    evidence_ref: str | None = None
    comment: str | None = None


class PurchaseAuthorizationPayload(BaseModel):
    approval_id: str
    actor_id: str = "operator"
    comment: str | None = None


class PurchaseRecordPayload(BaseModel):
    authorization_id: str
    supplier_ref: str
    actor_id: str = "operator"
    evidence_ref: str | None = None
    amount_total: float | None = None
    comment: str | None = None


class ReceiptVerificationPayload(BaseModel):
    purchase_id: str
    actor_id: str = "operator"
    evidence_ref: str
    received_quantity: int = Field(gt=0)
    discrepancy_note: str | None = None


class ArchivePayload(BaseModel):
    receipt_id: str
    actor_id: str = "operator"
    archive_ref: str
    comment: str | None = None


class ContractOrchestrationPayload(BaseModel):
    actor_id: str = "contract-agent"
    dry_run: bool = False
    generate_export: bool = False


class CandidatePayload(BaseModel):
    actor_id: str = "operator"
    data: dict[str, Any]


class WorkflowAdvancePayload(BaseModel):
    target_stage: str
    actor_id: str = "operator"
    reason: str = "manual workflow validation"


class ExceptionActionPayload(BaseModel):
    action: str
    actor_id: str = "operator"
    owner: str | None = None
    resolution: str | None = None
    evidence_ref: str | None = None


@router.post("", status_code=201)
def create(payload: ContractCreate, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    if payload.contract_ref != "2026.170160":
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Unsupported contract_ref")
    return create_contract(session, tenant_id, payload.positions, payload.actor_id)


@router.post("/upload", status_code=201)
async def upload(file: UploadFile = File(...), session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    """Accept a UTF-8/CP1251 CSV contract list; crawler output is a later step."""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise HTTPException(status_code=422, detail="Contract CSV is empty")
    positions = [{"part_number": row.get("part_number") or row.get("article") or row.get("OEM"),
                  "description": row.get("description") or row.get("part_name"),
                  "quantity": row.get("quantity") or row.get("qty") or 1} for row in rows]
    result = create_contract(session, tenant_id, positions, "operator")
    artifact_id = f"contract_art_{uuid.uuid4().hex[:12]}"
    stored_path, safe_filename, size_bytes = storage.save_file(
        tenant_id, artifact_id, BytesIO(raw), file.filename or "contract.csv")
    artifact = UploadArtifact(artifact_id=artifact_id, tenant_id=tenant_id, request_id=result["request_id"],
                              original_filename=file.filename or "contract.csv", safe_filename=safe_filename,
                              stored_path=stored_path, content_type=file.content_type, size_bytes=size_bytes,
                              sha256=storage.calculate_sha256(stored_path), source="upload",
                              uploaded_by="operator", status="attached",
                              created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    session.add(artifact)
    emit_event(session, result["request_id"], EventType.DOCUMENT_PARSED, actor_type="user", actor_id="operator",
               payload={"artifact_id": artifact_id, "filename": file.filename}, tenant_id=tenant_id, commit=False)
    session.commit()
    result["artifact_id"] = artifact_id
    return result


@router.post("/{request_id}/evidence")
def evidence(request_id: str, payload: EvidenceBatch, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return collect_evidence(session, request_id, tenant_id, payload.rows, payload.actor_id)


@router.post("/{request_id}/crawler-results/upload")
async def upload_crawler_results(request_id: str, file: UploadFile = File(...),
                                 session: Session = Depends(get_session),
                                 tenant_id: str = Depends(get_privileged_tenant)):
    raw = await file.read()
    rows, stats = normalize_uploaded_crawler_payload(raw, file.filename)
    if not rows:
        raise HTTPException(status_code=422, detail={"message": "Crawler upload contains no valid evidence rows",
                                                     "adapter_stats": stats})
    result = collect_evidence(session, request_id, tenant_id, rows, "my-crawler")
    return {**result, "adapter_stats": stats}


@router.get("/{request_id}/positions")
def positions(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    rows = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                       ContractPosition.tenant_id == tenant_id).order_by(col(ContractPosition.line_no))).all()
    return [{"position_id": row.position_id, "line_no": row.line_no, "part_number": row.part_number,
             "description": row.description, "quantity": row.quantity, "review_status": row.review_status,
             "selected_evidence_id": row.selected_evidence_id, "position_uuid": row.position_uuid,
             "completeness_status": row.completeness_status, "blocking_status": row.blocking_status,
             "blocking_error_code": row.blocking_error_code,
             "calculation": None if not row.calculation_json else row.calculation_json,
             "evidence": [{"evidence_id": evidence.evidence_id, "source": evidence.source,
                            "price": evidence.price, "source_url": evidence.source_url,
                            "captured_at": evidence.captured_at.isoformat(),
                            "expires_at": evidence.expires_at.isoformat() if evidence.expires_at else None,
                            "availability_status": evidence.availability_status,
                            "package_quantity": evidence.package_quantity,
                            "unit": evidence.unit,
                            "condition": evidence.condition,
                            "comparability_status": evidence.comparability_status,
                            "evidence_status": evidence.evidence_status,
                            "screenshot_ref": evidence.screenshot_ref,
                            "screenshot_sha256": evidence.screenshot_sha256,
                            "screenshot_readability_status": evidence.screenshot_readability_status,
                            "screenshot_completeness_status": evidence.screenshot_completeness_status}
                           for evidence in session.exec(select(PriceEvidence).where(
                               PriceEvidence.position_id == row.position_id,
                               PriceEvidence.tenant_id == tenant_id)).all()]} for row in rows]


@router.get("/{request_id}/crawler-manifest")
def crawler_manifest(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    rows = session.exec(select(ContractPosition).where(ContractPosition.request_id == request_id,
                                                       ContractPosition.tenant_id == tenant_id).order_by(col(ContractPosition.line_no))).all()
    if not rows:
        raise HTTPException(status_code=404, detail="Contract request not found")
    return {"request_id": request_id, "contract_ref": "2026.170160",
            "articles": [row.part_number for row in rows],
            "sources": ["exist.ru", "autodoc.ru", "rossko.ru"],
            "required_evidence": ["source_url", "captured_at", "screenshot_path"]}


@router.post("/{request_id}/positions/{position_id}/oem-candidates", status_code=201)
def oem_candidate(request_id: str, position_id: str, payload: CandidatePayload,
                  session: Session = Depends(get_session),
                  tenant_id: str = Depends(get_privileged_tenant)):
    return register_oem_candidate(session, request_id, tenant_id, position_id, payload.data, payload.actor_id)


@router.post("/{request_id}/positions/{position_id}/analog-candidates", status_code=201)
def analog_candidate(request_id: str, position_id: str, payload: CandidatePayload,
                     session: Session = Depends(get_session),
                     tenant_id: str = Depends(get_privileged_tenant)):
    return register_analog_candidate(session, request_id, tenant_id, position_id, payload.data, payload.actor_id)


@router.get("/{request_id}/positions/{position_id}/candidates")
def candidates(request_id: str, position_id: str, session: Session = Depends(get_session),
               tenant_id: str = Depends(get_privileged_tenant)):
    oems = session.exec(select(OEMCandidate).where(
        OEMCandidate.request_id == request_id,
        OEMCandidate.position_id == position_id,
        OEMCandidate.tenant_id == tenant_id,
    )).all()
    analogs = session.exec(select(AnalogCandidate).where(
        AnalogCandidate.request_id == request_id,
        AnalogCandidate.position_id == position_id,
        AnalogCandidate.tenant_id == tenant_id,
    )).all()
    compatibility = session.exec(select(CompatibilityEvidence).where(
        CompatibilityEvidence.request_id == request_id,
        CompatibilityEvidence.position_id == position_id,
        CompatibilityEvidence.tenant_id == tenant_id,
    )).all()
    return {
        "oem_candidates": [{
            "candidate_id": row.candidate_id,
            "oem_number": row.oem_number,
            "manufacturer": row.manufacturer,
            "source": row.source,
            "confidence": row.confidence,
            "lifecycle_status": row.lifecycle_status,
            "verification_status": row.verification_status,
        } for row in oems],
        "analog_candidates": [{
            "candidate_id": row.candidate_id,
            "article": row.article,
            "brand": row.brand,
            "source": row.source,
            "interchange_type": row.interchange_type,
            "independent_confirmations": row.independent_confirmations,
            "compatibility_score": row.compatibility_score,
            "evidence_score": row.evidence_score,
            "manual_review_status": row.manual_review_status,
            "rejection_reason": row.rejection_reason,
        } for row in analogs],
        "compatibility_evidence": [{
            "evidence_id": row.evidence_id,
            "candidate_type": row.candidate_type,
            "candidate_id": row.candidate_id,
            "evidence_type": row.evidence_type,
            "source": row.source,
            "score_points": row.score_points,
            "readability_status": row.readability_status,
            "completeness_status": row.completeness_status,
            "freshness_status": row.freshness_status,
        } for row in compatibility],
    }


@router.post("/{request_id}/evaluate")
def evaluate(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return evaluate_policy(session, request_id, tenant_id, "policy_engine")


@router.get("/{request_id}/control-plane")
def control_plane(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return get_control_plane(session, request_id, tenant_id)


@router.post("/{request_id}/orchestrate")
def orchestrate(request_id: str, payload: ContractOrchestrationPayload,
                session: Session = Depends(get_session),
                tenant_id: str = Depends(get_privileged_tenant)):
    return run_job(session, "contract_orchestrate", AutomationContext(
        tenant_id=tenant_id,
        request_id=request_id,
        actor_id=payload.actor_id,
        role="agent",
        dry_run=payload.dry_run,
        payload={"generate_export": payload.generate_export},
    ))


@router.post("/{request_id}/workflow/advance")
def workflow_advance(request_id: str, payload: WorkflowAdvancePayload,
                     session: Session = Depends(get_session),
                     tenant_id: str = Depends(get_privileged_tenant)):
    return advance_contract_workflow(session, request_id, tenant_id, payload.target_stage,
                                     payload.actor_id, payload.reason)


@router.get("/{request_id}/exceptions")
def exceptions(request_id: str, session: Session = Depends(get_session),
               tenant_id: str = Depends(get_privileged_tenant)):
    return list_contract_exceptions(session, request_id, tenant_id)


@router.post("/{request_id}/exceptions/{exception_id}/action")
def exception_action(request_id: str, exception_id: str, payload: ExceptionActionPayload,
                     session: Session = Depends(get_session),
                     tenant_id: str = Depends(get_privileged_tenant)):
    return update_contract_exception(session, request_id, tenant_id, exception_id, payload.action,
                                     payload.actor_id, payload.owner, payload.resolution, payload.evidence_ref)


@router.post("/{request_id}/positions/{position_id}/review")
def review(request_id: str, position_id: str, payload: ReviewPayload, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return review_position(session, request_id, tenant_id, position_id, payload.evidence_id, payload.actor_id, payload.comment)


@router.post("/{request_id}/approve")
def approve(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return approve_contract(session, request_id, tenant_id, "operator")


@router.post("/{request_id}/export")
def export(request_id: str, session: Session = Depends(get_session), tenant_id: str = Depends(get_privileged_tenant)):
    return export_contract(session, request_id, tenant_id, "operator")


@router.post("/{request_id}/client-approval")
def client_approval(request_id: str, payload: ClientApprovalPayload,
                    session: Session = Depends(get_session),
                    tenant_id: str = Depends(get_privileged_tenant)):
    return approve_client_export(session, request_id, tenant_id, payload.export_id, payload.actor_id,
                                 payload.evidence_ref, payload.comment)


@router.post("/{request_id}/purchase-authorization")
def purchase_authorization(request_id: str, payload: PurchaseAuthorizationPayload,
                           session: Session = Depends(get_session),
                           tenant_id: str = Depends(get_privileged_tenant)):
    return authorize_purchase(session, request_id, tenant_id, payload.approval_id, payload.actor_id, payload.comment)


@router.post("/{request_id}/purchase-record")
def purchase_record(request_id: str, payload: PurchaseRecordPayload,
                    session: Session = Depends(get_session),
                    tenant_id: str = Depends(get_privileged_tenant)):
    return record_purchase(session, request_id, tenant_id, payload.authorization_id, payload.supplier_ref,
                           payload.actor_id, payload.evidence_ref, payload.amount_total, payload.comment)


@router.post("/{request_id}/receipt-verification")
def receipt_verification(request_id: str, payload: ReceiptVerificationPayload,
                         session: Session = Depends(get_session),
                         tenant_id: str = Depends(get_privileged_tenant)):
    return verify_receipt(session, request_id, tenant_id, payload.purchase_id, payload.actor_id,
                          payload.evidence_ref, payload.received_quantity, payload.discrepancy_note)


@router.post("/{request_id}/archive")
def archive(request_id: str, payload: ArchivePayload,
            session: Session = Depends(get_session),
            tenant_id: str = Depends(get_privileged_tenant)):
    return archive_contract(session, request_id, tenant_id, payload.receipt_id, payload.actor_id,
                            payload.archive_ref, payload.comment)



@router.get("/{request_id}/export-custom-excel")
def export_custom_excel(
    request_id: str,
    suppliers: str | None = None,
    mode: str = "full",
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant)
):
    """
    Генерирует XLSX по форме договора.

    ?mode=full   — с гиперссылками на скриншоты (для внутреннего пользования)
    ?mode=simple — без скриншотов (для отправки клиенту, только после подтверждения)
    """
    from fastapi.responses import StreamingResponse
    from services.contract_operations import export_custom_contract_xlsx

    if mode not in ("full", "simple"):
        raise HTTPException(status_code=422, detail="mode должен быть 'full' или 'simple'")

    supplier_ids = [s.strip() for s in suppliers.split(",") if s.strip()] if suppliers else []
    try:
        buffer, filename = export_custom_contract_xlsx(session, request_id, tenant_id, supplier_ids, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{request_id}/export-evidence-pack")
def export_evidence_pack(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """
    Формирует ZIP-архив со всеми реальными скриншотами + index.json.
    Только для внутреннего использования (не для клиента).
    """
    from fastapi.responses import StreamingResponse, FileResponse
    from services.evidence_manager import get_evidence_manager
    import io

    em = get_evidence_manager(tenant_id, request_id)
    stats = em.get_stats()

    if stats["total"] == 0:
        raise HTTPException(
            status_code=404,
            detail="Скриншоты для данного запроса не найдены. Запустите скрапинг цен."
        )

    archive_path = em.pack_archive()
    archive_bytes = archive_path.read_bytes()

    return StreamingResponse(
        io.BytesIO(archive_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{request_id}_evidence_pack.zip"'}
    )




@router.post("/{request_id}/validate")
def validate_contract_data(
    request_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    """
    Запускает полный аудит данных контракта через Validation Layer (4 Quality Gates):
      1. PriceAnomalyDetector     — ценовые выбросы
      2. EvidenceIntegrityAuditor — целостность скриншотов
      3. AnalogCompatibilityChecker — корректность аналогов
      4. ScraperHealthChecker     — состояние Circuit Breaker-ов

    Возвращает ValidationReport в виде JSON.
    """
    from services.validation_layer import run_full_validation
    from services.live_scraper_service import get_circuit_breaker_statuses

    # Собираем цены по позициям из БД (PriceEvidence)
    evidences = session.exec(
        select(PriceEvidence).where(
            PriceEvidence.request_id == request_id,
            PriceEvidence.tenant_id == tenant_id,
        )
    ).all()

    prices_by_article: dict[str, dict[str, float | None]] = {}
    evidence_records: list[dict] = []

    for ev in evidences:
        art = ev.position_id  # используем position_id как ключ артикула
        if art not in prices_by_article:
            prices_by_article[art] = {}
        prices_by_article[art][ev.source] = ev.price
        evidence_records.append({
            "article": art,
            "source": ev.source,
            "screenshot_ref": ev.screenshot_ref,
            "screenshot_sha256": ev.screenshot_sha256,
            "price": ev.price,
        })

    # Собираем аналоги из БД
    positions = session.exec(
        select(ContractPosition).where(
            ContractPosition.request_id == request_id,
            ContractPosition.tenant_id == tenant_id,
        )
    ).all()

    analogs_data: list[dict] = []
    for pos in positions:
        analogs = session.exec(
            select(AnalogCandidate).where(
                AnalogCandidate.position_id == pos.position_id,
                AnalogCandidate.tenant_id == tenant_id,
            )
        ).all()
        for ana in analogs:
            analogs_data.append({
                "brand": ana.brand,
                "article": ana.article,
                "position_oem": pos.part_number,
            })

    circuit_statuses = get_circuit_breaker_statuses()

    report = run_full_validation(
        tenant_id=tenant_id,
        request_id=request_id,
        prices_by_article=prices_by_article,
        evidence_records=evidence_records,
        analogs=analogs_data,
        circuit_statuses=circuit_statuses,
    )

    return report.to_dict()


@router.post("/circuit-breaker/reset/{source}")
def reset_circuit_breaker(
    source: str,
    tenant_id: str = Depends(get_privileged_tenant),
):
    """
    Ручной сброс Circuit Breaker для указанного поставщика.
    Разрешённые значения: exist.ru, autodoc.ru, rossko.ru
    """
    from services.live_scraper_service import reset_circuit_breaker as do_reset, SCRAPER_REGISTRY
    if source not in SCRAPER_REGISTRY:
        raise HTTPException(
            status_code=422,
            detail=f"Неизвестный источник: {source}. Допустимые: {list(SCRAPER_REGISTRY.keys())}"
        )
    do_reset(source)
    return {"status": "ok", "message": f"Circuit breaker для {source} сброшен."}

