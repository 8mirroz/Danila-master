"""Supplier Reliability Recalculation Job — updates supplier scores based on reliability logs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from sqlmodel import Session, select

from app.automation.context import AutomationContext
from models import SupplierReliabilityLog
from suppliers import Supplier

logger = logging.getLogger("automation.jobs.supplier_recalc")

def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True}

    suppliers = session.exec(select(Supplier)).all()
    updated = 0

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ninety_days_ago = now - timedelta(days=90)

    for supplier in suppliers:
        logs = session.exec(
            select(SupplierReliabilityLog)
            .where(SupplierReliabilityLog.supplier_id == supplier.supplier_id)
            .where(SupplierReliabilityLog.logged_at >= ninety_days_ago)
        ).all()
        
        if not logs:
            continue
            
        avg_score = sum(log.reliability_score for log in logs) / len(logs)
        new_score = max(0.0, min(1.0, round(avg_score, 4)))
        
        if abs(supplier.reliability_score - new_score) > 0.0001:
            supplier.reliability_score = new_score
            session.add(supplier)
            updated += 1
            
    if updated > 0:
        session.commit()

    return {"ok": True, "recalculated_count": updated}
