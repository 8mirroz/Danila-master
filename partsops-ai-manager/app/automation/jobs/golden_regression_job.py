"""Golden Regression Job — calculates system accuracy and validates regression."""
from __future__ import annotations

import logging
from typing import Any, Dict
from sqlmodel import Session

from app.automation.context import AutomationContext
from learning import calculate_system_accuracy

logger = logging.getLogger("automation.jobs.golden_regression")

def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True}
        
    metrics = calculate_system_accuracy(session, context.tenant_id)
    logger.info("Golden Regression Metrics recalculated: %s", metrics)
    return {"ok": True, "metrics": metrics}
