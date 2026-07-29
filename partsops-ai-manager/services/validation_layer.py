"""
Validation Layer — многоуровневый слой валидации и контроля качества данных скрапинга.

Шлюзы качества (Quality Gates):
  1. PriceAnomalyDetector    — выявление ценовых выбросов (слишком дёшево / дорого)
  2. EvidenceIntegrityAuditor — физическая проверка файлов скриншотов
  3. AnalogCompatibilityChecker — скоринг релевантности кросс-номеров
  4. ValidationReport         — агрегированный вердикт готовности пакета
"""
from __future__ import annotations

import hashlib
import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ──────────────────────────────────────────────
# КОНСТАНТЫ
# ──────────────────────────────────────────────

# Пороги выбросов (кратность от медианы)
ANOMALY_LOWER_FACTOR = 0.25   # Цена < 25% медианы → подозрительно дёшево
ANOMALY_UPPER_FACTOR = 4.0    # Цена > 400% медианы → подозрительно дорого
MIN_SCREENSHOT_SIZE_BYTES = 100  # Файл скриншота < 100 байт → пустой placeholder
ANALOG_BRAND_BLACKLIST = {"noname", "unknown", "generic", "n/a"}


# ──────────────────────────────────────────────
# ТИПЫ И ВЕРДИКТЫ ВАЛИДАЦИИ
# ──────────────────────────────────────────────

@dataclass
class ValidationIssue:
    gate: str          # Имя шлюза качества
    severity: str      # "error" | "warning" | "info"
    code: str          # Машиночитаемый код ошибки
    message: str       # Человекочитаемое описание
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    gate_name: str
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)


@dataclass
class ValidationReport:
    """Агрегированный итоговый отчёт по всем шлюзам валидации."""
    tenant_id: str
    request_id: str
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    gates: list[GateResult] = field(default_factory=list)

    @property
    def overall_passed(self) -> bool:
        """True только если ни один шлюз не имеет критических ошибок."""
        return all(not g.has_errors for g in self.gates)

    @property
    def error_count(self) -> int:
        return sum(len([i for i in g.issues if i.severity == "error"]) for g in self.gates)

    @property
    def warning_count(self) -> int:
        return sum(len([i for i in g.issues if i.severity == "warning"]) for g in self.gates)

    def gate(self, name: str) -> Optional[GateResult]:
        return next((g for g in self.gates if g.gate_name == name), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "validated_at": self.validated_at.isoformat(),
            "overall_passed": self.overall_passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "gates": [
                {
                    "gate_name": g.gate_name,
                    "passed": g.passed,
                    "has_errors": g.has_errors,
                    "has_warnings": g.has_warnings,
                    "meta": g.meta,
                    "issues": [
                        {
                            "severity": i.severity,
                            "code": i.code,
                            "message": i.message,
                            "context": i.context,
                        }
                        for i in g.issues
                    ],
                }
                for g in self.gates
            ],
        }


# ──────────────────────────────────────────────
# ШЛЮЗ 1: АУДИТ АНОМАЛИЙ ЦЕН
# ──────────────────────────────────────────────

class PriceAnomalyDetector:
    """
    Выявляет ценовые выбросы среди предложений поставщиков.
    Сравнивает каждую цену с медианой по артикулу.
    """

    def run(
        self,
        prices_by_article: dict[str, dict[str, Optional[float]]],
        tenant_id: str,
        request_id: str,
    ) -> GateResult:
        """
        prices_by_article: {
            "34116852253": {"exist.ru": 6200.0, "autodoc.ru": 5950.0, "rossko.ru": None}
        }
        """
        issues: list[ValidationIssue] = []
        meta: dict[str, Any] = {"articles_checked": 0, "anomalies_detected": 0}

        for article, supplier_prices in prices_by_article.items():
            valid_prices = [v for v in supplier_prices.values() if v is not None and v > 0]
            meta["articles_checked"] += 1

            if len(valid_prices) < 2:
                if not valid_prices:
                    issues.append(ValidationIssue(
                        gate="price_anomaly",
                        severity="warning",
                        code="NO_PRICES",
                        message=f"Нет доступных цен ни от одного поставщика для артикула {article}",
                        context={"article": article},
                    ))
                continue

            median_price = statistics.median(valid_prices)

            for source, price in supplier_prices.items():
                if price is None:
                    continue
                if price <= 0:
                    issues.append(ValidationIssue(
                        gate="price_anomaly",
                        severity="error",
                        code="NEGATIVE_OR_ZERO_PRICE",
                        message=f"Некорректная цена {price} от {source} для {article}",
                        context={"article": article, "source": source, "price": price},
                    ))
                    meta["anomalies_detected"] += 1
                elif price < median_price * ANOMALY_LOWER_FACTOR:
                    issues.append(ValidationIssue(
                        gate="price_anomaly",
                        severity="warning",
                        code="PRICE_TOO_LOW",
                        message=(
                            f"Подозрительно низкая цена {price:.0f}₽ от {source} для {article} "
                            f"(медиана: {median_price:.0f}₽, порог: {median_price * ANOMALY_LOWER_FACTOR:.0f}₽)"
                        ),
                        context={"article": article, "source": source, "price": price, "median": median_price},
                    ))
                    meta["anomalies_detected"] += 1
                elif price > median_price * ANOMALY_UPPER_FACTOR:
                    issues.append(ValidationIssue(
                        gate="price_anomaly",
                        severity="warning",
                        code="PRICE_TOO_HIGH",
                        message=(
                            f"Аномально высокая цена {price:.0f}₽ от {source} для {article} "
                            f"(медиана: {median_price:.0f}₽, порог: {median_price * ANOMALY_UPPER_FACTOR:.0f}₽)"
                        ),
                        context={"article": article, "source": source, "price": price, "median": median_price},
                    ))
                    meta["anomalies_detected"] += 1

        passed = not any(i.severity == "error" for i in issues)
        return GateResult(gate_name="price_anomaly", passed=passed, issues=issues, meta=meta)


