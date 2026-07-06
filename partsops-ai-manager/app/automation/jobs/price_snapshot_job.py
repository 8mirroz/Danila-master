"""Price Snapshot Job — records current catalog item prices into PriceHistoryLedger."""
from __future__ import annotations

import logging
from typing import Any, Dict
from sqlmodel import Session, select

from app.automation.context import AutomationContext
from models import PriceHistoryLedger
from suppliers import SupplierCatalogItem

logger = logging.getLogger("automation.jobs.price_snapshot")

def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True}

    catalog_items = session.exec(
        select(SupplierCatalogItem).where(SupplierCatalogItem.tenant_id == context.tenant_id)
    ).all()

    recorded = 0
    for item in catalog_items:
        ledger_entry = PriceHistoryLedger(
            tenant_id=context.tenant_id,
            catalog_id=str(item.id),
            price=float(item.price),
            currency="RUB",
        )
        session.add(ledger_entry)
        recorded += 1

    if recorded > 0:
        session.commit()

    return {"ok": True, "recorded_count": recorded}
