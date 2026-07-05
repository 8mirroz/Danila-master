CRON_REGISTRY = {
    "every_minute": ["queue_health_check", "stuck_jobs_detector", "active_run_timeout_check"],
    "every_5_minutes": ["supplier_api_health_check", "pending_approval_reminder", "budget_guard_check"],
    "every_15_minutes": ["stale_price_list_detector", "failed_tool_call_retry", "inbox_deduplication"],
    "hourly": ["supplier_sync", "eval_sample_runner", "admin_correction_collector"],
    "daily": ["supplier_reliability_recalculate", "cost_report", "failed_match_report"],
}

def list_jobs():
    return CRON_REGISTRY
