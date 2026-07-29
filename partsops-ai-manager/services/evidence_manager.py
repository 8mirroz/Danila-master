"""
EvidenceManager — единый менеджер скриншотов доказательств цен.

Архитектура хранилища:
    partsops-ai-manager/storage/evidence/
      {tenant_id}/
        {request_id}/
          index.json                               ← манифест пакета
          {supplier_id}_{clean_oem}_orig.png       ← цена оригинала
          {supplier_id}_{clean_oem}_analog_{art}.png ← цена аналога
          archive/
            {request_id}_evidence_pack.zip         ← ZIP для внутреннего пользования

Классификация типов:
    orig   — страница с ценой оригинального артикула
    analog — страница с ценой аналога
    debug  — служебный скриншот (не включается в архив)

Архитектура браузерных профилей (улучшенная):
    ~/.partsops-browser-profiles/            ← контролируемое место
      exist/   → persistent Chromium profile
      autodoc/ → persistent Chromium profile
      rossko/  → persistent Chromium profile
      .meta/   → metadata: last_auth_{site}.json (время, статус)

    Переопределение через .env:
      BROWSER_PROFILE_BASE=/custom/path    ← базовая папка (альт.)
      EXIST_BROWSER_PROFILE_DIR=/path      ← конкретный сайт
      AUTODOC_BROWSER_PROFILE_DIR=/path
      ROSSKO_BROWSER_PROFILE_DIR=/path
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
import re
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ──────────────────────────────────────────────
# КОНСТАНТЫ
# ──────────────────────────────────────────────

EVIDENCE_ROOT = Path("storage/evidence")
ARCHIVE_SUBDIR = "archive"
INDEX_FILENAME = "index.json"

ALLOWED_TYPES = {"orig", "analog", "debug"}

# Расширения, которые принимаются как скриншот
VALID_SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


# ──────────────────────────────────────────────
# КОНФИГУРАЦИЯ БРАУЗЕРНЫХ ПРОФИЛЕЙ (улучшенная)
# ──────────────────────────────────────────────

_SITE_ENV_PREFIX = {
    "exist": "EXIST",
    "autodoc": "AUTODOC",
    "rossko": "ROSSKO",
}


def get_browser_profile_base() -> Path:
    """
    Возвращает базовую директорию для профилей браузера.

    Приоритет:
        1. BROWSER_PROFILE_BASE (env)
        2. ~/.partsops-browser-profiles (дефолт — изолированный, не в проекте)
    """
    custom = os.environ.get("BROWSER_PROFILE_BASE", "").strip()
    if custom:
        return Path(custom).expanduser()
    return Path.home() / ".partsops-browser-profiles"


def get_browser_profile_dir(site: str) -> Path:
    """
    Возвращает путь к персистентному профилю Playwright для конкретного сайта.

    Приоритет:
        1. {SITE}_BROWSER_PROFILE_DIR (env, per-site override)
        2. BROWSER_PROFILE_BASE/{site}/ (группа)
        3. ~/.partsops-browser-profiles/{site}/ (дефолт)
    """
    prefix = _SITE_ENV_PREFIX.get(site, site.upper())
    per_site = os.environ.get(f"{prefix}_BROWSER_PROFILE_DIR", "").strip()
    if per_site:
        path = Path(per_site).expanduser()
    else:
        path = get_browser_profile_base() / site
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    return path


def get_browser_profile_meta_dir() -> Path:
    """Путь к директории .meta/ с метаданными авторизации."""
    meta = get_browser_profile_base() / ".meta"
    meta.mkdir(parents=True, exist_ok=True)
    return meta


def record_auth_timestamp(site: str) -> None:
    """Записывает время последней успешной авторизации в .meta/last_auth_{site}.json"""
    meta_file = get_browser_profile_meta_dir() / f"last_auth_{site}.json"
    meta_file.write_text(
        json.dumps({
            "site": site,
            "auth_at": datetime.now(timezone.utc).isoformat(),
            "profile_dir": str(get_browser_profile_dir(site)),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_auth_status(site: str) -> dict[str, Any]:
    """Возвращает статус авторизации для сайта из .meta/."""
    meta_file = get_browser_profile_meta_dir() / f"last_auth_{site}.json"
    if not meta_file.exists():
        return {"site": site, "auth_at": None, "profile_exists": False}
    data = json.loads(meta_file.read_text(encoding="utf-8"))
    data["profile_exists"] = get_browser_profile_dir(site).exists()
    return data


def get_all_profiles_status() -> dict[str, dict[str, Any]]:
    """Возвращает статус авторизации всех 3 поставщиков."""
    return {site: get_auth_status(site) for site in _SITE_ENV_PREFIX}


# ──────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ──────────────────────────────────────────────

def _clean_oem(article: str) -> str:
    return re.sub(r"[\s\-\./]", "", article).upper()


def _sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or path.stat().st_size == 0:
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _evidence_root(tenant_id: str, request_id: str) -> Path:
    p = EVIDENCE_ROOT / tenant_id / request_id
    p.mkdir(parents=True, exist_ok=True)
    return p


# ──────────────────────────────────────────────
# ЗАПИСЬ МЕТАДАННЫХ (dataclass)
# ──────────────────────────────────────────────

@dataclass
class EvidenceRecord:
    supplier_id: str
    oem: str
    artifact_type: str           # orig | analog | debug
    path: Path
    sha256: Optional[str] = None
    size_bytes: int = 0
    is_real: bool = False        # False = placeholder (<100 bytes)
    captured_at: Optional[str] = None
    source_url: Optional[str] = None
    analog_oem: Optional[str] = None  # только для artifact_type=analog

    def to_dict(self) -> dict[str, Any]:
        return {
            "supplier_id": self.supplier_id,
            "oem": self.oem,
            "artifact_type": self.artifact_type,
            "path": str(self.path),
            "file_url": f"file://{self.path}",
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "is_real": self.is_real,
            "captured_at": self.captured_at,
            "source_url": self.source_url,
            "analog_oem": self.analog_oem,
        }


# ──────────────────────────────────────────────
# ОСНОВНОЙ МЕНЕДЖЕР
# ──────────────────────────────────────────────

class EvidenceManager:
    """
    Единый менеджер скриншотов для пакета сбора (request_id).
    Управляет: приёмом, перемещением, SHA-256, классификацией, индексом, архивом.
    """

    def __init__(self, tenant_id: str, request_id: str):
        self.tenant_id = tenant_id
        self.request_id = request_id
        self.root = _evidence_root(tenant_id, request_id)

    def build_filename(
        self,
        supplier_id: str,
        oem: str,
        artifact_type: str,
        analog_oem: Optional[str] = None,
    ) -> str:
        """
        Детерминированное имя файла по стандарту архитектуры:
          orig   → {supplier_id}_{clean_oem}_orig.png
          analog → {supplier_id}_{clean_oem}_analog_{clean_analog_oem}.png
          debug  → {supplier_id}_{clean_oem}_debug.png
        """
        assert artifact_type in ALLOWED_TYPES, f"Недопустимый тип: {artifact_type}"
        clean = _clean_oem(oem)
        if artifact_type == "analog" and analog_oem:
            clean_anl = _clean_oem(analog_oem)
            return f"{supplier_id}_{clean}_analog_{clean_anl}.png"
        return f"{supplier_id}_{clean}_{artifact_type}.png"

    def get_path(
        self,
        supplier_id: str,
        oem: str,
        artifact_type: str,
        analog_oem: Optional[str] = None,
    ) -> Path:
        """Полный путь к файлу скриншота."""
        return self.root / self.build_filename(supplier_id, oem, artifact_type, analog_oem)

    def ingest(
        self,
        src_path: Path | str,
        supplier_id: str,
        oem: str,
        artifact_type: str,
        analog_oem: Optional[str] = None,
        source_url: Optional[str] = None,
        captured_at: Optional[str] = None,
    ) -> EvidenceRecord:
        """
        Принимает скриншот из произвольного источника (my-crawler/screenshots/),
        перемещает в правильный путь, вычисляет SHA-256.
        """
        src = Path(src_path)
        if src.suffix.lower() not in VALID_SCREENSHOT_EXTENSIONS:
            raise ValueError(f"Неподдерживаемое расширение: {src.suffix}")

        dest = self.get_path(supplier_id, oem, artifact_type, analog_oem)

        if src.exists():
            shutil.copy2(src, dest)
        else:
            # Создаём placeholder если источника нет
            dest.touch()

        sha = _sha256_file(dest)
        size = dest.stat().st_size if dest.exists() else 0
        is_real = size >= 100  # < 100 байт = placeholder

        return EvidenceRecord(
            supplier_id=supplier_id,
            oem=oem,
            artifact_type=artifact_type,
            path=dest,
            sha256=sha,
            size_bytes=size,
            is_real=is_real,
            captured_at=captured_at or datetime.now(timezone.utc).isoformat(),
            source_url=source_url,
            analog_oem=analog_oem,
        )

    def ensure_placeholder(
        self,
        supplier_id: str,
        oem: str,
        artifact_type: str,
        analog_oem: Optional[str] = None,
    ) -> Path:
        """Создаёт placeholder-файл если скриншота ещё нет."""
        path = self.get_path(supplier_id, oem, artifact_type, analog_oem)
        if not path.exists():
            path.touch()
        return path

    def list_records(self, exclude_debug: bool = True) -> list[EvidenceRecord]:
        """
        Читает все файлы в директории пакета и возвращает список EvidenceRecord.
        Парсит имена файлов по стандарту архитектуры.
        """
        records = []
        for f in sorted(self.root.glob("*.png")):
            parsed = self._parse_filename(f.name)
            if not parsed:
                continue
            if exclude_debug and parsed.get("artifact_type") == "debug":
                continue
            sha = _sha256_file(f)
            size = f.stat().st_size
            records.append(EvidenceRecord(
                supplier_id=parsed["supplier_id"],
                oem=parsed["oem"],
                artifact_type=parsed["artifact_type"],
                path=f,
                sha256=sha,
                size_bytes=size,
                is_real=size >= 100,
                analog_oem=parsed.get("analog_oem"),
            ))
        return records

    def build_index(self) -> dict[str, Any]:
        """
        Создаёт index.json — полный манифест пакета скриншотов.
        """
        records = self.list_records(exclude_debug=False)
        stats = self.get_stats()
        index: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "request_id": self.request_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "records": [r.to_dict() for r in records],
        }
        index_path = self.root / INDEX_FILENAME
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return index

    def get_stats(self) -> dict[str, int]:
        """Статистика: всего файлов, реальных, placeholder, пустых."""
        records = self.list_records(exclude_debug=False)
        return {
            "total": len(records),
            "real": sum(1 for r in records if r.is_real),
            "placeholders": sum(1 for r in records if not r.is_real),
            "orig_count": sum(1 for r in records if r.artifact_type == "orig"),
            "analog_count": sum(1 for r in records if r.artifact_type == "analog"),
        }

    def pack_archive(self) -> Path:
        """
        Упаковывает все РЕАЛЬНЫЕ скриншоты + index.json в ZIP-архив.
        Архив только для внутреннего использования.
        Путь: storage/evidence/{tenant_id}/{request_id}/archive/{request_id}_evidence_pack.zip
        """
        archive_dir = self.root / ARCHIVE_SUBDIR
        archive_dir.mkdir(exist_ok=True)
        archive_path = archive_dir / f"{self.request_id}_evidence_pack.zip"

        # Пересоздаём index перед упаковкой
        self.build_index()

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Добавляем index.json
            index_p = self.root / INDEX_FILENAME
            if index_p.exists():
                zf.write(index_p, INDEX_FILENAME)

            # Добавляем только реальные скриншоты (> 100 байт)
            for f in sorted(self.root.glob("*.png")):
                if f.stat().st_size >= 100:
                    zf.write(f, f.name)

        return archive_path

    @staticmethod
    def _parse_filename(name: str) -> Optional[dict[str, str]]:
        """
        Разбирает имена файлов по шаблонам архитектуры:
          {supplier_id}_{clean_oem}_orig.png
          {supplier_id}_{clean_oem}_analog_{analog_oem}.png
          {supplier_id}_{clean_oem}_debug.png
        """
        name = name.removesuffix(".png")

        # analog: {sup}_{oem}_analog_{analog_oem}
        m = re.match(r"^([^_]+)_(.+)_analog_(.+)$", name)
        if m:
            return {
                "supplier_id": m.group(1),
                "oem": m.group(2),
                "artifact_type": "analog",
                "analog_oem": m.group(3),
            }

        # orig / debug: {sup}_{oem}_{type}
        m = re.match(r"^([^_]+)_(.+)_(orig|debug)$", name)
        if m:
            return {
                "supplier_id": m.group(1),
                "oem": m.group(2),
                "artifact_type": m.group(3),
            }

        return None


# ──────────────────────────────────────────────
# ФАБРИЧНАЯ ФУНКЦИЯ
# ──────────────────────────────────────────────

def get_evidence_manager(tenant_id: str, request_id: str) -> EvidenceManager:
    """Возвращает EvidenceManager для данного пакета сбора."""
    return EvidenceManager(tenant_id=tenant_id, request_id=request_id)
