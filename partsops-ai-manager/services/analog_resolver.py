import json
from typing import Any, Optional, Sequence
from datetime import datetime, timezone
from sqlmodel import Session, select

from models import AnalogCandidate, ContractPosition, PriceEvidence, OEMCandidate

# Curated brand tier catalogs
OES_BRANDS = {
    "MANN-FILTER", "MANN", "LEMFÖRDER", "LEMFOERDER", "BOSCH", "SACHS",
    "VALEO", "ZF", "BREMBO", "MAHLE", "KNECHT", "DENSO", "TEXTAR", "ATE",
    "HELLA", "PIERBURG", "BEHR", "TRW", "NISSENS"
}

PREMIUM_AFTERMARKET_BRANDS = {
    "FEBI", "FEBI BILSTEIN", "MEYLE", "INA", "CONTITECH", "NGK", "NIBK",
    "SKF", "DELPHI", "CORTECO", "DAYCO", "SWAG", "OPTIMAL", "GATES",
    "MOOG", "SIDEM", "MONROE", "KYB", "KAYABA"
}

BUDGET_BRANDS = {
    "PATRON", "STELLOX", "METACO", "ZERTIER", "SAT", "FENOX", "MILES",
    "LYNXAUTO", "ZEKKERT", "JAPANPARTS", "ASVA", "AVANTECH", "JUST DRIVE"
}


def classify_brand_tier(brand: str) -> tuple[str, int]:
    """
    Classify a brand into quality tiers:
    OES (Tier 1) -> Base Risk: 5%
    PREMIUM_AFTERMARKET (Tier 2) -> Base Risk: 15%
    BUDGET (Tier 3) -> Base Risk: 35%
    SPEC_MATCH (Tier 4) -> Base Risk: 55%
    """
    normalized = brand.strip().upper() if brand else ""
    if any(b in normalized for b in OES_BRANDS):
        return "OES", 5
    if any(b in normalized for b in PREMIUM_AFTERMARKET_BRANDS):
        return "PREMIUM_AFTERMARKET", 15
    if any(b in normalized for b in BUDGET_BRANDS):
        return "BUDGET", 35
    return "SPEC_MATCH", 55


def detect_oem_unavailability(
    oem_evidence: Sequence[PriceEvidence],
    oem_candidates: Sequence[OEMCandidate],
    max_acceptable_eta: int = 30
) -> dict[str, Any]:
    """
    Determine if OEM is unavailable or degraded.
    Triggers:
    - OEM_NOT_FOUND: No OEM candidates or zero evidence
    - OEM_OUT_OF_STOCK: All price evidence rows have availability_status != 'available' or quantity = 0
    - OEM_DELIVERY_DEGRADED: Minimum delivery ETA > max_acceptable_eta
    """
    if not oem_candidates:
        return {
            "is_unavailable": True,
            "reason_code": "OEM_NOT_FOUND",
            "message": "Оригинальный OEM артикул не найден в каталогах производителей."
        }
    
    if not oem_evidence:
        return {
            "is_unavailable": True,
            "reason_code": "OEM_OUT_OF_STOCK",
            "message": "Предложения по оригинальному OEM отсутствуют у всех проверенных поставщиков."
        }

    available_offers = [e for e in oem_evidence if e.availability_status == "available"]
    if not available_offers:
        return {
            "is_unavailable": True,
            "reason_code": "OEM_OUT_OF_STOCK",
            "message": "Остатки оригинального OEM равны нулю (0 шт) во всей сети дистрибьюторов."
        }

    etas = [e.delivery_eta_days for e in available_offers if e.delivery_eta_days is not None]
    if etas and min(etas) > max_acceptable_eta:
        return {
            "is_unavailable": True,
            "reason_code": "OEM_DELIVERY_DEGRADED",
            "message": f"Срок поставки оригинального OEM превышает критический порог ({min(etas)} дн. > {max_acceptable_eta} дн.)."
        }

    return {
        "is_unavailable": False,
        "reason_code": "OEM_AVAILABLE",
        "message": "Оригинал доступен в достаточном количестве."
    }