# ──────────────────────────────────────────────
# ШЛЮЗ 2: КОНТРОЛЬ ЦЕЛОСТНОСТИ ДОКАЗАТЕЛЬСТВ
# ──────────────────────────────────────────────

class EvidenceIntegrityAuditor:
    """
    Физически проверяет:
    - Существование файлов скриншотов на диске.
    - Ненулевой размер файла (> MIN_SCREENSHOT_SIZE_BYTES).
    - Соответствие SHA-256 (если передан).
    - Корректность file:// URL (абсолютный путь).
    """

    def run(
        self,
        evidence_records: list[dict[str, Any]],
        tenant_id: str,
        request_id: str,
    ) -> GateResult:
        """
        evidence_records: list of dicts with keys:
          - article: str
          - source: str
          - screenshot_ref: str (path or file:// URL)
          - screenshot_sha256: Optional[str]
          - price: Optional[float]
        """
        issues: list[ValidationIssue] = []
        meta: dict[str, Any] = {
            "total_checked": len(evidence_records),
            "missing_files": 0,
            "empty_files": 0,
            "sha256_mismatches": 0,
            "invalid_urls": 0,
        }

        for rec in evidence_records:
            article = rec.get("article", "?")
            source = rec.get("source", "?")
            ref = rec.get("screenshot_ref", "")
            expected_sha = rec.get("screenshot_sha256")

            if not ref:
                issues.append(ValidationIssue(
                    gate="evidence_integrity",
                    severity="warning",
                    code="MISSING_SCREENSHOT_REF",
                    message=f"Нет ссылки на скриншот для {article} @ {source}",
                    context={"article": article, "source": source},
                ))
                meta["missing_files"] += 1
                continue

            # Нормализуем путь
            path_str = ref.replace("file://", "")
            path = Path(path_str)

            if not path.is_absolute():
                issues.append(ValidationIssue(
                    gate="evidence_integrity",
                    severity="warning",
                    code="RELATIVE_PATH",
                    message=f"Относительный путь к скриншоту для {article} @ {source}: {ref}",
                    context={"article": article, "source": source, "ref": ref},
                ))
                meta["invalid_urls"] += 1

            if not path.exists():
                issues.append(ValidationIssue(
                    gate="evidence_integrity",
                    severity="error",
                    code="FILE_NOT_FOUND",
                    message=f"Файл скриншота не найден: {path}",
                    context={"article": article, "source": source, "path": str(path)},
                ))
                meta["missing_files"] += 1
                continue

            file_size = path.stat().st_size
            if file_size < MIN_SCREENSHOT_SIZE_BYTES:
                issues.append(ValidationIssue(
                    gate="evidence_integrity",
                    severity="warning",
                    code="EMPTY_SCREENSHOT",
                    message=(
                        f"Пустой/заглушечный скриншот ({file_size} байт) "
                        f"для {article} @ {source}. Требуется реальный захват."
                    ),
                    context={"article": article, "source": source, "size_bytes": file_size},
                ))
                meta["empty_files"] += 1

            # Проверка SHA-256
            if expected_sha and path.exists() and file_size > 0:
                actual_sha = self._sha256(path)
                if actual_sha != expected_sha:
                    issues.append(ValidationIssue(
                        gate="evidence_integrity",
                        severity="error",
                        code="SHA256_MISMATCH",
                        message=f"Нарушена целостность скриншота (SHA-256) для {article} @ {source}",
                        context={
                            "article": article,
                            "source": source,
                            "expected": expected_sha,
                            "actual": actual_sha,
                        },
                    ))
                    meta["sha256_mismatches"] += 1

        passed = not any(i.severity == "error" for i in issues)
        return GateResult(gate_name="evidence_integrity", passed=passed, issues=issues, meta=meta)

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()


# ──────────────────────────────────────────────
# ШЛЮЗ 3: СОВМЕСТИМОСТЬ АНАЛОГОВ
# ──────────────────────────────────────────────

