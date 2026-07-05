"""CLI entrypoint for automation job execution."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from app.automation.context import build_context
from app.automation.registry import get_job


def load_payload(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run automation jobs via CLI")
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--payload-path", default=None)
    parser.add_argument("--payload-json", default="{}")
    parser.add_argument("--pretty", action="store_true", default=False)
    options = parser.parse_args(argv)
    payload: dict[str, Any] = {}
    if options.payload_path:
        payload = load_payload(options.payload_path)
    else:
        try:
            payload = json.loads(options.payload_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"payload-json must be valid JSON: {exc}")
    context = build_context(
        tenant_id=options.tenant_id,
        request_id=options.request_id,
        dry_run=options.dry_run,
        **payload,
    )
    func = get_job(options.job_name)
    output = func(session=None, context=context)
    if options.pretty:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
