"""
PartsOps Bot — main entry point.

Long-polling Telegram bot for @autoparts_kot_bot.
Reads token from ~/.hermes/profiles/zera/.env.partsops (PARTSOPS_TG_TOKEN).
Whitelist operator TG IDs via PARTSOPS_OPERATOR_IDS (comma-sep).
"""

from __future__ import annotations

import dataclasses
import logging
import os
import signal
import ssl
import sys
import time
import urllib.parse
from pathlib import Path

import storage
from config import CFG
from router import Router


def _ssl_ctx() -> ssl.SSLContext:
    # pyhon-telegram-bot trusts default CA; Mac python3.14 + corp proxy sometimes
    # hiccups with self-signed MITM CA. We don't ship a CA bundle, so we relax
    # only for outbound Telegram calls. Production deployments should pin CA.
    ctx = ssl.create_default_context()
    if os.environ.get("PARTSOPS_INSECURE_SSL"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def setup_logging() -> None:
    level = logging.INFO if not CFG.get("debug") else logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


def install_signal_handlers(stop_evt) -> None:
    def _stop(signum, frame):
        log = logging.getLogger("signal")
        log.info("received signal %s, shutting down", signum)
        stop_evt.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)


def main() -> int:
    setup_logging()
    log = logging.getLogger("bot")

    storage.init_db(CFG["db_path"])
    log.info("storage ok at %s", CFG["db_path"])

    import threading
    stop = threading.Event()
    install_signal_handlers(stop)

    router = Router(token=CFG["token"], operators=set(CFG.get("operator_ids", [])))
    log.info(
        "router ready, operators=%s, poll_timeout=%s",
        CFG.get("operator_ids"), CFG.get("poll_timeout"),
    )

    # Hand over to polling loop. We use stdlib only — no extra deps.
    import json
    import urllib.request
    ctx = _ssl_ctx()
    offset = 0

    while not stop.is_set():
        body = json.dumps({
            "timeout": CFG.get("poll_timeout", 20),
            "limit": 50,
            "allowed_updates": ["message"],
            "offset": offset + 1,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{CFG['token']}/getUpdates",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=CFG.get("poll_timeout", 20) + 5, context=ctx) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            log.warning("getUpdates transient failure: %r; retry in 2s", e)
            time.sleep(2)
            continue

        if not data.get("ok"):
            log.error("getUpdates bad response: %r", data)
            time.sleep(2)
            continue

        for update in data.get("result", []):
            offset = max(offset, update.get("update_id", 0))
            try:
                router.dispatch(update)
            except Exception as e:
                log.exception("dispatch failed for update %s: %r", update.get("update_id"), e)

    log.info("bot stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
