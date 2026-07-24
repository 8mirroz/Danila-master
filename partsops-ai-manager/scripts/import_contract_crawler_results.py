"""Import evidence produced by the existing my-crawler into Contract Operations.

This is an adapter handoff, not a second catalog: it writes only PriceEvidence
for an already-created contract request. No network or LLM call is performed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import engine, init_db
from services.contract_operations import collect_evidence
from sqlmodel import Session, select
from models import ContractPosition


def parse_price(value: object) -> float:
    text = str(value or "").replace("₽", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    return float(text)


def load_rows(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("Crawler result must be a JSON array or {items: []}")
    result = []
    for row in rows:
        if row.get("price") in (None, "", "——"):
            continue
        result.append({**row, "price": parse_price(row["price"])})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = load_rows(args.source)
    if args.dry_run:
        print(json.dumps({"request_id": args.request_id, "rows": len(rows), "dry_run": True}, ensure_ascii=False))
        return 0
    init_db()
    with Session(engine) as session:
        positions = session.exec(select(ContractPosition).where(
            ContractPosition.request_id == args.request_id,
            ContractPosition.tenant_id == args.tenant_id)).all()
        if not positions:
            raise ValueError("Contract request or tenant not found")
        result = collect_evidence(session, args.request_id, args.tenant_id, rows, "my-crawler")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
