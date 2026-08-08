"""Versioned commercial quotes backed by the canonical pricing result."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from models import PartRequest, QuoteDocument, QuoteVersion, RequestState
from services.request_service import RequestService


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _request(session: Session, organization_id: str, request_id: str) -> PartRequest:
    request = RequestService.get_request(session, request_id, organization_id)
    if request.status != RequestState.APPROVED:
        raise HTTPException(
            422,
            detail={
                "code": "QUOTE_APPROVAL_REQUIRED",
                "request_status": request.status,
            },
        )
    if request.margin_policy_passed is not True:
        raise HTTPException(422, detail={"code": "QUOTE_MARGIN_POLICY_REQUIRED"})
    return request


def _selected_offers(request: PartRequest) -> dict[str, Any]:
    try:
        selected = json.loads(request.match_evidence_json or "{}")
        parts = json.loads(request.parts_json or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(422, detail={"code": "QUOTE_EVIDENCE_INVALID"}) from exc
    required = {
        str(part.get("name", "")).strip()
        for part in parts
        if isinstance(part, dict) and part.get("name")
    }
    if not isinstance(selected, dict) or not required.issubset(selected):
        raise HTTPException(422, detail={"code": "QUOTE_SELECTED_OFFER_REQUIRED"})
    return selected


def issue_quote(
    session: Session,
    *,
    organization_id: str,
    request_id: str,
    created_by: str,
    valid_for_days: int = 14,
) -> dict[str, Any]:
    request = _request(session, organization_id, request_id)
    selected = _selected_offers(request)
    pricing = RequestService.preview_pricing(session, request_id, organization_id)[
        "pricing"
    ]
    if pricing.get("margin_violations") or not pricing.get("margin_policy_passed"):
        raise HTTPException(422, detail={"code": "QUOTE_MARGIN_POLICY_REQUIRED"})
    now = _now()
    quote = session.exec(
        select(QuoteDocument).where(
            QuoteDocument.organization_id == organization_id,
            QuoteDocument.request_id == request_id,
        )
    ).first()
    if quote is None:
        quote = QuoteDocument(
            quote_id=f"QTE-{uuid.uuid4().hex[:10].upper()}",
            organization_id=organization_id,
            request_id=request_id,
            current_version=1,
            valid_until=now + timedelta(days=valid_for_days),
            created_at=now,
            updated_at=now,
        )
        session.add(quote)
        session.flush()
    else:
        quote.current_version += 1
        quote.status = "issued"
        quote.valid_until = now + timedelta(days=valid_for_days)
        quote.updated_at = now
        session.add(quote)
    version = QuoteVersion(
        quote_id=quote.quote_id,
        organization_id=organization_id,
        version=quote.current_version,
        pricing_snapshot_json=_json(pricing),
        selected_offer_snapshot_json=_json(selected),
        created_by=created_by,
        created_at=now,
    )
    session.add(version)
    session.commit()
    session.refresh(quote)
    return serialize_quote(quote, version)

def build_multi_tier_options(pricing: dict[str, Any]) -> dict[str, Any]:
    total_cost = float(pricing.get("total_supplier_cost_rub", 0.0) or 0.0)
    total_sell = float(pricing.get("total_sell_price_rub", 0.0) or 0.0)

    if total_sell == 0.0:
        total_sell = total_cost * 1.30

    oem_total = round(total_sell, 2)
    optimum_total = round(total_sell * 0.82, 2)
    budget_total = round(total_sell * 0.65, 2)

    oem_margin = round(((oem_total - total_cost) / oem_total) * 100, 1) if oem_total > 0 else 0.0
    optimum_margin = round(((optimum_total - (total_cost * 0.75)) / optimum_total) * 100, 1) if optimum_total > 0 else 0.0
    budget_margin = round(((budget_total - (total_cost * 0.55)) / budget_total) * 100, 1) if budget_total > 0 else 0.0

    return {
        "oem": {
            "tier_key": "oem",
            "name": "Оригинал OEM",
            "description": "100% заводские детали от официального дилера",
            "total_price_rub": oem_total,
            "estimated_margin_percent": max(0.0, oem_margin),
            "delivery_days": 1,
            "badge": "Заводское качество",
        },
        "optimum": {
            "tier_key": "optimum",
            "name": "Оптимум (Tier-1)",
            "description": "Проверенные европейские аналоги (Bosch, Lemforder, Sachs)",
            "total_price_rub": optimum_total,
            "estimated_margin_percent": max(0.0, optimum_margin),
            "delivery_days": 2,
            "badge": "Выбор закупщиков",
        },
        "budget": {
            "tier_key": "budget",
            "name": "Эконом",
            "description": "Доступные проверенные производители в наличии",
            "total_price_rub": budget_total,
            "estimated_margin_percent": max(0.0, budget_margin),
            "delivery_days": 1,
            "badge": "Максимальная выгода",
        },
    }


def get_quote(
    session: Session, *, organization_id: str, quote_id: str, version: int | None = None
) -> dict[str, Any]:
    quote = session.exec(
        select(QuoteDocument).where(
            QuoteDocument.quote_id == quote_id,
            QuoteDocument.organization_id == organization_id,
        )
    ).first()
    if not quote:
        raise HTTPException(404, detail="Quote not found")
    query = select(QuoteVersion).where(
        QuoteVersion.quote_id == quote.quote_id,
        QuoteVersion.organization_id == organization_id,
    )
    if version is not None:
        query = query.where(QuoteVersion.version == version)
    else:
        query = query.where(QuoteVersion.version == quote.current_version)
    revision = session.exec(query).first()
    if not revision:
        raise HTTPException(404, detail="Quote version not found")
    return serialize_quote(quote, revision)


def list_quotes(session: Session, *, organization_id: str) -> list[dict[str, Any]]:
    quotes = session.exec(
        select(QuoteDocument)
        .where(QuoteDocument.organization_id == organization_id)
        .order_by(QuoteDocument.updated_at.desc())
    ).all()
    return [
        {
            "quote_id": quote.quote_id,
            "request_id": quote.request_id,
            "status": quote.status,
            "current_version": quote.current_version,
            "valid_until": quote.valid_until.isoformat(),
            "updated_at": quote.updated_at.isoformat(),
        }
        for quote in quotes
    ]


def serialize_quote(quote: QuoteDocument, version: QuoteVersion) -> dict[str, Any]:
    return {
        "quote_id": quote.quote_id,
        "request_id": quote.request_id,
        "status": quote.status,
        "version": version.version,
        "valid_until": quote.valid_until.isoformat(),
        "pricing": json.loads(version.pricing_snapshot_json),
        "selected_offers": json.loads(version.selected_offer_snapshot_json),
        "created_at": version.created_at.isoformat(),
    }
