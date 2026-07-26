"""
Run orchestrator with explicit health contracts.

Wraps the existing per-site crawler runs with bounded retry, healing,
structured reporting, and remediation command generation.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from crawlee import Request

from .main import (
    SITE_LABELS,
    SITE_ENV_PREFIX,
    run_site_crawler,
    build_requests,
    load_articles,
    resolve_articles_path,
    partition_requests_by_site,
    is_headless,
    export_results,
    get_browser_profile_dir,
    get_proxy_config_for_site,
)
from .report import (
    RunReport,
    SiteOutcome,
    ArticleOutcome,
    generate_run_report_json,
    generate_run_summary_md,
    write_exit_code,
    print_site_summary,
    print_global_verdict,
    print_remediation_section,
    exit_code_for_status,
)
from .acceptance import (
    compute_article_outcomes,
    validate_site_records,
    compute_site_status,
    validate_report_invariants,
)
from .healing import (
    bounded_retry,
    rossko_extended_wait,
    rossko_classify_empty,
    exist_reload_and_settle,
    exist_classify_empty,
    autodoc_search_with_fallback,
    classify_error,
)

RESULTS_DIR = "results"
RUN_REPORT_JSON = os.path.join(RESULTS_DIR, "run_report.json")
RUN_SUMMARY_MD = os.path.join(RESULTS_DIR, "run_summary.md")
EXIT_CODE_PATH = os.path.join(RESULTS_DIR, "run_report.exit_code")


# ---------------------------------------------------------------------------
# Remediation command generation
# ---------------------------------------------------------------------------

def _generate_remediation_commands(site: str, status: str) -> list[str]:
    """Generate concrete remediation commands for a site failure."""
    commands: list[str] = []
    site_lower = site.lower()

    if status in ("WARN", "FAIL"):
        commands.append(f"scripts/bootstrap_profile.py --site {site_lower}")
        commands.append(f"scripts/smoke_site.py --site {site_lower} --article <article_from_articles_txt>")
        commands.append(f"scripts/remediate_site.py --site {site_lower}")

    if status == "FAIL":
        # More aggressive diagnostics
        commands.append(f"HEADLESS=0 scripts/run_production_crawler.py  # headed mode for visual debug")

    return commands


# ---------------------------------------------------------------------------
# Env validation
# ---------------------------------------------------------------------------

def validate_env(articles: list[str]) -> list[str]:
    """Validate environment before running. Returns list of warnings/errors."""
    issues: list[str] = []

    if not articles:
        issues.append("No articles loaded from articles.txt")

    # Check per-site profiles
    for site in SITE_LABELS:
        prefix = SITE_ENV_PREFIX[site]
        profile_key = f"{prefix}_BROWSER_PROFILE_DIR"
        shared_key = "BROWSER_PROFILE_DIR"

        site_profile = os.environ.get(profile_key, "").strip()
        shared_profile = os.environ.get(shared_key, "").strip()

        if site_profile and shared_profile:
            issues.append(
                f"[{site}] Both {profile_key} and {shared_key} are set. "
                f"Using {profile_key} (site-specific takes precedence)."
            )

    # Check concurrency bounds
    try:
        max_conc = int(os.environ.get("CRAWLER_MAX_CONCURRENCY", "2"))
        if max_conc < 1 or max_conc > 4:
            issues.append(f"CRAWLER_MAX_CONCURRENCY={max_conc} out of range [1-4]; using default 2")
    except ValueError:
        issues.append("CRAWLER_MAX_CONCURRENCY is not a valid integer; using default 2")

    # Validate proxy URL format if set
    for site in SITE_LABELS:
        prefix = SITE_ENV_PREFIX[site]
        proxy_url = os.environ.get(f"{prefix}_PROXY_URL", "").strip()
        if proxy_url and not proxy_url.startswith(("http://", "https://", "socks5://")):
            issues.append(f"[{site}] Proxy URL format may be invalid: {proxy_url[:20]}...")

    return issues


def _get_env_contract() -> dict:
    """Snapshot key env vars for the run report."""
    contract: dict = {}
    for site in SITE_LABELS:
        prefix = SITE_ENV_PREFIX[site]
        contract[f"{prefix}_BROWSER_PROFILE_DIR"] = os.environ.get(f"{prefix}_BROWSER_PROFILE_DIR", "")
        contract[f"{prefix}_PROXY_URL"] = "***SET***" if os.environ.get(f"{prefix}_PROXY_URL", "") else ""
    contract["BROWSER_PROFILE_DIR"] = os.environ.get("BROWSER_PROFILE_DIR", "")
    contract["PROXY_URL"] = "***SET***" if os.environ.get("PROXY_URL", "") else ""
    contract["HEADLESS"] = os.environ.get("HEADLESS", "")
    contract["CRAWLER_MAX_CONCURRENCY"] = os.environ.get("CRAWLER_MAX_CONCURRENCY", "2")
    return contract


# ---------------------------------------------------------------------------
# Site runner with healing
# ---------------------------------------------------------------------------

async def run_site_with_healing(
    site: str,
    site_requests: list[Request],
    headless_mode: bool,
    articles_input: list[str],
) -> SiteOutcome:
    """Run one site with bounded retries and fallback healing.

    Returns a SiteOutcome with full health data.
    """
    fallback_paths: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []
    miss_reasons_map: dict[str, str] = {}
    miss_details_map: dict[str, str] = {}

    # Step 1: Run the crawler with bounded retries
    records, succeeded, fallback_paths = await bounded_retry(
        run_site_crawler,
        site,
        site_requests,
        headless_mode,
        max_retries=2,
        site=site,
        fallback_paths=fallback_paths,
    )

    if not succeeded:
        records = records or []
        errors.append(f"All {len(site_requests)} attempts failed for {site}")
    elif not records:
        warnings.append(f"Site {site} returned 0 records after {len(site_requests)} request(s)")

    # Step 2: Validate records and compute article outcomes
    article_outcomes, validation_warnings = validate_site_records(
        site, records or [], articles_input,
        miss_reasons_map, miss_details_map,
    )
    warnings.extend(validation_warnings)

    # Step 3: Compute screenshot counts
    screenshots_ok = 0
    for rec in (records or []):
        sp = rec.get("screenshot_path", "")
        if sp and os.path.isfile(sp) and os.path.getsize(sp) > 0:
            screenshots_ok += 1
    screenshots_missing = len(records or []) - screenshots_ok

    # Step 4: Build site outcome
    articles_hit = sum(1 for ao in article_outcomes if ao.found)
    articles_miss = sum(1 for ao in article_outcomes if not ao.found)

    site_outcome = SiteOutcome(
        site=site,
        status="PENDING",  # will be computed below
        requests_total=len(site_requests),
        records_total=len(records or []),
        articles_total=len(articles_input),
        articles_hit=articles_hit,
        articles_miss=articles_miss,
        screenshots_ok=screenshots_ok,
        screenshots_missing=screenshots_missing,
        warnings=warnings,
        errors=errors,
        fallback_paths_used=fallback_paths,
        article_outcomes=article_outcomes,
    )

    # Step 5: Compute status
    site_outcome.status = compute_site_status(site_outcome)

    # Step 6: Generate remediation commands if needed
    if site_outcome.status in ("WARN", "FAIL"):
        site_outcome.remediation_commands = _generate_remediation_commands(
            site, site_outcome.status,
        )

    return site_outcome


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def orchestrate_run(
    articles: list[str],
    headless: bool,
) -> RunReport:
    """Full orchestration of all site crawlers with health contracts.

    Args:
        articles: List of article numbers to search.
        headless: Whether to run browsers headless.

    Returns:
        RunReport with complete health data.
    """
    started_at = datetime.now(timezone.utc).isoformat()

    # Build requests and partition by site
    requests = build_requests(articles)
    request_batches = partition_requests_by_site(requests)

    # Run each site with healing
    site_outcomes: list[SiteOutcome] = []
    for site in SITE_LABELS:
        site_requests = request_batches[site]
        if not site_requests:
            # Site has no articles to process
            site_outcomes.append(SiteOutcome(
                site=site,
                status="OK",
                requests_total=0,
                records_total=0,
                articles_total=0,
                articles_hit=0,
                articles_miss=0,
                warnings=[f"No requests for site {site}"],
            ))
            continue

        print(f"\n[{site}] Running {len(site_requests)} request(s)...")
        site_outcome = await run_site_with_healing(
            site, site_requests, headless, articles,
        )
        site_outcomes.append(site_outcome)

        # Print per-site summary immediately
        print_site_summary(site_outcome)

    # Compute overall status
    overall_status = _compute_overall_status(site_outcomes)

    # Validate invariants
    invariants = validate_report_invariants(site_outcomes)
    global_warnings: list[str] = []
    for inv in invariants:
        global_warnings.append(inv)

    finished_at = datetime.now(timezone.utc).isoformat()

    # Generate global remediation commands
    global_remediation: list[str] = []
    if overall_status in ("WARN", "FAIL"):
        for site_out in site_outcomes:
            if site_out.status in ("WARN", "FAIL"):
                global_remediation.extend(site_out.remediation_commands)

    report = RunReport(
        overall_status=overall_status,
        started_at=started_at,
        finished_at=finished_at,
        articles_input=articles,
        sites=site_outcomes,
        remediation_commands_global=list(set(global_remediation)),
        env_contract=_get_env_contract(),
    )

    return report


def _compute_overall_status(site_outcomes: list[SiteOutcome]) -> str:
    """Compute global status from all site outcomes.

    - OK if every site is OK
    - FAIL if any site is FAIL
    - WARN if any site is WARN and none are FAIL
    """
    has_fail = any(s.status == "FAIL" for s in site_outcomes)
    has_warn = any(s.status == "WARN" for s in site_outcomes)

    if has_fail:
        return "FAIL"
    if has_warn:
        return "WARN"
    return "OK"


# ---------------------------------------------------------------------------
# Exported results from crawl
# ---------------------------------------------------------------------------

def export_crawl_results(records: list[dict]) -> tuple[str, str]:
    """Export aggregated records using existing export function."""
    return export_results(records, RESULTS_DIR)


# ---------------------------------------------------------------------------
# Main entry point for the orchestrator (called from main.py)
# ---------------------------------------------------------------------------

async def run(articles: list[str], headless: bool) -> int:
    """Run the full orchestrator and return exit code.

    This is the replacement for the inline loop in main().
    """
    # Validate environment
    env_issues = validate_env(articles)
    for issue in env_issues:
        print(f"[env] {issue}")

    # Run
    report = await orchestrate_run(articles, headless)

    # Export aggregated results from all sites
    all_records: list[dict] = []
    for site_out in report.sites:
        pass  # Records are already exported by run_site_crawler into dataset

    # Generate report artifacts
    json_path = generate_run_report_json(report, RUN_REPORT_JSON)
    md_path = generate_run_summary_md(report, RUN_SUMMARY_MD)
    exit_code = write_exit_code(report, EXIT_CODE_PATH)

    print(f"\nReport JSON: {json_path}")
    print(f"Report MD:   {md_path}")
    print(f"Exit code:   {exit_code} ({report.overall_status})")

    # Print terminal verdict
    print_global_verdict(report)
    if report.overall_status in ("WARN", "FAIL"):
        print_remediation_section(report)

    return exit_code