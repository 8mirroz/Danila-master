"""
Structured run-report data classes and serialization.

Defines the explicit OK / WARN / FAIL contract per site and globally,
and produces both machine-readable (JSON) and operator-readable (Markdown) artifacts.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Miss reason categories  (stable, bounded set)
# ---------------------------------------------------------------------------
MISS_REASON_CATEGORIES = frozenset({
    "no_results",
    "auth_required",
    "layout_changed",
    "network_error",
    "anti_bot",
    "evidence_failed",
    "card_shell_only",
    "search_empty",
    "unknown",
})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ArticleOutcome:
    """Coverage outcome for one (article × site) pair."""
    search_article: str
    found: bool
    records_count: int = 0
    miss_reason: str = ""                     # one of MISS_REASON_CATEGORIES
    miss_detail: str = ""                     # optional human-readable context


@dataclass
class SiteOutcome:
    """Aggregated outcome for one marketplace site."""
    site: str
    status: str                               # OK | WARN | FAIL
    requests_total: int = 0
    records_total: int = 0
    articles_total: int = 0
    articles_hit: int = 0
    articles_miss: int = 0
    screenshots_ok: int = 0
    screenshots_missing: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    remediation_commands: list[str] = field(default_factory=list)
    fallback_paths_used: list[str] = field(default_factory=list)
    article_outcomes: list[ArticleOutcome] = field(default_factory=list)


@dataclass
class RunReport:
    """Top-level report for one full crawler run."""
    overall_status: str                       # OK | WARN | FAIL
    started_at: str                           # ISO-8601
    finished_at: str                          # ISO-8601
    articles_input: list[str] = field(default_factory=list)
    sites: list[SiteOutcome] = field(default_factory=list)
    remediation_commands_global: list[str] = field(default_factory=list)
    env_contract: dict = field(default_factory=dict)  # snapshot of key env vars used


# ---------------------------------------------------------------------------
# Exit code contract  0 → OK,  10 → WARN,  20 → FAIL
# ---------------------------------------------------------------------------

STATUS_EXIT_MAP = {
    "OK": 0,
    "WARN": 10,
    "FAIL": 20,
}


def exit_code_for_status(status: str) -> int:
    return STATUS_EXIT_MAP.get(status, 20)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _default_serializer(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if hasattr(o, "__dict__"):
        return asdict(o)
    return str(o)


def generate_run_report_json(report: RunReport, path: str) -> str:
    """Write results/run_report.json. Returns absolute path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = json.loads(json.dumps(report, default=_default_serializer))
    # Manual asdict for proper dataclass recursion
    data = _report_to_dict(report)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return os.path.abspath(path)


def _report_to_dict(report: RunReport) -> dict:
    return {
        "overall_status": report.overall_status,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "articles_input": report.articles_input,
        "sites": [_site_to_dict(s) for s in report.sites],
        "remediation_commands_global": report.remediation_commands_global,
        "env_contract": report.env_contract,
    }


def _site_to_dict(site: SiteOutcome) -> dict:
    return {
        "site": site.site,
        "status": site.status,
        "requests_total": site.requests_total,
        "records_total": site.records_total,
        "articles_total": site.articles_total,
        "articles_hit": site.articles_hit,
        "articles_miss": site.articles_miss,
        "screenshots_ok": site.screenshots_ok,
        "screenshots_missing": site.screenshots_missing,
        "warnings": site.warnings,
        "errors": site.errors,
        "remediation_commands": site.remediation_commands,
        "fallback_paths_used": site.fallback_paths_used,
        "article_outcomes": [
            {
                "search_article": a.search_article,
                "found": a.found,
                "records_count": a.records_count,
                "miss_reason": a.miss_reason,
                "miss_detail": a.miss_detail,
            }
            for a in site.article_outcomes
        ],
    }


