"""
PartsOps Bot — config.

Reads from ~/.hermes/profiles/zera/.env.partsops:
- PARTSOPS_TG_TOKEN
- PARTSOPS_TG_BOT_USERNAME (optional)
- PARTSOPS_OPERATOR_IDS (comma-separated, optional)
- PARTSOPS_DB_PATH (optional)
- PARTSOPS_LOG_LEVEL (optional)

Long-polling defaults. Webhook mode requires explicit enable.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("config")

ENV_FILE = Path("~/.hermes/profiles/zera/.env.partsops").expanduser()


def _read_env_file() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_FILE.exists():
        return out
    for raw in ENV_FILE.read_text(errors="replace").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


ENV = _read_env_file()


def _first(name: str, fallback: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v:
        return v
    v = ENV.get(name)
    return v or fallback


def _as_csv_int(name: str, fallback: list[int]) -> list[int]:
    raw = _first(name)
    if raw is None:
        return list(fallback)
    out: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            out.append(int(item, 10))
        except ValueError:
            continue
    return out or list(fallback)


def _level(name: str, fallback: str) -> str:
    v = (_first(name) or "").upper() or fallback
    return {"DEBUG": "DEBUG", "INFO": "INFO", "WARN": "WARNING", "WARNING": "WARNING", "ERROR": "ERROR", "CRITICAL": "CRITICAL"}.get(v, fallback)


CFG: dict = {
    "token": _first("PARTSOPS_TG_TOKEN") or "",
    "bot_username": _first("PARTSOPS_TG_BOT_USERNAME") or "bot",
    "operator_ids": _as_csv_int("PARTSOPS_OPERATOR_IDS", [0]),
    "db_path": _first(
        "PARTSOPS_DB_PATH", str(Path("~/.hermes/profiles/partsops/data/partsops.db").expanduser())
    ),
    "log_level_env": _level("PARTSOPS_LOG_LEVEL", "INFO"),
    "poll_timeout": int(_first("PARTSOPS_POLL_TIMEOUT") or 15),
    "webhook_enabled": False,
    "webhook_url": _first("PARTSOPS_WEBHOOK_URL"),
    "webhook_path": _first("PARTSOPS_WEBHOOK_PATH", "/partsops/tg"),
    "webhook_port": int(_first("PARTSOPS_WEBHOOK_PORT") or 8777),
    "debug": os.environ.get("PARTSOPS_DEBUG", "0").lower() in {"1", "true", "yes"},
}


def sanity_check() -> bool:
    ok = True
    if not CFG["token"]:
        logger.error("PARTSOPS_TG_TOKEN is not set — bot cannot start.")
        ok = False
    if CFG["db_path"] and not Path(CFG["db_path"]).parent.exists():
        try:
            Path(CFG["db_path"]).parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("cannot create DB dir %r: %r", CFG["db_path"], e)
            ok = False
    return ok


if __name__ == "__main__":
    # quick smoke test
    print(json.dumps({k: (v if k != "token" else (v[:10] + "…" if v else v)) for k, v in CFG.items()}, ensure_ascii=False, indent=2, default=str))
    print("sanity:", sanity_check())