def evaluate_analog_risk(
    brand: str,
    interchange_type: str = "direct",
    is_safety_related: bool = False,
    oem_price: Optional[float] = None,
    analog_price: Optional[float] = None,
    oem_eta: Optional[int] = None,
    analog_eta: Optional[int] = None,
) -> dict[str, Any]:
    """
    Compute risk score (0-100%) and risk factors for an analog part.
    """
    tier, base_risk = classify_brand_tier(brand)
    risk_score = base_risk
    risk_factors = []

    # Interchange Penalty
    if interchange_type == "conditional":
        risk_score += 15
        risk_factors.append("Условная заменяемость (требуется адаптер/проставка)")
    elif interchange_type == "kit":
        risk_score += 10
        risk_factors.append("Замена в составе комплекта")
    elif interchange_type == "unknown":
        risk_score += 25
        risk_factors.append("Неверифицированный тип кросса")

    # Safety Penalty
    if is_safety_related:
        if tier in {"BUDGET", "SPEC_MATCH"}:
            risk_score += 30
            risk_factors.append("Критическая деталь безопасности (Тормоза/Рулевое) от бюджетного бренда")
        else:
            risk_score += 5
            risk_factors.append("Узел повышенной ответственности")

    # Price Delta Calculation
    price_delta_percent = None
    if oem_price and analog_price and oem_price > 0:
        price_delta_percent = round(((analog_price - oem_price) / oem_price) * 100.0, 2)
        if price_delta_percent < -70:
            risk_score += 20
            risk_factors.append("Аномально низкая цена (подозрение на фальсификат >70% дисконт)")

    # ETA Delta Calculation
    eta_delta_days = None
    if oem_eta is not None and analog_eta is not None:
        eta_delta_days = analog_eta - oem_eta

    final_risk_score = min(100, max(0, risk_score))
    
    requires_human_approval = False
    if is_safety_related and tier in {"BUDGET", "SPEC_MATCH"}:
        requires_human_approval = True
    elif final_risk_score >= 40:
        requires_human_approval = True

    return {
        "quality_tier": tier,
        "risk_score": final_risk_score,
        "risk_factors": risk_factors,
        "price_delta_percent": price_delta_percent,
        "eta_delta_days": eta_delta_days,
        "requires_human_approval": requires_human_approval,
    }


def rank_and_select_analogs(
    session: Session,
    position_id: str,
    tenant_id: str,
    is_safety_related: bool = False
) -> list[dict[str, Any]]:
    """
    Fetch all AnalogCandidate records for a position, classify, score, and rank them.
    Returns ranked candidates sorted by suitability (lowest risk, best price delta).
    """
    analogs = session.exec(
        select(AnalogCandidate).where(
            AnalogCandidate.position_id == position_id,
            AnalogCandidate.tenant_id == tenant_id,
        )
    ).all()

    results = []
    for analog in analogs:
        eval_result = evaluate_analog_risk(
            brand=analog.brand,
            interchange_type=analog.interchange_type,
            is_safety_related=is_safety_related
        )
        
        # Update analog model in DB
        analog.quality_tier = eval_result["quality_tier"]
        analog.risk_score = eval_result["risk_score"]
        analog.risk_factors_json = json.dumps(eval_result["risk_factors"], ensure_ascii=False)
        analog.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(analog)

        results.append({
            "candidate_id": analog.candidate_id,
            "article": analog.article,
            "brand": analog.brand,
            "quality_tier": analog.quality_tier,
            "risk_score": analog.risk_score,
            "risk_factors": eval_result["risk_factors"],
            "requires_human_approval": eval_result["requires_human_approval"],
            "manual_review_status": analog.manual_review_status,
        })

    results.sort(key=lambda x: (x["risk_score"], x["brand"]))
    session.commit()
    return results
