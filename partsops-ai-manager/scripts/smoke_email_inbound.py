#!/usr/bin/env python3
"""Local smoke: config → signed webhook → list → ingest → print request_id.

Usage:
  export PARTSOPS_API_TOKEN=test-token
  export PARTSOPS_EMAIL_WEBHOOK_SECRET=dev-secret-at-least-16
  export BASE_URL=http://127.0.0.1:8000
  python scripts/smoke_email_inbound.py
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ.get("PARTSOPS_API_TOKEN", "test-token")
SECRET = os.environ.get("PARTSOPS_EMAIL_WEBHOOK_SECRET", "")
TENANT = os.environ.get("PARTSOPS_TENANT_ID", "default")
SLUG = os.environ.get("EMAIL_ORG_SLUG", "default")
ADDRESS = os.environ.get("EMAIL_INBOX_ADDRESS", f"rfq+{SLUG}@inbound.local")


def _req(method: str, path: str, body: dict | None = None, *, signed: bool = False, role: str = "admin") -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Tenant-ID": TENANT,
        "X-User-Role": role,
        "Authorization": f"Bearer {TOKEN}",
    }
    if signed:
        if not SECRET:
            print("ERROR: set PARTSOPS_EMAIL_WEBHOOK_SECRET", file=sys.stderr)
            sys.exit(2)
        headers["X-PartsOps-Signature"] = "sha256=" + hmac.new(
            SECRET.encode("utf-8"), data or b"", hashlib.sha256
        ).hexdigest()
        # webhook does not need tenant role headers but harmless
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} {path}: {err}", file=sys.stderr)
        raise


def main() -> int:
    print(f"== smoke email inbound @ {BASE} tenant={TENANT}")

    cfg = _req(
        "PUT",
        "/api/email/config",
        {
            "org_slug": SLUG,
            "address": ADDRESS,
            "provider": "mailgun",
            "auto_ingest": False,
            "default_priority": "normal",
            "allowed_senders": [],
        },
        role="admin",
    )
    print("config:", json.dumps(cfg, ensure_ascii=False)[:200])

    csv = "Артикул;Наименование;Количество\nSMK-1;Smoke pad;1\n"
    payload = {
        "provider": "mailgun",
        "message_id": f"<smoke-{os.getpid()}@local>",
        "from": "smoke@partner.example",
        "to": [ADDRESS],
        "subject": "Smoke RFQ email",
        "text_body": "Smoke free-text: oil filter x1 OEM 11427566327",
        "attachments": [
            {
                "filename": "smoke.csv",
                "content_type": "text/csv",
                "bytes_base64": base64.b64encode(csv.encode("utf-8")).decode(),
            }
        ],
    }
    inbound = _req("POST", "/api/integrations/email/inbound", payload, signed=True, role="manager")
    print("inbound:", inbound)
    emsg = inbound.get("email_message_id")
    if not emsg:
        print("FAIL: no email_message_id", file=sys.stderr)
        return 1

    listed = _req("GET", "/api/email/messages", role="manager")
    print("list count:", len(listed) if isinstance(listed, list) else listed)

    stats_before = _req("GET", "/api/email/stats", role="manager")
    print("stats before ingest:", stats_before)
    if not isinstance(stats_before, dict) or "total" not in stats_before:
        print("FAIL: /api/email/stats missing total", file=sys.stderr)
        return 1
    for key in ("parsed", "ingested", "rejected", "received", "ingesting"):
        if key not in stats_before:
            print(f"FAIL: /api/email/stats missing key={key}", file=sys.stderr)
            return 1

    ingested = _req("POST", f"/api/email/messages/{emsg}/ingest", {}, role="manager")
    print("ingest:", ingested)
    rid = ingested.get("request_id")
    if not rid:
        print("FAIL: no request_id", file=sys.stderr)
        return 1

    stats_after = _req("GET", "/api/email/stats", role="manager")
    print("stats after ingest:", stats_after)
    if int(stats_after.get("ingested", 0)) < 1:
        print("FAIL: stats.ingested did not increase after ingest", file=sys.stderr)
        return 1

    # Idempotent second ingest must not create a second request
    again = _req("POST", f"/api/email/messages/{emsg}/ingest", {}, role="manager")
    if again.get("request_id") != rid:
        print(f"FAIL: second ingest request_id mismatch {again}", file=sys.stderr)
        return 1
    if again.get("idempotent") is not True:
        print(f"WARN: second ingest idempotent flag={again.get('idempotent')}", file=sys.stderr)

    # --- reject path honesty: second inbound → operator reject → no ingest ---
    reject_payload = {
        "provider": "mailgun",
        "message_id": f"<smoke-reject-{os.getpid()}@local>",
        "from": "noise@partner.example",
        "to": [ADDRESS],
        "subject": "Smoke reject me",
        "text_body": "not a real RFQ",
        "attachments": [],
    }
    inbound2 = _req("POST", "/api/integrations/email/inbound", reject_payload, signed=True, role="manager")
    emsg2 = inbound2.get("email_message_id")
    if not emsg2:
        print("FAIL: no email_message_id for reject path", file=sys.stderr)
        return 1

    stats_pre_reject = _req("GET", "/api/email/stats", role="manager")
    rejected_before = int(stats_pre_reject.get("rejected", 0))

    rejected = _req(
        "POST",
        f"/api/email/messages/{emsg2}/reject",
        {"reason": "smoke_operator_reject"},
        role="manager",
    )
    if rejected.get("status") != "rejected":
        print(f"FAIL: reject status={rejected}", file=sys.stderr)
        return 1
    if rejected.get("rejection_reason") != "smoke_operator_reject":
        print(f"FAIL: rejection_reason={rejected.get('rejection_reason')}", file=sys.stderr)
        return 1

    # Ingest after reject must fail (4xx)
    try:
        _req("POST", f"/api/email/messages/{emsg2}/ingest", {}, role="manager")
        print("FAIL: ingest after reject should not succeed", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as exc:
        if exc.code not in (409, 422):
            print(f"FAIL: expected 409/422 after reject, got {exc.code}", file=sys.stderr)
            return 1
        print(f"ingest-after-reject HTTP {exc.code} (expected)")

    # Idempotent reject
    rejected_again = _req(
        "POST",
        f"/api/email/messages/{emsg2}/reject",
        {"reason": "should_not_overwrite"},
        role="manager",
    )
    if rejected_again.get("status") != "rejected":
        print(f"FAIL: idempotent reject status={rejected_again}", file=sys.stderr)
        return 1
    if rejected_again.get("rejection_reason") != "smoke_operator_reject":
        print(
            f"FAIL: idempotent reject overwrote reason={rejected_again.get('rejection_reason')}",
            file=sys.stderr,
        )
        return 1

    stats_post_reject = _req("GET", "/api/email/stats", role="manager")
    if int(stats_post_reject.get("rejected", 0)) < rejected_before + 1:
        print(
            f"FAIL: stats.rejected did not increase ({rejected_before} → {stats_post_reject.get('rejected')})",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK request_id={rid} email_message_id={emsg} "
        f"rejected_id={emsg2} stats.rejected={stats_post_reject.get('rejected')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
