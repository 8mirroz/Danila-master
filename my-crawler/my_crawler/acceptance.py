"""
Evidence and acceptance invariants for crawler records.

Every successful record must satisfy required fields.
Every site success must have at least one record per hit article,
every screenshot path must exist and be non-empty.
Zero-record success is treated as FAIL, never as an empty success.
"""

import os
from typing import Optional

from .report import ArticleOutcome, SiteOutcome, MISS_REASON_CATEGORIES

# ---------------------------------------------------------------------------
# Required fields per record  (exact keys from route handlers)
# ---------------------------------------------------------------------------
REQUIRED_RECORD_FIELDS = frozenset({
    "site",
    "search_article",
    "brand",
    "article",
    "price",
    "source_url",
    "captured_at",
    "screenshot_path",
})


# ---------------------------------------------------------------------------
# Record validation
# ---------------------------------------------------------------------------

def validate_record(record: dict) -> list[str]:
    """Return a list of missing or invalid field names. Empty list = valid."""
    issues: list[str] = []
    for field in REQUIRED_RECORD_FIELDS:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(field)
    return issues


def record_passes_evidence_check(record: dict) -> tuple[bool, str]:
    """Verify screenshot_path exists and is non-empty. Returns (pass, reason)."""
    screenshot_path = record.get("screenshot_path", "")
    if not screenshot_path:
        return False, "missing screenshot_path"
    if not os.path.isfile(screenshot_path):
        return False, f"screenshot file not found: {screenshot_path}"
    if os.path.getsize(screenshot_path) == 0:
        return False, f"screenshot file is empty: {screenshot_path}"
    return True, ""


# ---------------------------------------------------------------------------
# Site-level validation
# ---------------------------------------------------------------------------

def compute_article_outcomes(
    site: str,
    records: list[dict],
    articles_input: list[str],
    miss_reasons_map: Optional[dict[str, str]] = None,
    miss_details_map: Optional[dict[str, str]] = None,
) -> list[ArticleOutcome]:
    """Build per-article coverage outcomes.

    Args:
        site: Site label (exist, autodoc, rossko).
        records: Parsed records for this site.
        articles_input: Full list of articles that were searched.
        miss_reasons_map: Optional map of {article: miss_reason} from route handler classification.
        miss_details_map: Optional map of {article: miss_detail} for human-readable context.

    Returns:
        List of ArticleOutcome, one per input article.
    """
    if miss_reasons_map is None:
        miss_reasons_map = {}
    if miss_details_map is None:
        miss_details_map = {}

    # Group records by search_article
    records_by_article: dict[str, list[dict]] = {}
    for rec in records:
        art = rec.get("search_article", "")
        records_by_article.setdefault(art, []).append(rec)

    outcomes: list[ArticleOutcome] = []
    for article in articles_input:
        article_records = records_by_article.get(article, [])
        found = len(article_records) > 0
        miss_reason = miss_reasons_map.get(article, "")
        miss_detail = miss_details_map.get(article, "")

        # Ensure miss_reason is a valid category
        if miss_reason and miss_reason not in MISS_REASON_CATEGORIES:
            miss_reason = "unknown"

        outcomes.append(ArticleOutcome(
            search_article=article,
            found=found,
            records_count=len(article_records),
            miss_reason=miss_reason if not found else "",
            miss_detail=miss_detail if not found else "",
        ))

    return outcomes


def validate_site_records(
    site: str,
    records: list[dict],
    articles_input: list[str],
    miss_reasons_map: Optional[dict[str, str]] = None,
    miss_details_map: Optional[dict[str, str]] = None,
) -> tuple[list[ArticleOutcome], list[str]]:
    """Validate all records for a site. Returns (article_outcomes, warnings)."""
    warnings: list[str] = []

    # 1. Check each record for required fields
    for i, rec in enumerate(records):
        missing = validate_record(rec)
        if missing:
            warnings.append(f"record {i} missing fields: {', '.join(missing)}")

    # 2. Check screenshot health
    ok_count = 0
    missing_count = 0
    for rec in records:
        passed, reason = record_passes_evidence_check(rec)
        if passed:
            ok_count += 1
        else:
            missing_count += 1
            warnings.append(f"evidence issue: {reason}")

    # 3. Compute article outcomes
    article_outcomes = compute_article_outcomes(
        site, records, articles_input, miss_reasons_map, miss_details_map,
    )

    # 4. Detect zero-record success (empty success with no exceptions)
    if not records and not warnings:
        warnings.append("site finished with zero records and no explicit errors")

    return article_outcomes, warnings


# ---------------------------------------------------------------------------
# Site-status computation
# ---------------------------------------------------------------------------

def compute_site_status(
    site_outcome: SiteOutcome,
) -> str:
    """Determine OK / WARN / FAIL for a site.

    Rules:
    - FAIL if zero records and no fallback path successfully recovered data.
    - FAIL if all articles missed.
    - WARN if any article missed but at least one found, or fallback was used.
    - OK if every article found with valid records and evidence.
    """
    if site_outcome.articles_total == 0:
        # No articles expected; use records as proxy
        if site_outcome.records_total == 0 and site_outcome.errors:
            return "FAIL"
        return "OK"

    # All articles hit with records
    all_hit = site_outcome.articles_hit == site_outcome.articles_total and site_outcome.articles_total > 0
    any_hit = site_outcome.articles_hit > 0
    any_error = bool(site_outcome.errors)
    fallback_used = bool(site_outcome.fallback_paths_used)

    if all_hit and not any_error and not fallback_used:
        return "OK"

    if any_hit and not any_error:
        # Partial coverage with no errors → WARN (missing articles + possibly fallback)
        return "WARN"

    if fallback_used and any_hit:
        # Proxy fallback recovered some data → WARN
        return "WARN"

    # Everything else is FAIL
    return "FAIL"


# ---------------------------------------------------------------------------
# Report-level invariants
# ---------------------------------------------------------------------------

def validate_report_invariants(
    site_outcomes: list[SiteOutcome],
) -> list[str]:
    """Check global invariants across the run report.

    Returns list of invariant violations (empty = all pass).
    """
    violations: list[str] = []
    for site in site_outcomes:
        if site.records_total == 0 and site.status == "OK":
            violations.append(
                f"INVARIANT VIOLATION: {site.site} has 0 records but status is OK"
            )
        if site.records_total == 0 and not site.errors:
            violations.append(
                f"INVARIANT VIOLATION: {site.site} has 0 records and no errors — "
                f"should be FAIL"
            )
        if site.screenshots_missing > 0 and site.status == "OK":
            violations.append(
                f"INVARIANT VIOLATION: {site.site} has {site.screenshots_missing} "
                f"missing screenshots but status is OK"
            )
    return violations