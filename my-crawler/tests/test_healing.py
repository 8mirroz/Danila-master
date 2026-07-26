"""Tests for the healing module — bounded retry, exception classification, fallback policies."""

import asyncio
from my_crawler.healing import (
    classify_error,
    bounded_retry,
    rossko_classify_empty,
    exist_classify_empty,
)


class TestExceptionClassification:
    def test_timeout_classification(self):
        exc = TimeoutError("Navigation timeout exceeded")
        assert classify_error(exc) == "timeout"
        exc2 = Exception("Timeout 30000ms exceeded")
        assert classify_error(exc2) == "timeout"

    def test_network_error_classification(self):
        exc = ConnectionRefusedError("Connection refused")
        assert classify_error(exc) == "network_error"
        exc2 = Exception("DNS resolution failed")
        assert classify_error(exc2) == "network_error"
        exc3 = Exception("ENOTFOUND example.com")
        assert classify_error(exc3) == "network_error"

    def test_anti_bot_classification(self):
        exc = Exception("captcha detected")
        assert classify_error(exc) == "anti_bot"
        exc2 = Exception("HTTP 429 Too Many Requests")
        assert classify_error(exc2) == "anti_bot"
        exc3 = Exception("Access Denied 403")
        assert classify_error(exc3) == "anti_bot"

    def test_auth_required_classification(self):
        exc = Exception("login required")
        assert classify_error(exc) == "auth_required"
        exc2 = Exception("401 Unauthorized")
        assert classify_error(exc2) == "auth_required"

    def test_layout_changed_classification(self):
        exc = Exception("element not found")
        assert classify_error(exc) == "layout_changed"
        exc2 = Exception("no such element: Unable to locate element")
        assert classify_error(exc2) == "layout_changed"
        exc3 = Exception("locator not found")
        assert classify_error(exc3) == "layout_changed"

    def test_unknown_classification(self):
        exc = Exception("Some random error")
        assert classify_error(exc) == "unknown"


class TestBoundedRetry:
    def test_succeeds_on_first_attempt(self):
        async def succeed():
            return "success"

        result, succeeded, paths = asyncio.run(bounded_retry(succeed, max_retries=2))
        assert succeeded
        assert result == "success"
        assert paths == []

    def test_retries_on_failure(self):
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"

        result, succeeded, paths = asyncio.run(bounded_retry(fail_then_succeed, max_retries=2))
        assert succeeded
        assert result == "success"
        assert len(paths) == 1
        assert "retry" in paths[0]

    def test_exhausts_retries(self):
        async def always_fail():
            raise ValueError("Persistent error")

        result, succeeded, paths = asyncio.run(bounded_retry(always_fail, max_retries=2))
        assert not succeeded
        assert result is None
        assert len(paths) == 1
        assert "exhausted" in paths[0]

    def test_respects_max_retries_zero(self):
        call_count = 0

        async def fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        result, succeeded, _ = asyncio.run(bounded_retry(fail, max_retries=0))
        assert not succeeded
        assert call_count == 1  # only the initial attempt

    def test_records_fallback_path(self):
        async def fail():
            raise ValueError("Error")

        fallback_paths = ["pre_existing"]
        _, succeeded, paths = asyncio.run(bounded_retry(
            fail, max_retries=1, fallback_paths=fallback_paths,
        ))
        assert not succeeded
        assert "pre_existing" in paths
        assert any("exhausted" in p for p in paths)


class TestRosskoClassifyEmpty:
    def test_search_empty(self):
        html = '<div>Ничего не найдено</div>'
        assert rossko_classify_empty(html) == "search_empty"

    def test_anti_bot(self):
        html = '<div>капча</div>'
        assert rossko_classify_empty(html) == "anti_bot"

    def test_auth_required(self):
        html = '<div>войти</div>'
        assert rossko_classify_empty(html) == "auth_required"

    def test_layout_changed(self):
        html = '<div>some other content</div>'
        assert rossko_classify_empty(html) == "layout_changed"


class TestExistClassifyEmpty:
    def test_not_found(self):
        html = '404 Страница не найдена'
        assert exist_classify_empty("http://exist.ru", html) == "no_results"

    def test_auth_required(self):
        html = 'Вход'
        assert exist_classify_empty("http://exist.ru", html) == "auth_required"

    def test_catalog_page(self):
        html = '<ul class="catalogs">'
        assert exist_classify_empty("http://exist.ru/Price/?pcode=OC90", html) == "no_results"

    def test_layout_changed(self):
        html = '<div>unexpected page structure</div>'
        assert exist_classify_empty("http://exist.ru/Price/?pcode=OC90", html) == "layout_changed"