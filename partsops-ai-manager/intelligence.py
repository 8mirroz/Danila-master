"""
PartsOps AI Manager v3 — Intelligence Layer (Phase 4)
Handles Price History Ledger median calculations, Supplier Reliability updates,
Return/Warranty Risk assessment, and automatic Purchase Order (PO) draft generation.
"""
import json
import statistics
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlmodel import Session, select

from models import PriceHistoryLedger, SupplierReliabilityLog, PartRequest
from suppliers import Supplier, SupplierCatalogItem, Invoice


def get_90d_median_price(catalog_id: str, session: Session) -> Optional[float]:
    """
    Calculate the 90-day median price for a specific catalog item
    from the append-only PriceHistoryLedger.
    """
    cutoff = datetime.utcnow() - timedelta(days=90)
    statement = select(PriceHistoryLedger).where(
        PriceHistoryLedger.catalog_id == catalog_id,
        PriceHistoryLedger.recorded_at >= cutoff
    )
    records = session.exec(statement).all()
    if not records:
        return None
        
    prices = [r.price for r in records]
    return round(statistics.median(prices), 2)


def record_price_update(catalog_id: str, price: float, currency: str, session: Session):
    """Append a new price entry to the PriceHistoryLedger."""
    ledger_entry = PriceHistoryLedger(
        catalog_id=catalog_id,
        price=price,
        currency=currency,
        recorded_at=datetime.utcnow()
    )
    session.add(ledger_entry)
    session.commit()


def update_supplier_reliability(
    supplier_id: str,
    new_score: float,
    event_type: str,
    reason: str,
    session: Session
):
    """
    Update supplier reliability score: writes an audit event to
    SupplierReliabilityLog and mutates the current score on the Supplier record.
    """
    # 1. Mutate Supplier record
    statement = select(Supplier).where(Supplier.supplier_id == supplier_id)
    supplier = session.exec(statement).first()
    if supplier:
        old_score = supplier.reliability_score
        supplier.reliability_score = round(max(0.0, min(1.0, new_score)), 2)
        session.add(supplier)
        
        # 2. Append event to audit log
        log_entry = SupplierReliabilityLog(
            supplier_id=supplier_id,
            reliability_score=supplier.reliability_score,
            event_type=event_type,
            reason=f"{reason} (изменено с {old_score:.2f} на {supplier.reliability_score:.2f})",
            logged_at=datetime.utcnow()
        )
        session.add(log_entry)
        session.commit()


def assess_return_risk(part_name: str, brand: str) -> Dict:
    """
    Assess warranty/return risk tier based on catalog category.
    Returns risk level ("low" | "medium" | "high") and returnable policy boolean.
    """
    part_lower = part_name.lower()
    # High-risk safety-critical or non-returnable aftermarket categories
    if "амортизатор" in part_lower or "рычаг" in part_lower or "рейка" in part_lower:
        return {"risk_level": "high", "is_non_returnable": True, "policy_margin": 0.20}
    elif "электрика" in part_lower or "свечи" in part_lower or "датчик" in part_lower:
        return {"risk_level": "medium", "is_non_returnable": True, "policy_margin": 0.18}
    else:
        return {"risk_level": "low", "is_non_returnable": False, "policy_margin": 0.12}


def generate_purchase_order_drafts(request_id: str, session: Session) -> List[Dict]:
    """
    Generates draft purchase orders for the client request's accepted matched parts,
    grouped by supplier to avoid multiple shipments.
    """
    statement = select(PartRequest).where(PartRequest.request_id == request_id)
    req = session.exec(statement).first()
    if not req or not req.parts_json:
        return []

    try:
        parts = json.loads(req.parts_json)
    except Exception:
        parts = []

    po_drafts = []
    # Group items by supplier_id
    items_by_supplier = {}
    for part in parts:
        best_match = part.get("best_match")
        supplier = part.get("supplier")
        if best_match and supplier:
            sup_id = supplier["supplier_id"]
            if sup_id not in items_by_supplier:
                items_by_supplier[sup_id] = []
            items_by_supplier[sup_id].append({
                "catalog_id": best_match["catalog_id"],
                "name": best_match["name"],
                "oem": best_match.get("oem_number", ""),
                "price": best_match["price"],
                "quantity": part.get("quantity", 1)
            })

    for sup_id, items in items_by_supplier.items():
        total_cost = sum(item["price"] * item["quantity"] for item in items)
        po_drafts.append({
            "po_number": f"PO-{request_id}-{sup_id}",
            "request_id": request_id,
            "supplier_id": sup_id,
            "items": items,
            "total_cost": total_cost,
            "status": "DRAFT",
            "created_at": datetime.utcnow().isoformat()
        })

    return po_drafts
