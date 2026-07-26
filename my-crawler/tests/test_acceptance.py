"""Tests for the acceptance module — record validation, invariants, screenshot checks."""

import os
import tempfile
from my_crawler.acceptance import (
    validate_record,
    record_passes_evidence_check,
    compute_article_outcomes,
    validate_site_records,
    compute_site_status,
    validate_report_invariants,
)
from my_crawler.report import SiteOutcome, ArticleOutcome


class TestRecordValidation:
    def test_valid_record_passes(self):
        record = {
            "site": "exist.ru",
            "search_article": "OC90",
            "brand": "BOSCH",
            "article": "OC90",
            "price": "4500 ₽",
            "source_url": "https://exist.ru/Price/?pcode=OC90",
            "captured_at": "2026-07-24T12:00:00",
            "screenshot_path": "/tmp/screenshot.png",
        }
        assert validate_record(record) == []

    def test_missing_field_fails(self):
        record = {
            "site": "exist.ru",
            "search_article": "OC90",
            "article": "OC90",
            "price": "4500 ₽",
        }
        issues = validate_record(record)
        assert "brand" in issues
        assert "source_url" in issues
        assert "captured_at" in issues
        assert "screenshot_path" in issues

    def test_empty_strings_fail(self):
        record = {
            "site": "",
            "search_article": "OC90",
            "brand": "",
            "article": "OC90",
            "price": "",
            "source_url": "",
            "captured_at": "",
            "screenshot_path": "",
        }
        issues = validate_record(record)
        assert "site" in issues
        assert "brand" in issues
        assert "price" in issues
        assert "source_url" in issues
        assert "captured_at" in issues
        assert "screenshot_path" in issues


class TestEvidenceCheck:
    def test_missing_screenshot_path_fails(self):
        passed, reason = record_passes_evidence_check({"screenshot_path": ""})
        assert not passed
        assert "missing" in reason

    def test_nonexistent_file_fails(self):
        passed, reason = record_passes_evidence_check({"screenshot_path": "/nonexistent/path.png"})
        assert not passed
        assert "not found" in reason

    def test_existing_file_passes(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png data")
            path = f.name
        try:
            passed, reason = record_passes_evidence_check({"screenshot_path": path})
            assert passed
            assert reason == ""
        finally:
            os.unlink(path)

    def test_empty_file_fails(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        try:
            passed, reason = record_passes_evidence_check({"screenshot_path": path})
            assert not passed
            assert "empty" in reason
        finally:
            os.unlink(path)


class TestArticleOutcomes:
    def test_all_articles_found(self):
        records = [
            {"search_article": "OC90"},
            {"search_article": "OC90"},
            {"search_article": "W6103"},
        ]
        outcomes = compute_article_outcomes("exist", records, ["OC90", "W6103"])
        assert len(outcomes) == 2
        assert outcomes[0].found
        assert outcomes[0].records_count == 2
        assert outcomes[1].found
        assert outcomes[1].records_count == 1

    def test_partial_coverage(self):
        records = [
            {"search_article": "OC90"},
        ]
        outcomes = compute_article_outcomes("exist", records, ["OC90", "W6103"])
        assert len(outcomes) == 2
        assert outcomes[0].found
        assert outcomes[1].found == False

    def test_miss_reason_from_map(self):
        records = []
        miss_reasons = {"OC90": "search_empty", "W6103": "layout_changed"}
        outcomes = compute_article_outcomes("autodoc", records, ["OC90", "W6103"], miss_reasons_map=miss_reasons)
        assert outcomes[0].miss_reason == "search_empty"
        assert outcomes[1].miss_reason == "layout_changed"

    def test_invalid_miss_reason_defaults_to_unknown(self):
        records = []
        miss_reasons = {"OC90": "invalid_reason"}
        outcomes = compute_article_outcomes("autodoc", records, ["OC90"], miss_reasons_map=miss_reasons)
        assert outcomes[0].miss_reason == "unknown"


class TestSiteValidation:
    def test_valid_site_passes(self):
        records = [{"search_article": "OC90", "site": "exist.ru", "screenshot_path": "/tmp/test.png"}]
        outcomes, warnings = validate_site_records("exist", records, ["OC90"])
        assert len(outcomes) == 1
        assert outcomes[0].found

    def test_zero_record_site_warns(self):
        outcomes, warnings = validate_site_records("exist", [], ["OC90"])
        assert len(warnings) >= 1
        assert any("zero records" in w.lower() for w in warnings)


class TestSiteStatus:
    def test_all_hit_ok(self):
        site = SiteOutcome(
            site="exist", status="PENDING",
            articles_total=2, articles_hit=2, articles_miss=0,
        )
        assert compute_site_status(site) == "OK"

    def test_partial_coverage_warn(self):
        site = SiteOutcome(
            site="autodoc", status="PENDING",
            articles_total=2, articles_hit=1, articles_miss=1,
        )
        assert compute_site_status(site) == "WARN"

    def test_fallback_used_warn(self):
        site = SiteOutcome(
            site="rossko", status="PENDING",
            articles_total=2, articles_hit=1, articles_miss=1,
            fallback_paths_used=["proxy_fallback"],
        )
        assert compute_site_status(site) == "WARN"

    def test_zero_records_with_errors_fail(self):
        site = SiteOutcome(
            site="exist", status="PENDING",
            articles_total=2, records_total=0, articles_hit=0, articles_miss=2,
            errors=["All requests failed"],
        )
        assert compute_site_status(site) == "FAIL"

    def test_zero_records_no_errors_fail(self):
        site = SiteOutcome(
            site="exist", status="PENDING",
            articles_total=2, records_total=0, articles_hit=0, articles_miss=2,
        )
        assert compute_site_status(site) == "FAIL"


class TestReportInvariants:
    def test_zero_records_ok_violation(self):
        violations = validate_report_invariants([
            SiteOutcome(site="exist", status="OK", records_total=0),
        ])
        assert len(violations) >= 1

    def test_zero_records_no_errors_violation(self):
        violations = validate_report_invariants([
            SiteOutcome(site="exist", status="FAIL", records_total=0),
        ])
        assert len(violations) >= 1

    def test_missing_screenshots_with_ok_violation(self):
        violations = validate_report_invariants([
            SiteOutcome(site="exist", status="OK", records_total=3, articles_total=2,
                        articles_hit=2, articles_miss=0,
                        screenshots_ok=2, screenshots_missing=1),
        ])
        assert len(violations) >= 1