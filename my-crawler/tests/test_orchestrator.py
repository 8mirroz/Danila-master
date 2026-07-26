"""Tests for the orchestrator module — overall status computation, env validation."""

import os
from my_crawler.orchestrator import _compute_overall_status, validate_env
from my_crawler.report import SiteOutcome


class TestOverallStatus:
    def test_all_ok(self):
        outcomes = [
            SiteOutcome(site="exist", status="OK"),
            SiteOutcome(site="autodoc", status="OK"),
            SiteOutcome(site="rossko", status="OK"),
        ]
        assert _compute_overall_status(outcomes) == "OK"

    def test_any_fail_is_fail(self):
        outcomes = [
            SiteOutcome(site="exist", status="OK"),
            SiteOutcome(site="autodoc", status="FAIL"),
            SiteOutcome(site="rossko", status="OK"),
        ]
        assert _compute_overall_status(outcomes) == "FAIL"

    def test_warn_without_fail_is_warn(self):
        outcomes = [
            SiteOutcome(site="exist", status="OK"),
            SiteOutcome(site="autodoc", status="WARN"),
            SiteOutcome(site="rossko", status="OK"),
        ]
        assert _compute_overall_status(outcomes) == "WARN"

    def test_all_warn_is_warn(self):
        outcomes = [
            SiteOutcome(site="exist", status="WARN"),
            SiteOutcome(site="autodoc", status="WARN"),
        ]
        assert _compute_overall_status(outcomes) == "WARN"

    def test_empty_outcomes_ok(self):
        assert _compute_overall_status([]) == "OK"


class TestValidateEnv:
    def tear_method(self):
        for key in ["BROWSER_PROFILE_DIR", "EXIST_BROWSER_PROFILE_DIR",
                     "CRAWLER_MAX_CONCURRENCY", "EXIST_PROXY_URL"]:
            os.environ.pop(key, None)

    def test_no_articles_issues(self):
        issues = validate_env([])
        assert any("No articles" in i for i in issues)

    def test_valid_articles_no_issues(self):
        issues = validate_env(["OC90", "W6103"])
        # Should not have "No articles" issue
        assert not any("No articles" in i for i in issues)

    def test_shared_and_site_profile_conflict(self):
        os.environ["BROWSER_PROFILE_DIR"] = "/tmp/shared"
        os.environ["EXIST_BROWSER_PROFILE_DIR"] = "/tmp/exist"
        issues = validate_env(["OC90"])
        assert any("Both" in i and "BROWSER_PROFILE_DIR" in i for i in issues)
        self.tear_method()

    def test_concurrency_out_of_range(self):
        os.environ["CRAWLER_MAX_CONCURRENCY"] = "10"
        issues = validate_env(["OC90"])
        assert any("out of range" in i for i in issues)
        self.tear_method()

    def test_concurrency_invalid_int(self):
        os.environ["CRAWLER_MAX_CONCURRENCY"] = "abc"
        issues = validate_env(["OC90"])
        assert any("not a valid integer" in i for i in issues)
        self.tear_method()

    def test_proxy_url_format(self):
        os.environ["EXIST_PROXY_URL"] = "invalid-proxy-format"
        issues = validate_env(["OC90"])
        assert any("format may be invalid" in i for i in issues)
        self.tear_method()

    def test_valid_proxy_url_no_issue(self):
        os.environ["EXIST_PROXY_URL"] = "http://user:pass@host:8080"
        issues = validate_env(["OC90"])
        assert not any("format may be invalid" in i for i in issues)
        self.tear_method()