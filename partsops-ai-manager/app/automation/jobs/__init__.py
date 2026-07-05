"""Jobs package — one entry point per file, registered with the registry."""

__all__ = [
    "intake_collect_job",
    "intake_validate_job",
    "intake_validate_vin_job",
    "intake_dedupe_job",
    "intake_extract_intent_job",
    "supplier_match_job",
    "supplier_validate_job",
    "quote_collect_job",
    "quote_evaluate_job",
    "quote_policy_check_job",
    "po_create_job",
    "erp_sync_job",
    "erp_sync_retry_job",
    "notify_owner_job",
    "escalate_stalled_job",
    "golden_sample_job",
    "archive_close_job",
    "dead_letter_cleanup_job",
    "metrics_refresh_job",
]
