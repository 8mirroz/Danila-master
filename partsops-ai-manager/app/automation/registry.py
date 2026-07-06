"""
Registry — typed job and pipeline registry.

Registration is explicit, not auto-discovery. Keeps import graph tight
and makes `run_job(name)` deterministic.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger("automation.registry")

JobFunc = Callable[[Any], dict]
PipelineFunc = Callable[[Any], dict]

JOB_REGISTRY: Dict[str, JobFunc] = {}
PIPELINE_REGISTRY: Dict[str, PipelineFunc] = {}


def register_job(name: str, func: JobFunc) -> JobFunc:
    JOB_REGISTRY[name] = func
    logger.debug("Registered job %s", name)
    return func


def register_pipeline(name: str, func: PipelineFunc) -> PipelineFunc:
    PIPELINE_REGISTRY[name] = func
    logger.debug("Registered pipeline %s", name)
    return func


def get_job(name: str) -> JobFunc:
    try:
        return JOB_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown job {name!r}. Available: {sorted(JOB_REGISTRY)}") from exc


def list_jobs() -> List[str]:
    return sorted(JOB_REGISTRY)


def list_pipelines() -> List[str]:
    return sorted(PIPELINE_REGISTRY)


try:
    from app.automation.jobs import (
        archive_close_job,
        dead_letter_cleanup_job,
        erp_sync_job,
        erp_sync_retry_job,
        escalate_stalled_job,
        golden_sample_job,
        intake_collect_job,
        intake_dedupe_job,
        intake_extract_intent_job,
        intake_validate_job,
        intake_validate_vin_job,
        metrics_refresh_job,
        notify_owner_job,
        po_create_job,
        quote_collect_job,
        quote_evaluate_job,
        quote_policy_check_job,
        supplier_match_job,
        supplier_validate_job,
        auto_advance_job,
        sla_watchdog_job,
        supplier_recalc_job,
        golden_regression_job,
        price_snapshot_job,
    )

    def _init_registry() -> None:
        register_job("archive_close", archive_close_job.run)
        register_job("dead_letter_cleanup", dead_letter_cleanup_job.run)
        register_job("erp_sync", erp_sync_job.run)
        register_job("erp_sync_retry", erp_sync_retry_job.run)
        register_job("escalate_stalled", escalate_stalled_job.run)
        register_job("golden_sample", golden_sample_job.run)
        register_job("intake_collect", intake_collect_job.run)
        register_job("intake_dedupe", intake_dedupe_job.run)
        register_job("intake_extract_intent", intake_extract_intent_job.run)
        register_job("intake_validate", intake_validate_job.run)
        register_job("intake_validate_vin", intake_validate_vin_job.run)
        register_job("metrics_refresh", metrics_refresh_job.run)
        register_job("notify_owner", notify_owner_job.run)
        register_job("po_create", po_create_job.run)
        register_job("quote_collect", quote_collect_job.run)
        register_job("quote_evaluate", quote_evaluate_job.run)
        register_job("quote_policy_check", quote_policy_check_job.run)
        register_job("supplier_match", supplier_match_job.run)
        register_job("supplier_validate", supplier_validate_job.run)
        register_job("auto_advance", auto_advance_job.run)
        register_job("sla_watchdog", sla_watchdog_job.run)
        register_job("supplier_recalc", supplier_recalc_job.run)
        register_job("golden_regression", golden_regression_job.run)
        register_job("price_snapshot", price_snapshot_job.run)

    _init_registry()
except Exception as exc:  # noqa: BLE001
    logger.debug("Registry bootstrap skipped: %s", exc)
