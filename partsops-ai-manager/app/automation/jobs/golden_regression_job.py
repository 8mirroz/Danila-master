"""Golden Regression Job — accuracy metrics + threshold alerts.

Writes a JSON report under storage/exports when configured and flags
regression when accuracy drops below PARTSOPS_GOLDEN_MIN_ACCURACY (default 70).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sqlmodel import Session

from app.automation.context import AutomationContext
from learning import calculate_system_accuracy

logger = logging.getLogger("automation.jobs.golden_regression")

DEFAULT_MIN_ACCURACY = float(os.environ.get("PARTSOPS_GOLDEN_MIN_ACCURACY", "70.0"))


def run(session: Session, context: AutomationContext) -> Dict[str, Any]:
    if context.dry_run:
        return {"ok": True, "dry_run": True, "metrics": None}

    metrics = calculate_system_accuracy(session, context.tenant_id)
    accuracy = float(metrics.get("accuracy_percent") or 0.0)
    min_acc = float(context.payload.get("min_accuracy") or DEFAULT_MIN_ACCURACY)
    regression = accuracy < min_acc and int(metrics.get("total_requests") or 0) > 0

    report = {
        "tenant_id": context.tenant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "min_accuracy": min_acc,
        "regression": regression,
        "status": "regression" if regression else "ok",
    }

    report_path = None
    try:
        export_dir = Path(
            os.environ.get(
                "PARTSOPS_GOLDEN_REPORT_DIR",
                str(Path(__file__).resolve().parents[3] / "storage" / "exports"),
            )
        )
        export_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = export_dir / f"golden_regression_{context.tenant_id}_{stamp}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(report_path)
    except Exception as exc:
        logger.warning("Could not write golden report file: %s", exc)

    if regression:
        logger.warning(
            "Golden regression ALERT tenant=%s accuracy=%.1f%% < %.1f%% corrections=%s",
            context.tenant_id,
            accuracy,
            min_acc,
            metrics.get("manual_corrections"),
        )
    else:
        logger.info("Golden Regression Metrics: %s", metrics)

    return {
        "ok": not regression,
        "metrics": metrics,
        "regression": regression,
        "min_accuracy": min_acc,
        "report_path": str(report_path) if report_path else None,
        "status": report["status"],
    }