def generate_run_summary_md(report: RunReport, path: str) -> str:
    """Write results/run_summary.md. Returns absolute path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines: list[str] = []
    lines.append("# PartsOps Crawler Run Summary")
    lines.append("")
    lines.append(f"- **Overall Status**: {report.overall_status}")
    lines.append(f"- **Started**: {report.started_at}")
    lines.append(f"- **Finished**: {report.finished_at}")
    lines.append(f"- **Articles Input**: {len(report.articles_input)}")
    lines.append("")

    for i, site in enumerate(report.sites):
        lines.append(f"## {i+1}. {site.site}")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Status | {site.status} |")
        lines.append(f"| Requests | {site.requests_total} |")
        lines.append(f"| Records | {site.records_total} |")
        lines.append(f"| Articles Expected | {site.articles_total} |")
        lines.append(f"| Articles Hit | {site.articles_hit} |")
        lines.append(f"| Articles Missed | {site.articles_miss} |")
        lines.append(f"| Screenshots OK | {site.screenshots_ok} |")
        lines.append(f"| Screenshots Missing | {site.screenshots_missing} |")
        if site.fallback_paths_used:
            lines.append(f"| Fallback Paths Used | {', '.join(site.fallback_paths_used)} |")
        lines.append("")

        if site.article_outcomes:
            lines.append("### Article Coverage")
            lines.append("")
            lines.append("| Article | Found | Records | Miss Reason |")
            lines.append("|---------|-------|---------|-------------|")
            for ao in site.article_outcomes:
                lines.append(
                    f"| {ao.search_article} | {'✓' if ao.found else '✗'} | "
                    f"{ao.records_count} | {ao.miss_reason or '-'} |"
                )
            lines.append("")

        if site.warnings:
            lines.append("### Warnings")
            for w in site.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if site.errors:
            lines.append("### Errors")
            for e in site.errors:
                lines.append(f"- {e}")
            lines.append("")

        if site.remediation_commands:
            lines.append("### Remediation")
            for cmd in site.remediation_commands:
                lines.append(f"- `{cmd}`")
            lines.append("")

    if report.remediation_commands_global:
        lines.append("## Global Remediation Commands")
        lines.append("")
        for cmd in report.remediation_commands_global:
            lines.append(f"- `{cmd}`")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return os.path.abspath(path)


def write_exit_code(report: RunReport, path: str) -> int:
    """Write exit-code file and return the numeric code."""
    code = exit_code_for_status(report.overall_status)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(code))
    return code


# ---------------------------------------------------------------------------
# Terminal output helpers
# ---------------------------------------------------------------------------

def print_site_summary(site: SiteOutcome) -> None:
    """Short per-site terminal summary."""
    status_icon = {"OK": "✓", "WARN": "⚠", "FAIL": "✗"}.get(site.status, "?")
    print(f"  [{status_icon}] {site.site}: {site.status}  "
          f"(records={site.records_total}, "
          f"articles_hit={site.articles_hit}/{site.articles_total}, "
          f"screenshots={site.screenshots_ok})")
    if site.fallback_paths_used:
        print(f"       fallbacks: {', '.join(site.fallback_paths_used)}")
    if site.warnings:
        for w in site.warnings:
            print(f"       ⚠ {w}")
    if site.errors:
        for e in site.errors:
            print(f"       ✗ {e}")


def print_global_verdict(report: RunReport) -> None:
    """Single decisive verdict line."""
    icon = {"OK": "✓", "WARN": "⚠", "FAIL": "✗"}.get(report.overall_status, "?")
    print("")
    print("=" * 60)
    print(f"  VERDICT: {icon}  {report.overall_status}")
    print("=" * 60)


def print_remediation_section(report: RunReport) -> None:
    """Print remediation commands if status is WARN or FAIL."""
    all_cmds = list(report.remediation_commands_global)
    for site in report.sites:
        all_cmds.extend(site.remediation_commands)
    if all_cmds:
        print("")
        print("Remediation commands:")
        for cmd in all_cmds:
            print(f"  $ {cmd}")
        print("")