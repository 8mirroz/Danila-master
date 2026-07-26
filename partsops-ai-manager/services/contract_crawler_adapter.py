"""Normalize my-crawler output into Contract Operations price evidence rows."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException

ALLOWED_SOURCES = {"exist.ru", "autodoc.ru", "rossko.ru"}


def parse_crawler_price(value: object) -> float:
    text = str(value or "").strip()
    if not text or text == "--" or text == "——":
        raise ValueError("empty price")
    cleaned = re.sub(r"[^\d,.\-]", "", text.replace("\xa0", "").replace(" ", "")).replace(",", ".")
    if not cleaned:
        raise ValueError("empty price")
    return float(cleaned)


def load_crawler_payload(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("Crawler result must be a JSON array or {items: []}")
    return rows


def normalize_crawler_rows(rows: list[dict[str, Any]], source_base: Path | None = None,
                           require_absolute_screenshots: bool = False) -> tuple[list[dict[str, Any]], dict[str, int]]:
    normalized: list[dict[str, Any]] = []
    stats = {"input": len(rows), "normalized": 0, "skipped": 0, "duplicates": 0}
    seen: set[tuple[str, str, str, str]] = set()
    base = source_base or Path.cwd()

    for row in rows:
        try:
            source = str(row.get("source") or row.get("site") or "").lower().strip()
            if source not in ALLOWED_SOURCES:
                raise ValueError("unsupported source")
            article = str(row.get("part_number") or row.get("search_article") or row.get("article") or "").strip()
            url = str(row.get("source_url") or row.get("url") or row.get("product_url") or "").strip()
            screenshot = str(row.get("screenshot_ref") or row.get("screenshot_path") or row.get("screenshot") or "").strip()
            captured = row.get("captured_at") or row.get("capturedAt") or row.get("timestamp")
            price = parse_crawler_price(row.get("price"))
            if not article or not url or not screenshot or not captured:
                raise ValueError("missing required field")
            screenshot_path = Path(screenshot).expanduser()
            if require_absolute_screenshots and not screenshot_path.is_absolute():
                raise ValueError("relative screenshot path")
            if not screenshot_path.is_absolute():
                screenshot_path = (base / screenshot_path).resolve()
            key = (source, article, url, str(screenshot_path))
            if key in seen:
                stats["duplicates"] += 1
                continue
            seen.add(key)
            normalized.append({
                "part_number": article,
                "source": source,
                "price": price,
                "source_url": url,
                "captured_at": captured,
                "screenshot_ref": str(screenshot_path),
                "availability_status": row.get("availability_status") or row.get("availability") or "available",
                "package_quantity": row.get("package_quantity") or row.get("pack_qty") or 1,
                "unit": row.get("unit") or "piece",
                "condition": row.get("condition") or "new",
                "available_quantity": row.get("available_quantity") or row.get("stock_qty"),
                "warehouse": row.get("warehouse"),
                "delivery_region": row.get("delivery_region"),
                "delivery_eta_days": row.get("delivery_eta_days") or row.get("delivery_days"),
                "order_status": row.get("order_status") or "observed",
                "html_snapshot": row.get("html_snapshot"),
                "adapter_run_id": row.get("adapter_run_id") or row.get("run_id"),
                "parser_version": row.get("parser_version"),
                "retry_count": row.get("retry_count") or 0,
                "unavailable_reason": row.get("unavailable_reason"),
                "freshness_ttl_hours": row.get("freshness_ttl_hours"),
            })
        except (TypeError, ValueError):
            stats["skipped"] += 1

    stats["normalized"] = len(normalized)
    return normalized, stats


def normalize_uploaded_crawler_payload(raw: bytes, filename: str | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Crawler upload must be UTF-8 JSON") from exc
    rows = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="Crawler upload must be a JSON array or {items: []}")
    return normalize_crawler_rows(rows, Path.cwd(), require_absolute_screenshots=True)
