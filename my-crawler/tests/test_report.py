"""Tests for the report module — data classes, JSON/MD generation, exit code contract."""

import json
import os
import tempfile
from my_crawler.report import (
    RunReport,
    SiteOutcome,
    ArticleOutcome,
    generate_run_report_json,
    generate_run_summary_md,
    write_exit_code,
    exit_code_for_status,
)


class TestExitCodeContract:
    def test_ok_exit_code(self):
        assert exit_code_for_status("OK") == 0

    def test_warn_exit_code(self):
        assert exit_code_for_status("WARN") == 10

    def test_fail_exit_code(self):
        assert exit_code_for_status("FAIL") == 20

    def test_unknown_status_fails(self):
        assert exit_code_for_status("UNKNOWN") == 20


class TestRunReportGeneration:
    def _make_report(self, status: str) -> RunReport:
        return RunReport(
            overall_status=status,
            started_at="2026-07-24T12:00:00",
            finished_at="2026-07-24T12:30:00",
            articles_input=["OC90", "W6103"],
            sites=[
                SiteOutcome(
                    site="exist",
                    status="OK",
                    requests_total=2,
                    records_total=4,
                    articles_total=2,
                    articles_hit=2,
                    articles_miss=0,
                    screenshots_ok=4,
                    article_outcomes=[
                        ArticleOutcome(search_article="OC90", found=True, records_count=2),
                        ArticleOutcome(search_article="W6103", found=True, records_count=2),
                    ],
                ),
                SiteOutcome(
                    site="autodoc",
                    status="WARN",
                    requests_total=2,
                    records_total=1,
                    articles_total=2,
                    articles_hit=1,
                    articles_miss=1,
                    screenshots_ok=1,
                    warnings=["Article not found: OC90"],
                    fallback_paths_used=["search_button_fallback"],
                    article_outcomes=[
                        ArticleOutcome(search_article="OC90", found=False, miss_reason="search_empty"),
                        ArticleOutcome(search_article="W6103", found=True, records_count=1),
                    ],
                ),
            ],
        )

    def test_generate_json_ok(self):
        report = self._make_report("OK")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = generate_run_report_json(report, path)
            assert os.path.isfile(result)
            with open(result) as f:
                data = json.load(f)
            assert data["overall_status"] == "OK"
            assert len(data["sites"]) == 2
            assert data["sites"][0]["site"] == "exist"
            assert data["sites"][0]["status"] == "OK"
            assert data["sites"][1]["status"] == "WARN"
        finally:
            os.unlink(path)

    def test_generate_json_warn(self):
        report = self._make_report("WARN")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = generate_run_report_json(report, path)
            with open(result) as f:
                data = json.load(f)
            assert data["overall_status"] == "WARN"
            assert data["sites"][1]["fallback_paths_used"] == ["search_button_fallback"]
        finally:
            os.unlink(path)

    def test_generate_json_fail(self):
        report = self._make_report("FAIL")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = generate_run_report_json(report, path)
            with open(result) as f:
                data = json.load(f)
            assert data["overall_status"] == "FAIL"
        finally:
            os.unlink(path)

    def test_generate_summary_md(self):
        report = self._make_report("WARN")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            path = f.name
        try:
            result = generate_run_summary_md(report, path)
            assert os.path.isfile(result)
            with open(result) as f:
                content = f.read()
            assert "# PartsOps Crawler Run Summary" in content
            assert "**Overall Status**: WARN" in content
            assert "exist" in content
            assert "autodoc" in content
            assert "search_button_fallback" in content
            assert "search_empty" in content
        finally:
            os.unlink(path)

    def test_write_exit_code(self):
        report = self._make_report("OK")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            path = f.name
        try:
            code = write_exit_code(report, path)
            assert code == 0
            with open(path) as f:
                assert f.read().strip() == "0"
        finally:
            os.unlink(path)

    def test_write_exit_code_warn(self):
        report = self._make_report("WARN")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            path = f.name
        try:
            code = write_exit_code(report, path)
            assert code == 10
            with open(path) as f:
                assert f.read().strip() == "10"
        finally:
            os.unlink(path)

    def test_write_exit_code_fail(self):
        report = self._make_report("FAIL")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            path = f.name
        try:
            code = write_exit_code(report, path)
            assert code == 20
            with open(path) as f:
                assert f.read().strip() == "20"
        finally:
            os.unlink(path)

    def test_remediation_commands_in_report(self):
        report = self._make_report("FAIL")
        report.sites[0].remediation_commands = ["scripts/bootstrap_profile.py --site exist"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = generate_run_report_json(report, path)
            with open(result) as f:
                data = json.load(f)
            assert data["sites"][0]["remediation_commands"] == ["scripts/bootstrap_profile.py --site exist"]
        finally:
            os.unlink(path)

    def test_article_outcomes_in_report(self):
        report = self._make_report("WARN")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            result = generate_run_report_json(report, path)
            with open(result) as f:
                data = json.load(f)
            autodoc_outcomes = data["sites"][1]["article_outcomes"]
            assert len(autodoc_outcomes) == 2
            assert not autodoc_outcomes[0]["found"]
            assert autodoc_outcomes[0]["miss_reason"] == "search_empty"
            assert autodoc_outcomes[1]["found"]
        finally:
            os.unlink(path)