"""CLI entrypoint for policy evaluation."""
from __future__ import annotations

import argparse
import json
import sys

from app.automation.context import build_context
from app.automation.rules import policy_check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate automation policies via CLI")
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--payload", default="{}", help="JSON payload string")
    parser.add_argument("--pretty", action="store_true", default=False)
    options = parser.parse_args(argv)
    try:
        payload = json.loads(options.payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"payload must be valid JSON: {exc}")
    context = build_context(
        tenant_id=options.tenant_id,
        request_id=options.request_id,
        dry_run=options.dry_run,
        **payload,
    )
    output = policy_check(context)
    if options.pretty:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(output, ensure_ascii=False))
    return 1 if output.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
