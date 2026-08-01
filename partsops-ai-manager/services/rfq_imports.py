"""Tenant-safe RFQ spreadsheet preview and reusable mapping service."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from models import ImportMapping, UploadArtifact
from services.supplier_service import _parse_supplier_table_file

FIELDS = {"part_number", "description", "quantity", "brand"}
ALIASES = {
    "part_number": {"артикул", "номер", "oem", "part number", "sku", "article"},
    "description": {
        "наименование",
        "описание",
        "деталь",
        "позиция",
        "name",
        "description",
    },
    "quantity": {"количество", "qty", "quantity", "кол-во"},
    "brand": {"бренд", "марка", "brand", "manufacturer"},
}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _norm(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _mapping(headers: list[str], override: dict[str, str] | None) -> dict[str, str]:
    result = dict(override or {})
    for field, aliases in ALIASES.items():
        if field not in result:
            result[field] = next(
                (header for header in headers if _norm(header) in aliases), ""
            )
    return {
        key: value
        for key, value in result.items()
        if key in FIELDS and value in headers
    }


def preview(
    session: Session,
    organization_id: str,
    artifact_id: str,
    mapping: dict[str, str] | None = None,
    *,
    include_all: bool = False,
) -> dict[str, Any]:
    artifact = session.exec(
        select(UploadArtifact).where(
            UploadArtifact.artifact_id == artifact_id,
            UploadArtifact.tenant_id == organization_id,
        )
    ).first()
    if not artifact or artifact.status not in {"stored", "attached"}:
        raise HTTPException(404, "Import artifact not found")
    rows, file_type = _parse_supplier_table_file(
        artifact.stored_path, artifact.original_filename, artifact.content_type
    )
    headers = list(rows[0].keys()) if rows else []
    resolved = _mapping(headers, mapping)
    positions, invalid = [], 0
    for row in rows:
        number, description = (
            str(row.get(resolved.get("part_number", ""), "")).strip(),
            str(row.get(resolved.get("description", ""), "")).strip(),
        )
        try:
            quantity = max(
                1,
                int(
                    float(
                        str(row.get(resolved.get("quantity", ""), "1")).replace(
                            ",", "."
                        )
                    )
                ),
            )
        except ValueError:
            invalid += 1
            continue
        if not number and not description:
            invalid += 1
            continue
        positions.append(
            {
                "part_number": number,
                "description": description,
                "quantity": quantity,
                "brand": str(row.get(resolved.get("brand", ""), "")).strip(),
            }
        )
    result = {
        "artifact_id": artifact_id,
        "file_type": file_type,
        "headers": headers,
        "mapping": resolved,
        "rows_total": len(rows),
        "valid_positions": len(positions),
        "invalid_rows": invalid,
        "sample_positions": positions[:20],
        "requires_mapping": not bool(
            resolved.get("part_number") or resolved.get("description")
        ),
    }
    if include_all:
        result["positions"] = positions
    return result


def save_mapping(
    session: Session, organization_id: str, name: str, mapping: dict[str, str]
) -> ImportMapping:
    if not name.strip() or not mapping:
        raise HTTPException(422, "Mapping name and columns are required")
    if any(
        key not in FIELDS or not isinstance(value, str) or not value.strip()
        for key, value in mapping.items()
    ):
        raise HTTPException(422, "Invalid RFQ mapping")
    item = session.exec(
        select(ImportMapping).where(
            ImportMapping.organization_id == organization_id,
            ImportMapping.kind == "rfq",
            ImportMapping.name == name.strip(),
        )
    ).first()
    if item is None:
        item = ImportMapping(
            organization_id=organization_id,
            kind="rfq",
            name=name.strip(),
            mapping_json=json.dumps(mapping, ensure_ascii=False),
        )
    else:
        item.mapping_json, item.updated_at = (
            json.dumps(mapping, ensure_ascii=False),
            _now(),
        )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def build_rfq_text(import_preview: dict[str, Any]) -> str:
    """Turn confirmed spreadsheet rows into explicit RFQ input for the canonical intake service."""
    lines = []
    for position in import_preview.get("positions", import_preview["sample_positions"]):
        identity = " ".join(
            value
            for value in (
                position.get("part_number"),
                position.get("description"),
                position.get("brand"),
            )
            if value
        )
        lines.append(f"{identity} x{position['quantity']}")
    if not lines:
        raise HTTPException(422, "RFQ import contains no valid positions")
    return "\n".join(lines)


def import_idempotency_key(artifact_id: str) -> str:
    return f"rfq-import:{artifact_id}"