class AnalogCompatibilityChecker:
    """
    Проверяет аналоги на базовую совместимость:
    - Не пустой бренд / артикул.
    - Бренд не в чёрном списке заглушек.
    - Нет прямых совпадений с оригинальным OEM (тогда это не аналог).
    """

    def run(
        self,
        analogs: list[dict[str, Any]],  # [{brand, article, position_oem}]
        tenant_id: str,
        request_id: str,
    ) -> GateResult:
        issues: list[ValidationIssue] = []
        meta: dict[str, Any] = {
            "total_analogs": len(analogs),
            "rejected": 0,
            "accepted": 0,
        }

        for ana in analogs:
            brand = (ana.get("brand") or "").strip()
            article = (ana.get("article") or "").strip()
            pos_oem = (ana.get("position_oem") or "").strip()

            if not brand or not article:
                issues.append(ValidationIssue(
                    gate="analog_compatibility",
                    severity="warning",
                    code="INCOMPLETE_ANALOG",
                    message=f"Неполные данные аналога: brand='{brand}', article='{article}'",
                    context={"brand": brand, "article": article},
                ))
                meta["rejected"] += 1
                continue

            if brand.lower() in ANALOG_BRAND_BLACKLIST:
                issues.append(ValidationIssue(
                    gate="analog_compatibility",
                    severity="warning",
                    code="BLACKLISTED_BRAND",
                    message=f"Аналог с подозрительным брендом '{brand}' для артикула '{article}'",
                    context={"brand": brand, "article": article},
                ))
                meta["rejected"] += 1
                continue

            # Проверяем, не совпадает ли аналог с оригиналом
            if pos_oem and _normalize_oem(article) == _normalize_oem(pos_oem):
                issues.append(ValidationIssue(
                    gate="analog_compatibility",
                    severity="warning",
                    code="ANALOG_EQUALS_OEM",
                    message=(
                        f"Аналог '{brand} {article}' совпадает с оригинальным артикулом '{pos_oem}' "
                        f"после нормализации — не является аналогом."
                    ),
                    context={"brand": brand, "article": article, "position_oem": pos_oem},
                ))
                meta["rejected"] += 1
                continue

            meta["accepted"] += 1

        passed = meta["rejected"] == 0 or meta["accepted"] > 0
        return GateResult(gate_name="analog_compatibility", passed=passed, issues=issues, meta=meta)


# ──────────────────────────────────────────────
# ШЛЮЗ 4: CIRCUIT BREAKER STATUS CHECK
# ──────────────────────────────────────────────

class ScraperHealthChecker:
    """
    Проверяет текущее состояние Circuit Breaker-ов для всех поставщиков.
    Даёт предупреждение, если хотя бы один поставщик недоступен.
    """

    def run(self, circuit_statuses: dict[str, dict[str, Any]]) -> GateResult:
        issues: list[ValidationIssue] = []
        meta: dict[str, Any] = {"sources_checked": 0, "open_circuits": 0}

        for source, status in circuit_statuses.items():
            meta["sources_checked"] += 1
            if status.get("is_open"):
                issues.append(ValidationIssue(
                    gate="scraper_health",
                    severity="warning",
                    code="CIRCUIT_OPEN",
                    message=(
                        f"Circuit breaker OPEN для {source}: "
                        f"{status.get('failures', '?')} последовательных ошибок. "
                        f"Данные этого поставщика недоступны."
                    ),
                    context={"source": source, **status},
                ))
                meta["open_circuits"] += 1

        passed = meta["open_circuits"] == 0
        return GateResult(gate_name="scraper_health", passed=passed, issues=issues, meta=meta)


# ──────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ──────────────────────────────────────────────

def _normalize_oem(article: str) -> str:
    return re.sub(r"[\s\-\./]", "", article).upper()


# ──────────────────────────────────────────────
# ГЛАВНАЯ ТОЧКА ВХОДА: run_full_validation
# ──────────────────────────────────────────────

def run_full_validation(
    *,
    tenant_id: str,
    request_id: str,
    prices_by_article: dict[str, dict[str, Optional[float]]],
    evidence_records: list[dict[str, Any]],
    analogs: list[dict[str, Any]],
    circuit_statuses: dict[str, dict[str, Any]],
) -> ValidationReport:
    """
    Запускает все 4 шлюза валидации и возвращает агрегированный ValidationReport.

    Параметры:
      prices_by_article — {oem: {source: price_or_None}}
      evidence_records  — [{article, source, screenshot_ref, screenshot_sha256, price}]
      analogs           — [{brand, article, position_oem}]
      circuit_statuses  — {source: {state, is_open, failures}}
    """
    report = ValidationReport(tenant_id=tenant_id, request_id=request_id)

    # Gate 1: Аномалии цен
    report.gates.append(
        PriceAnomalyDetector().run(prices_by_article, tenant_id, request_id)
    )

    # Gate 2: Целостность доказательств
    report.gates.append(
        EvidenceIntegrityAuditor().run(evidence_records, tenant_id, request_id)
    )

    # Gate 3: Совместимость аналогов
    report.gates.append(
        AnalogCompatibilityChecker().run(analogs, tenant_id, request_id)
    )

    # Gate 4: Доступность скраперов (Circuit Breaker)
    report.gates.append(
        ScraperHealthChecker().run(circuit_statuses)
    )

    return report
