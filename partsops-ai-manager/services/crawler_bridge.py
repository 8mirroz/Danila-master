"""
CrawlerBridge — мост между partsops-ai-manager и my-crawler.

Запускает реальный Playwright-скрапер (my_crawler) через subprocess,
читает результаты и перемещает скриншоты в storage/evidence/ через EvidenceManager.

Архитектура браузерных профилей (управляемая):
  ~/.partsops-browser-profiles/
    exist/    ← Playwright persistent context (cookie-сессия Exist.ru)
    autodoc/  ← Playwright persistent context (cookie-сессия Autodoc.ru)
    rossko/   ← Playwright persistent context (cookie-сессия Rossko.ru)
    .meta/    ← JSON-метаданные: время авторизации, статус

Переменные окружения для переопределения:
  BROWSER_PROFILE_BASE     — базовая папка (заменяет ~/.partsops-browser-profiles)
  EXIST_BROWSER_PROFILE_DIR — конкретный профиль Exist.ru
  AUTODOC_BROWSER_PROFILE_DIR
  ROSSKO_BROWSER_PROFILE_DIR
  CRAWLER_ROOT             — путь к директории my-crawler (авто-определяется)
  HEADLESS                 — 1/0 (1 = headless режим, по умолчанию 1)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from services.evidence_manager import (
    EvidenceManager,
    get_browser_profile_dir,
    record_auth_timestamp,
    _clean_oem,
)


# ──────────────────────────────────────────────
# РАСПОЛОЖЕНИЕ my-crawler
# ──────────────────────────────────────────────

def _find_crawler_root() -> Path:
    """
    Определяет путь к директории my-crawler.
    Приоритет:
      1. CRAWLER_ROOT (env)
      2. ../my-crawler относительно partsops-ai-manager
    """
    env_val = os.environ.get("CRAWLER_ROOT", "").strip()
    if env_val:
        return Path(env_val).expanduser().resolve()

    # Автоопределение: partsops-ai-manager/../my-crawler
    here = Path(__file__).parent.parent  # partsops-ai-manager/
    candidate = (here.parent / "my-crawler").resolve()
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"my-crawler не найден. Укажите CRAWLER_ROOT в .env или разместите "
        f"my-crawler рядом с partsops-ai-manager."
    )


CRAWLER_ROOT = None  # Ленивая инициализация


def get_crawler_root() -> Path:
    global CRAWLER_ROOT
    if CRAWLER_ROOT is None:
        CRAWLER_ROOT = _find_crawler_root()
    return CRAWLER_ROOT


# ──────────────────────────────────────────────
# ИСТОЧНИК → ПОСТАВЩИК
# ──────────────────────────────────────────────

SOURCE_TO_SUPPLIER_ID = {
    "exist": "sup_exist",
    "exist.ru": "sup_exist",
    "autodoc": "sup_autodoc",
    "autodoc.ru": "sup_autodoc",
    "rossko": "sup_rossko",
    "rossko.ru": "sup_rossko",
}

SOURCE_LABELS = ["exist", "autodoc", "rossko"]


# ──────────────────────────────────────────────
# РЕЗУЛЬТАТ ПАРСИНГА
# ──────────────────────────────────────────────

@dataclass
class CrawlerItem:
    """Нормализованная запись результата из my-crawler."""
    site: str                          # exist | autodoc | rossko
    supplier_id: str
    article: str                       # оригинальный артикул (как запрошено)
    brand: str
    part_name: str
    price: Optional[float]
    currency: str = "RUB"
    availability: str = "unknown"
    delivery: str = ""
    source_url: str = ""
    screenshot_path: Optional[str] = None   # путь в my-crawler/screenshots/
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.price is not None and self.price > 0


@dataclass
class CrawlerRunResult:
    """Итоговый результат одного прогона my-crawler."""
    tenant_id: str
    request_id: str
    articles: list[str]
    items: list[CrawlerItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    exit_code: int = 0

    def items_for(self, site: str) -> list[CrawlerItem]:
        return [i for i in self.items if i.site == site]

    def best_price_for(self, article: str) -> Optional[float]:
        prices = [
            i.price for i in self.items
            if _clean_oem(i.article) == _clean_oem(article) and i.is_success and i.price
        ]
        return min(prices) if prices else None


# ──────────────────────────────────────────────
# ПАРСИНГ РЕЗУЛЬТАТОВ MY-CRAWLER
# ──────────────────────────────────────────────

_PRICE_RE = re.compile(r"([\d]+(?:[.,]\d+)?)")


def _parse_price(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).replace("\xa0", "").replace(" ", "").replace(",", ".")
    m = _PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _normalize_items(raw_records: list[dict]) -> list[CrawlerItem]:
    """Нормализует записи из aggregated_parts.json в CrawlerItem."""
    items = []
    for rec in raw_records:
        site = str(rec.get("site") or rec.get("source") or "").lower().strip()
        if site not in SOURCE_LABELS and site not in SOURCE_TO_SUPPLIER_ID:
            continue

        # Нормализуем site к короткому виду (exist, autodoc, rossko)
        site_short = site.split(".")[0]
        supplier_id = SOURCE_TO_SUPPLIER_ID.get(site_short, f"sup_{site_short}")

        article = str(rec.get("article") or rec.get("part_number") or "").strip()
        if not article:
            continue

        screenshot = rec.get("screenshot_path") or rec.get("screenshot_ref") or rec.get("screenshot")
        price = _parse_price(rec.get("price") or rec.get("price_rub"))

        items.append(CrawlerItem(
            site=site_short,
            supplier_id=supplier_id,
            article=article,
            brand=str(rec.get("brand") or "").strip(),
            part_name=str(rec.get("part_name") or rec.get("description") or "").strip(),
            price=price,
            currency="RUB",
            availability=str(rec.get("availability") or rec.get("availability_status") or "unknown"),
            delivery=str(rec.get("delivery") or rec.get("delivery_days") or ""),
            source_url=str(rec.get("source_url") or rec.get("url") or ""),
            screenshot_path=str(screenshot) if screenshot else None,
            captured_at=str(rec.get("captured_at") or rec.get("timestamp") or datetime.now(timezone.utc).isoformat()),
            raw=rec,
        ))
    return items


# ──────────────────────────────────────────────
# ЗАПУСК my-crawler ЧЕРЕЗ SUBPROCESS
# ──────────────────────────────────────────────

def _build_env(sites: list[str]) -> dict[str, str]:
    """Строит env для subprocess с профилями браузера."""
    env = os.environ.copy()
    env["HEADLESS"] = os.environ.get("HEADLESS", "1")

    # Передаём пути к персистентным профилям для каждого сайта
    for site in sites:
        profile_dir = get_browser_profile_dir(site)
        prefix = {"exist": "EXIST", "autodoc": "AUTODOC", "rossko": "ROSSKO"}.get(site, site.upper())
        env[f"{prefix}_BROWSER_PROFILE_DIR"] = str(profile_dir)

    return env


def _write_articles_file(articles: list[str], path: Path) -> None:
    """Записывает список артикулов в articles.txt."""
    path.write_text(
        "\n".join(a for a in articles if a.strip()),
        encoding="utf-8",
    )


def run_crawler_subprocess(
    articles: list[str],
    sites: Optional[list[str]] = None,
    timeout_seconds: int = 300,
) -> tuple[int, Path]:
    """
    Запускает my-crawler через subprocess.
    Возвращает (exit_code, results_dir).
    """
    crawler_root = get_crawler_root()
    articles_path = crawler_root / "articles.txt"
    results_dir = crawler_root / "results"

    # Записываем артикулы
    _write_articles_file(articles, articles_path)

    # Определяем Python-интерпретатор из venv my-crawler
    venv_python = crawler_root / ".venv" / "bin" / "python"
    python_exe = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [python_exe, "-m", "my_crawler.main"]
    active_sites = sites or SOURCE_LABELS
    env = _build_env(active_sites)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(crawler_root),
            env=env,
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
        )
        return proc.returncode, results_dir
    except subprocess.TimeoutExpired:
        return -1, results_dir
    except Exception as exc:  # noqa: BLE001
        return -2, results_dir


# ──────────────────────────────────────────────
# ГЛАВНАЯ ФУНКЦИЯ МОСТА
# ──────────────────────────────────────────────

def run_crawler_for_articles(
    articles: list[str],
    tenant_id: str,
    request_id: str,
    sites: Optional[list[str]] = None,
    timeout_seconds: int = 300,
) -> CrawlerRunResult:
    """
    Запускает my-crawler для указанных артикулов и возвращает CrawlerRunResult.
    Скриншоты автоматически перемещаются в storage/evidence/{tenant_id}/{request_id}/.
    """
    result = CrawlerRunResult(
        tenant_id=tenant_id,
        request_id=request_id,
        articles=articles,
    )
    active_sites = sites or SOURCE_LABELS
    em = EvidenceManager(tenant_id, request_id)

    try:
        exit_code, results_dir = run_crawler_subprocess(articles, active_sites, timeout_seconds)
        result.exit_code = exit_code

        if exit_code not in (0,):
            result.errors.append(f"Краулер завершился с кодом {exit_code}")
            return result

        # Читаем aggregated_parts.json
        json_path = results_dir / "aggregated_parts.json"
        if not json_path.exists():
            result.errors.append("aggregated_parts.json не найден: краулер не создал результатов")
            return result

        raw_records: list[dict] = json.loads(json_path.read_text(encoding="utf-8"))
        items = _normalize_items(raw_records)

        # Перемещаем скриншоты в стандартизированное хранилище
        for item in items:
            if item.screenshot_path:
                src = Path(item.screenshot_path)
                try:
                    rec = em.ingest(
                        src_path=src,
                        supplier_id=item.supplier_id,
                        oem=item.article,
                        artifact_type="orig",
                        source_url=item.source_url,
                        captured_at=item.captured_at,
                    )
                    item.screenshot_path = str(rec.path)
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(f"Ошибка переноса скриншота {src}: {exc}")

        result.items = items

    except FileNotFoundError as exc:
        result.errors.append(f"my-crawler не найден: {exc}")
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"Непредвиденная ошибка краулера: {exc}")
    finally:
        result.completed_at = datetime.now(timezone.utc).isoformat()

    return result


def sync_results_to_evidence(
    run_result: CrawlerRunResult,
    session: Any,
) -> list[dict[str, Any]]:
    """
    Сохраняет результаты краулера в БД как PriceEvidence.
    Возвращает список созданных записей (словарей).
    Импорт Session и PriceEvidence делается локально, чтобы избежать циклов.
    """
    from sqlmodel import Session as _Session  # noqa: F401
    from models import PriceEvidence
    import uuid
    from datetime import datetime as _dt, timezone as _tz

    created = []
    for item in run_result.items:
        if not item.is_success:
            continue

        evidence = PriceEvidence(
            evidence_id=f"EV-{uuid.uuid4().hex[:12].upper()}",
            request_id=run_result.request_id,
            position_id=item.article,
            tenant_id=run_result.tenant_id,
            source=f"{item.site}.ru",
            price=item.price if item.price is not None else 0.0,
            currency=item.currency,
            source_url=item.source_url,
            captured_at=_dt.fromisoformat(item.captured_at.replace("Z", "+00:00"))
                        if item.captured_at else _dt.now(_tz.utc),
            screenshot_ref=item.screenshot_path or "",
            availability_status=item.availability,
            order_status="observed",
        )
        session.add(evidence)
        created.append(evidence.model_dump())

    session.commit()
    return created
