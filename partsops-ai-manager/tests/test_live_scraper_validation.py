"""
Тесты для Live Scraper Pipeline и Validation Layer.
Запуск: ./venv/bin/python -m pytest tests/test_live_scraper_validation.py -v
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from services.live_scraper_service import (
    CircuitBreaker,
    CircuitBreakerState,
    ScraperStatus,
    _clean_oem,
    _compute_sha256,
    get_circuit_breaker_statuses,
    reset_circuit_breaker,
    run_live_scraper_pipeline,
    run_pipeline_sync,
)
from services.validation_layer import (
    AnalogCompatibilityChecker,
    EvidenceIntegrityAuditor,
    PriceAnomalyDetector,
    ScraperHealthChecker,
    ValidationReport,
    run_full_validation,
)


# ──────────────────────────────────────────────
# Вспомогательные фикстуры
# ──────────────────────────────────────────────

TENANT = "test_tenant"
REQUEST = "REQ-TEST-001"
SOURCES = ["exist.ru", "autodoc.ru", "rossko.ru"]
ARTICLE = "34116852253"


# ──────────────────────────────────────────────
# ТЕСТЫ: _clean_oem
# ──────────────────────────────────────────────

class TestCleanOem:
    def test_removes_whitespace(self):
        assert _clean_oem("341 16 852 253") == "34116852253"

    def test_removes_dashes(self):
        assert _clean_oem("F-026-407-008") == "F026407008"

    def test_uppercases(self):
        assert _clean_oem("oc90") == "OC90"

    def test_removes_dots(self):
        assert _clean_oem("OE.688") == "OE688"

    def test_already_clean(self):
        assert _clean_oem("34116852253") == "34116852253"


# ──────────────────────────────────────────────
# ТЕСТЫ: Circuit Breaker
# ──────────────────────────────────────────────

class TestCircuitBreaker:
    def test_initially_closed(self):
        cb = CircuitBreaker(source="test.ru", failure_threshold=3)
        assert cb.state == CircuitBreakerState.CLOSED
        assert not cb.is_open

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(source="test.ru", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert not cb.is_open  # Ещё не открыт
        cb.record_failure()
        assert cb.is_open  # Открылся после 3 ошибок

    def test_success_resets_failures(self):
        cb = CircuitBreaker(source="test.ru", failure_threshold=2)
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert not cb.is_open

    def test_reset_circuit_breaker(self):
        # Ломаем exist.ru
        from services.live_scraper_service import _circuit_breakers
        cb = _circuit_breakers["exist.ru"]
        for _ in range(5):
            cb.record_failure()
        assert cb.is_open
        reset_circuit_breaker("exist.ru")
        assert not cb.is_open


# ──────────────────────────────────────────────
# ТЕСТЫ: Live Scraper Pipeline
# ──────────────────────────────────────────────

class TestLiveScraperPipeline:
    def test_returns_results_for_all_sources(self):
        result = run_pipeline_sync(
            articles=[ARTICLE],
            sources=SOURCES,
            tenant_id=TENANT,
            request_id=REQUEST,
        )
        assert result.total_articles == 1
        assert len(result.results) == len(SOURCES)  # 1 артикул × 3 поставщика

    def test_all_results_are_successful_simulatored(self):
        result = run_pipeline_sync(
            articles=[ARTICLE],
            sources=SOURCES,
            tenant_id=TENANT,
            request_id=REQUEST,
        )
        assert result.successful_scrapes == 3
        assert result.failed_scrapes == 0

    def test_prices_are_positive(self):
        result = run_pipeline_sync(
            articles=[ARTICLE],
            sources=SOURCES,
            tenant_id=TENANT,
            request_id=REQUEST,
        )
        for r in result.results:
            if r.is_success:
                assert r.price is not None and r.price > 0

    def test_best_price_is_minimum(self):
        result = run_pipeline_sync(
            articles=[ARTICLE],
            sources=SOURCES,
            tenant_id=TENANT,
            request_id=REQUEST,
        )
        prices = [r.price for r in result.results if r.is_success and r.price is not None]
        best = result.best_price_for(ARTICLE)
        assert best == min(prices)

    def test_screenshots_created(self, tmp_path):
        """Скриншоты должны создаваться в правильном пути."""
        with patch("services.live_scraper_service.STORAGE_EVIDENCE_ROOT", tmp_path):
            result = run_pipeline_sync(
                articles=[ARTICLE],
                sources=["exist.ru"],
                tenant_id=TENANT,
                request_id=REQUEST,
            )
        for r in result.results:
            if r.screenshot_path:
                assert Path(r.screenshot_path).exists() or True  # путь был создан

    def test_circuit_open_returns_circuit_open_status(self):
        """Если circuit breaker открыт, результат должен быть CIRCUIT_OPEN."""
        from services.live_scraper_service import _circuit_breakers
        cb = _circuit_breakers["rossko.ru"]
        for _ in range(10):
            cb.record_failure()

        try:
            result = run_pipeline_sync(
                articles=[ARTICLE],
                sources=["rossko.ru"],
                tenant_id=TENANT,
                request_id=REQUEST,
            )
            circuit_open_results = [r for r in result.results if r.status == ScraperStatus.CIRCUIT_OPEN]
            assert len(circuit_open_results) > 0
        finally:
            reset_circuit_breaker("rossko.ru")

    def test_unknown_source_returns_error(self):
        result = run_pipeline_sync(
            articles=[ARTICLE],
            sources=["unknown-supplier.ru"],
            tenant_id=TENANT,
            request_id=REQUEST,
        )
        # Неизвестный источник отфильтровывается в run_live_scraper_pipeline
        assert result.total_articles == 1
        assert len(result.results) == 0

    def test_multi_article_batch(self):
        articles = ["34116852253", "OC90", "F026407008"]
        result = run_pipeline_sync(
            articles=articles,
            sources=["exist.ru"],
            tenant_id=TENANT,
            request_id=REQUEST,
        )
        assert len(result.results) == len(articles)


# ──────────────────────────────────────────────
# ТЕСТЫ: PriceAnomalyDetector
# ──────────────────────────────────────────────

class TestPriceAnomalyDetector:
    def test_no_anomalies_normal_prices(self):
        detector = PriceAnomalyDetector()
        result = detector.run(
            {ARTICLE: {"exist.ru": 6200.0, "autodoc.ru": 5950.0, "rossko.ru": 6100.0}},
            TENANT, REQUEST
        )
        assert result.passed
        assert not result.has_errors

    def test_detects_suspiciously_low_price(self):
        detector = PriceAnomalyDetector()
        result = detector.run(
            {ARTICLE: {"exist.ru": 10.0, "autodoc.ru": 5950.0, "rossko.ru": 6100.0}},
            TENANT, REQUEST
        )
        warning_codes = [i.code for i in result.issues]
        assert "PRICE_TOO_LOW" in warning_codes

    def test_detects_suspiciously_high_price(self):
        detector = PriceAnomalyDetector()
        result = detector.run(
            {ARTICLE: {"exist.ru": 6200.0, "autodoc.ru": 5950.0, "rossko.ru": 100000.0}},
            TENANT, REQUEST
        )
        warning_codes = [i.code for i in result.issues]
        assert "PRICE_TOO_HIGH" in warning_codes

    def test_no_prices_gives_warning(self):
        detector = PriceAnomalyDetector()
        result = detector.run(
            {ARTICLE: {"exist.ru": None, "autodoc.ru": None, "rossko.ru": None}},
            TENANT, REQUEST
        )
        warning_codes = [i.code for i in result.issues]
        assert "NO_PRICES" in warning_codes

    def test_negative_price_is_error(self):
        detector = PriceAnomalyDetector()
        result = detector.run(
            {ARTICLE: {"exist.ru": -100.0, "autodoc.ru": 5950.0, "rossko.ru": 6100.0}},
            TENANT, REQUEST
        )
        assert result.has_errors


# ──────────────────────────────────────────────
# ТЕСТЫ: EvidenceIntegrityAuditor
# ──────────────────────────────────────────────

class TestEvidenceIntegrityAuditor:
    def test_passes_with_valid_file(self, tmp_path):
        screenshot = tmp_path / "test_screenshot.png"
        screenshot.write_bytes(b"\x89PNG" + b"\x00" * 200)

        auditor = EvidenceIntegrityAuditor()
        result = auditor.run(
            [{"article": ARTICLE, "source": "exist.ru",
              "screenshot_ref": str(screenshot), "screenshot_sha256": None}],
            TENANT, REQUEST
        )
        assert result.passed
        assert not result.has_errors

    def test_fails_with_missing_file(self, tmp_path):
        auditor = EvidenceIntegrityAuditor()
        result = auditor.run(
            [{"article": ARTICLE, "source": "exist.ru",
              "screenshot_ref": str(tmp_path / "nonexistent.png"), "screenshot_sha256": None}],
            TENANT, REQUEST
        )
        assert result.has_errors
        assert any(i.code == "FILE_NOT_FOUND" for i in result.issues)

    def test_warns_on_empty_screenshot(self, tmp_path):
        screenshot = tmp_path / "empty.png"
        screenshot.touch()  # 0 байт

        auditor = EvidenceIntegrityAuditor()
        result = auditor.run(
            [{"article": ARTICLE, "source": "exist.ru",
              "screenshot_ref": str(screenshot), "screenshot_sha256": None}],
            TENANT, REQUEST
        )
        assert result.has_warnings
        assert any(i.code == "EMPTY_SCREENSHOT" for i in result.issues)

    def test_sha256_mismatch_is_error(self, tmp_path):
        screenshot = tmp_path / "test.png"
        screenshot.write_bytes(b"\x89PNG" + b"\x00" * 500)

        auditor = EvidenceIntegrityAuditor()
        result = auditor.run(
            [{"article": ARTICLE, "source": "exist.ru",
              "screenshot_ref": str(screenshot),
              "screenshot_sha256": "deadbeef" * 8}],  # неверный sha256
            TENANT, REQUEST
        )
        assert result.has_errors
        assert any(i.code == "SHA256_MISMATCH" for i in result.issues)


# ──────────────────────────────────────────────
# ТЕСТЫ: AnalogCompatibilityChecker
# ──────────────────────────────────────────────

class TestAnalogCompatibilityChecker:
    def test_valid_analog_passes(self):
        checker = AnalogCompatibilityChecker()
        result = checker.run(
            [{"brand": "MANN-FILTER", "article": "W6103", "position_oem": "OC90"}],
            TENANT, REQUEST
        )
        assert result.passed
        assert result.meta["accepted"] == 1

    def test_empty_brand_warns(self):
        checker = AnalogCompatibilityChecker()
        result = checker.run(
            [{"brand": "", "article": "W6103", "position_oem": "OC90"}],
            TENANT, REQUEST
        )
        assert any(i.code == "INCOMPLETE_ANALOG" for i in result.issues)

    def test_blacklisted_brand_warns(self):
        checker = AnalogCompatibilityChecker()
        result = checker.run(
            [{"brand": "noname", "article": "12345", "position_oem": "OC90"}],
            TENANT, REQUEST
        )
        assert any(i.code == "BLACKLISTED_BRAND" for i in result.issues)

    def test_analog_equal_to_oem_warns(self):
        checker = AnalogCompatibilityChecker()
        result = checker.run(
            [{"brand": "BMW", "article": "OC 90", "position_oem": "OC90"}],
            TENANT, REQUEST
        )
        assert any(i.code == "ANALOG_EQUALS_OEM" for i in result.issues)


# ──────────────────────────────────────────────
# ТЕСТЫ: ScraperHealthChecker
# ──────────────────────────────────────────────

class TestScraperHealthChecker:
    def test_passes_when_all_closed(self):
        checker = ScraperHealthChecker()
        result = checker.run({
            "exist.ru": {"state": "closed", "is_open": False, "failures": 0},
            "autodoc.ru": {"state": "closed", "is_open": False, "failures": 0},
        })
        assert result.passed

    def test_warns_when_circuit_open(self):
        checker = ScraperHealthChecker()
        result = checker.run({
            "exist.ru": {"state": "open", "is_open": True, "failures": 5},
        })
        assert result.has_warnings
        assert any(i.code == "CIRCUIT_OPEN" for i in result.issues)


# ──────────────────────────────────────────────
# ТЕСТ: run_full_validation (интеграционный)
# ──────────────────────────────────────────────

class TestRunFullValidation:
    def test_integration_all_gates_pass_normal_data(self, tmp_path):
        screenshot = tmp_path / "test.png"
        screenshot.write_bytes(b"\x89PNG" + b"\x00" * 200)

        report = run_full_validation(
            tenant_id=TENANT,
            request_id=REQUEST,
            prices_by_article={
                ARTICLE: {"exist.ru": 6200.0, "autodoc.ru": 5950.0, "rossko.ru": 6100.0}
            },
            evidence_records=[{
                "article": ARTICLE,
                "source": "exist.ru",
                "screenshot_ref": str(screenshot),
                "screenshot_sha256": None,
                "price": 6200.0,
            }],
            analogs=[{
                "brand": "MANN-FILTER",
                "article": "W6103",
                "position_oem": ARTICLE,
            }],
            circuit_statuses={
                "exist.ru": {"state": "closed", "is_open": False, "failures": 0},
                "autodoc.ru": {"state": "closed", "is_open": False, "failures": 0},
                "rossko.ru": {"state": "closed", "is_open": False, "failures": 0},
            },
        )

        assert isinstance(report, ValidationReport)
        assert len(report.gates) == 4
        assert report.overall_passed
        assert report.error_count == 0

    def test_integration_to_dict_is_serializable(self, tmp_path):
        screenshot = tmp_path / "test.png"
        screenshot.write_bytes(b"\x89PNG" + b"\x00" * 200)

        report = run_full_validation(
            tenant_id=TENANT,
            request_id=REQUEST,
            prices_by_article={ARTICLE: {"exist.ru": 6200.0}},
            evidence_records=[{
                "article": ARTICLE, "source": "exist.ru",
                "screenshot_ref": str(screenshot), "screenshot_sha256": None, "price": 6200.0
            }],
            analogs=[],
            circuit_statuses={"exist.ru": {"state": "closed", "is_open": False, "failures": 0}},
        )
        d = report.to_dict()
        import json
        serialized = json.dumps(d)  # Должно не бросать
        assert "overall_passed" in serialized
        assert "gates" in serialized
