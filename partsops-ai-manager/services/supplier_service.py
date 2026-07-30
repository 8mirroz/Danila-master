from __future__ import annotations

import json
import os
import uuid
import csv
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select, delete, col

from database import engine
from models import PriceHistoryLedger, SupplierReliabilityLog, UploadArtifact
from app.automation.storage import storage
from suppliers import (
    Supplier,
    SupplierCatalogItem,
    SupplierTable,
    SupplierTableRow,
    SupplierActivityLog,
)

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _json_load(raw_value: Optional[str], default: Any) -> Any:
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return default

def _find_supplier_by_tenant(session: Session, supplier_id: str, tenant_id: str) -> Supplier | None:
    return session.exec(
        select(Supplier).where(
            Supplier.supplier_id == supplier_id,
            Supplier.tenant_id == tenant_id,
        )
    ).first()

def _get_supplier_categories(session: Session, supplier_id: str, tenant_id: str) -> list[str]:
    items = session.exec(
        select(SupplierCatalogItem).where(
            SupplierCatalogItem.supplier_id == supplier_id,
            SupplierCatalogItem.tenant_id == tenant_id,
        )
    ).all()
    categories = sorted({item.category for item in items if item.category})
    return categories

def _serialize_supplier(session: Session, supplier: Supplier) -> dict[str, Any]:
    categories = _get_supplier_categories(session, supplier.supplier_id, supplier.tenant_id)
    tables = session.exec(
        select(SupplierTable).where(
            SupplierTable.supplier_id == supplier.supplier_id,
            SupplierTable.tenant_id == supplier.tenant_id,
        )
    ).all()
    last_log = session.exec(
        select(SupplierActivityLog).where(
            SupplierActivityLog.supplier_id == supplier.supplier_id,
            SupplierActivityLog.tenant_id == supplier.tenant_id,
        ).order_by(col(SupplierActivityLog.created_at).desc())
    ).first()
    from services.live_scraper_service import SCRAPER_REGISTRY

    scraper_source = None
    search_url_template = None
    has_scraper_config = False

    for source_key, sc_info in SCRAPER_REGISTRY.items():
        if sc_info.get("supplier_id") == supplier.supplier_id or source_key in supplier.supplier_id:
            scraper_source = source_key
            search_url_template = sc_info.get("search_url_template")
            has_scraper_config = True
            break

    return {
        "supplier_id": supplier.supplier_id,
        "name": supplier.name,
        "contact_person": supplier.contact_person,
        "phone": supplier.phone,
        "email": supplier.email,
        "city": supplier.city,
        "specialization": supplier.specialization,
        "reliability_score": supplier.reliability_score,
        "avg_delivery_days": supplier.avg_delivery_days,
        "is_active": supplier.is_active,
        "status": supplier.status,
        "rating_manual": supplier.rating_manual,
        "rating_auto": supplier.rating_auto,
        "account_owner": supplier.account_owner,
        "payment_terms": supplier.payment_terms,
        "delivery_terms": supplier.delivery_terms,
        "currency_default": supplier.currency_default,
        "notes_internal": supplier.notes_internal,
        "last_feed_at": supplier.last_feed_at.isoformat() if supplier.last_feed_at else None,
        "last_sync_status": supplier.last_sync_status,
        "created_at": supplier.created_at.isoformat(),
        "categories": categories,
        "table_count": len(tables),
        "active_table_count": len([table for table in tables if table.is_active]),
        "last_activity_at": last_log.created_at.isoformat() if last_log else None,
        "scraper_source": scraper_source,
        "search_url_template": search_url_template,
        "has_scraper_config": has_scraper_config,
    }

def _serialize_table(table: SupplierTable) -> dict[str, Any]:
    return {
        "table_id": table.table_id,
        "supplier_id": table.supplier_id,
        "name": table.name,
        "source_type": table.source_type,
        "filename": table.filename,
        "version": table.version,
        "status": table.status,
        "uploaded_at": table.uploaded_at.isoformat(),
        "uploaded_by": table.uploaded_by,
        "row_count": table.row_count,
        "mapped_columns_json": _json_load(table.mapped_columns_json, {}),
        "validation_summary_json": _json_load(table.validation_summary_json, {}),
        "is_active": table.is_active,
    }

def _serialize_row(row: SupplierTableRow) -> dict[str, Any]:
    return {
        "row_key": row.row_key,
        "part_name": row.part_name,
        "oem_number": row.oem_number,
        "brand": row.brand,
        "price": row.price,
        "currency": row.currency,
        "stock_qty": row.stock_qty,
        "delivery_days": row.delivery_days,
        "category": row.category,
        "raw_payload_json": _json_load(row.raw_payload_json, {}),
    }

def _serialize_log(log: SupplierActivityLog) -> dict[str, Any]:
    return {
        "event_id": log.event_id,
        "supplier_id": log.supplier_id,
        "table_id": log.table_id,
        "event_type": log.event_type,
        "actor_id": log.actor_id,
        "payload": _json_load(log.payload_json, {}),
        "created_at": log.created_at.isoformat(),
    }

def _append_supplier_log(
    session: Session,
    supplier_id: str,
    tenant_id: str,
    event_type: str,
    actor_id: str = "system",
    table_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> SupplierActivityLog:
    log = SupplierActivityLog(
        tenant_id=tenant_id,
        event_id=f"SUPLOG-{uuid.uuid4().hex[:12].upper()}",
        supplier_id=supplier_id,
        table_id=table_id,
        event_type=event_type,
        actor_id=actor_id,
        payload_json=json.dumps(payload or {}, ensure_ascii=False, default=str),
        created_at=_utcnow(),
    )
    session.add(log)
    return log

def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()

def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        normalized = str(value).replace(" ", "").replace(",", ".")
        return float(normalized)
    except (TypeError, ValueError):
        return default

def _coerce_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        normalized = str(value).replace(" ", "").replace(",", ".")
        return int(float(normalized))
    except (TypeError, ValueError):
        return default

def _normalize_header(value: Any) -> str:
    return "".join(ch.lower() for ch in _coerce_text(value) if ch.isalnum())

def _parse_xlsx_rows(stored_path: str) -> list[dict[str, Any]]:
    import openpyxl
    from settings import settings
    max_rows = settings.MAX_PARSE_ROWS
    
    try:
        wb = openpyxl.load_workbook(stored_path, read_only=True, data_only=True)
    except Exception as e:
        raise ValueError(f"Failed to open Excel file: {e}")

    sheet = wb.active
    if not sheet:
        return []

    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return []

    if not header_row:
        return []

    headers = [_coerce_text(val) or f"column_{idx + 1}" for idx, val in enumerate(header_row)]
    
    parsed_rows: list[dict[str, Any]] = []
    for r in rows_iter:
        if not r or not any(_coerce_text(val) for val in r):
            continue
        row_dict = {}
        for idx, val in enumerate(headers):
            cell_val = r[idx] if idx < len(r) else None
            row_dict[val] = _coerce_text(cell_val)
        parsed_rows.append(row_dict)
        if len(parsed_rows) >= max_rows:
            break
    
    wb.close()
    return parsed_rows

def _decode_text_file(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")

def _parse_delimited_rows(stored_path: str, delimiter: Optional[str] = None) -> list[dict[str, Any]]:
    from settings import settings
    max_rows = settings.MAX_PARSE_ROWS
    
    raw_bytes = Path(stored_path).read_bytes()
    text = _decode_text_file(raw_bytes)
    sample = text[:2048]
    resolved_delimiter = delimiter
    if resolved_delimiter is None:
        try:
            resolved_delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            resolved_delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=resolved_delimiter)
    rows = []
    for row in reader:
        if any(_coerce_text(value) for value in row.values()):
            rows.append(dict(row))
            if len(rows) >= max_rows:
                break
    return rows

def _parse_json_rows(stored_path: str) -> list[dict[str, Any]]:
    from settings import settings
    max_rows = settings.MAX_PARSE_ROWS
    
    raw_payload = json.loads(_decode_text_file(Path(stored_path).read_bytes()))
    if isinstance(raw_payload, dict):
        raw_payload = raw_payload.get("rows", [])
    if not isinstance(raw_payload, list):
        raise ValueError("JSON import must contain a list of rows or an object with 'rows'")
    return [row for row in raw_payload if isinstance(row, dict)][:max_rows]

def _parse_supplier_table_file(stored_path: str, filename: str, content_type: Optional[str]) -> tuple[list[dict[str, Any]], str]:
    from settings import settings
    
    # Hard file-size guard at parser level (defense in depth beyond storage)
    try:
        file_size = os.path.getsize(stored_path)
    except OSError:
        file_size = 0
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise ValueError(f"UPLOAD_FILE_TOO_LARGE: {file_size} bytes exceeds limit {max_bytes} bytes")
    
    extension = Path(filename or stored_path).suffix.lower()
    if extension == ".json" or content_type == "application/json":
        return _parse_json_rows(stored_path), "json"
    if extension == ".xlsx" or content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return _parse_xlsx_rows(stored_path), "excel"
    if extension in {".txt", ".tsv"}:
        return _parse_delimited_rows(stored_path, delimiter="\t"), "text"
    return _parse_delimited_rows(stored_path), "csv"

def _extract_supplier_table_rows(raw_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    from settings import settings
    max_rows = settings.MAX_PARSE_ROWS
    if len(raw_rows) > max_rows:
        raise ValueError(f"UPLOAD_TOO_MANY_ROWS: {len(raw_rows)} rows exceeds limit {max_rows}")
    
    alias_map = {
        "part_name": ["partname", "name", "part", "detail", "description", "item", "название", "деталь", "позиция", "наименование"],
        "oem_number": ["oemnumber", "oem", "oemno", "articlenumber", "article", "sku", "номер", "артикул", "номердетали"],
        "brand": ["brand", "manufacturer", "make", "бренд", "производитель", "марка"],
        "price": ["price", "cost", "unitprice", "цена", "стоимость", "priceруб"],
        "currency": ["currency", "curr", "валюта"],
        "stock_qty": ["stockqty", "stock", "qty", "quantity", "availability", "остаток", "наличие", "количество"],
        "delivery_days": ["deliverydays", "delivery", "leadtime", "sla", "days", "срок", "доставка", "дней"],
        "category": ["category", "group", "family", "категория", "группа"],
    }
    normalized_aliases = {
        target: {_normalize_header(alias) for alias in aliases}
        for target, aliases in alias_map.items()
    }

    mapped_columns: dict[str, str] = {}
    normalized_rows: list[dict[str, Any]] = []
    skipped_rows = 0

    for index, row in enumerate(raw_rows, start=1):
        original_items = list(row.items())
        normalized_source = {_normalize_header(key): value for key, value in original_items if _normalize_header(key)}

        extracted: dict[str, Any] = {}
        for target, aliases in normalized_aliases.items():
            for source_key, source_value in normalized_source.items():
                if source_key in aliases:
                    extracted[target] = source_value
                    mapped_columns.setdefault(
                        target,
                        next((original_key for original_key, value in original_items if _normalize_header(original_key) == source_key), source_key),
                    )
                    break

        part_name = _coerce_text(extracted.get("part_name"))
        if not part_name:
            fallback = next((value for value in row.values() if _coerce_text(value)), "")
            part_name = _coerce_text(fallback)
        if not part_name:
            skipped_rows += 1
            continue

        normalized_rows.append(
            {
                "row_key": f"import:{index}",
                "part_name": part_name,
                "oem_number": _coerce_text(extracted.get("oem_number")),
                "brand": _coerce_text(extracted.get("brand")),
                "price": _coerce_float(extracted.get("price")),
                "currency": _coerce_text(extracted.get("currency")) or "RUB",
                "stock_qty": _coerce_int(extracted.get("stock_qty")),
                "delivery_days": _coerce_int(extracted.get("delivery_days")),
                "category": _coerce_text(extracted.get("category")),
                "raw_payload_json": row,
            }
        )

    warnings: list[str] = []
    if not normalized_rows:
        warnings.append("no_rows_imported")
    if skipped_rows:
        warnings.append(f"skipped_rows:{skipped_rows}")
    if "part_name" not in mapped_columns:
        warnings.append("part_name_inferred_from_first_non_empty_column")

    validation_summary = {
        "total_rows": len(raw_rows),
        "imported_rows": len(normalized_rows),
        "skipped_rows": skipped_rows,
        "warnings": warnings,
    }
    return normalized_rows, mapped_columns, validation_summary

def _create_supplier_table_entry(
    session: Session,
    supplier_id: str,
    tenant_id: str,
    *,
    name: str,
    source_type: str,
    filename: str,
    uploaded_by: str,
    rows: list[dict[str, Any]],
    mapped_columns_json: Optional[dict[str, Any]] = None,
    validation_summary_json: Optional[dict[str, Any]] = None,
    status: str = "active",
) -> SupplierTable:
    current_versions = session.exec(
        select(SupplierTable).where(
            SupplierTable.supplier_id == supplier_id,
            SupplierTable.tenant_id == tenant_id,
        )
    ).all()
    version = max([table.version for table in current_versions], default=0) + 1
    for existing in current_versions:
        existing.is_active = False
        session.add(existing)

    table = SupplierTable(
        tenant_id=tenant_id,
        table_id=f"TBL-{uuid.uuid4().hex[:8].upper()}",
        supplier_id=supplier_id,
        name=name,
        source_type=source_type,
        filename=filename,
        version=version,
        status=status,
        uploaded_at=_utcnow(),
        uploaded_by=uploaded_by,
        row_count=len(rows),
        mapped_columns_json=json.dumps(mapped_columns_json or {}, ensure_ascii=False),
        validation_summary_json=json.dumps(validation_summary_json or {}, ensure_ascii=False),
        is_active=True,
    )
    session.add(table)
    session.flush()

    for index, row in enumerate(rows, start=1):
        raw_payload = row.get("raw_payload_json", row)
        session.add(
            SupplierTableRow(
                tenant_id=tenant_id,
                table_id=table.table_id,
                supplier_id=supplier_id,
                row_key=row.get("row_key") or f"{table.table_id}:{index}",
                part_name=row.get("part_name") or row.get("name") or "Unknown part",
                oem_number=_coerce_text(row.get("oem_number")),
                brand=_coerce_text(row.get("brand")),
                price=_coerce_float(row.get("price")),
                currency=_coerce_text(row.get("currency")) or "RUB",
                stock_qty=_coerce_int(row.get("stock_qty")),
                delivery_days=_coerce_int(row.get("delivery_days")),
                category=_coerce_text(row.get("category")),
                raw_payload_json=json.dumps(raw_payload, ensure_ascii=False, default=str),
                created_at=_utcnow(),
            )
        )

    return table

def _find_supplier_table_row(
    session: Session,
    supplier_id: str,
    table_id: str,
    row_key: str,
    tenant_id: str,
) -> SupplierTableRow | None:
    return session.exec(
        select(SupplierTableRow).where(
            SupplierTableRow.table_id == table_id,
            SupplierTableRow.supplier_id == supplier_id,
            SupplierTableRow.row_key == row_key,
            SupplierTableRow.tenant_id == tenant_id,
        )
    ).first()

def _apply_row_patch(row: SupplierTableRow, payload_data: dict[str, Any]) -> dict[str, Any]:
    changed_fields: dict[str, Any] = {}
    for field in (
        "part_name",
        "oem_number",
        "brand",
        "price",
        "currency",
        "stock_qty",
        "delivery_days",
        "category",
    ):
        value = payload_data.get(field)
        if value is None:
            continue
        setattr(row, field, value)
        changed_fields[field] = value

    raw_payload = _json_load(row.raw_payload_json, {})
    if isinstance(raw_payload, dict):
        for key, value in changed_fields.items():
            raw_payload[key] = value
        row.raw_payload_json = json.dumps(raw_payload, ensure_ascii=False, default=str)
    return changed_fields


class SupplierService:
    @staticmethod
    def get_suppliers(session: Session, tenant_id: str, status: Optional[str] = None, q: str = "") -> list[dict[str, Any]]:
        statement = select(Supplier).where(Supplier.tenant_id == tenant_id)
        if status:
            statement = statement.where(Supplier.status == status)
        suppliers = session.exec(statement.order_by(col(Supplier.name).asc())).all()
        query_text = q.strip().lower()

        results = []
        for s in suppliers:
            serialized = _serialize_supplier(session, s)
            if query_text:
                matched = (
                    query_text in s.name.lower()
                    or query_text in s.specialization.lower()
                    or any(query_text in cat.lower() for cat in serialized.get("categories", []))
                )
                if not matched:
                    continue
            results.append(serialized)
        return results

    @staticmethod
    def create_supplier(session: Session, tenant_id: str, payload_data: dict[str, Any]) -> dict[str, Any]:
        supplier_id = payload_data.get("supplier_id") or f"SUP-{uuid.uuid4().hex[:8].upper()}"
        existing = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if existing:
            raise HTTPException(status_code=400, detail="Supplier with this ID already exists")

        new_supplier = Supplier(
            tenant_id=tenant_id,
            supplier_id=supplier_id,
            name=payload_data["name"],
            contact_person=payload_data.get("contact_person", ""),
            phone=payload_data.get("phone", ""),
            email=payload_data.get("email", ""),
            city=payload_data.get("city", ""),
            specialization=payload_data.get("specialization", ""),
            reliability_score=payload_data.get("reliability_score", 0.85),
            avg_delivery_days=payload_data.get("avg_delivery_days", 3),
            is_active=payload_data.get("status", "active") == "active",
            status=payload_data.get("status", "active"),
            rating_manual=payload_data.get("rating_manual"),
            rating_auto=0.0,
            account_owner=payload_data.get("account_owner", ""),
            payment_terms=payload_data.get("payment_terms", ""),
            delivery_terms=payload_data.get("delivery_terms", ""),
            currency_default=payload_data.get("currency_default", "RUB"),
            notes_internal=payload_data.get("notes_internal", ""),
            last_feed_at=None,
            last_sync_status=payload_data.get("last_sync_status", "synced"),
            created_at=_utcnow(),
        )
        session.add(new_supplier)
        _append_supplier_log(session, supplier_id, tenant_id, "supplier_created", payload={"name": new_supplier.name})
        session.commit()
        session.refresh(new_supplier)
        return _serialize_supplier(session, new_supplier)

    @staticmethod
    def get_supplier(session: Session, supplier_id: str, tenant_id: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return _serialize_supplier(session, s)

    @staticmethod
    def patch_supplier(session: Session, supplier_id: str, tenant_id: str, payload_data: dict[str, Any]) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")

        updates = {}
        for k, v in payload_data.items():
            if k == "status" and v is not None:
                s.status = v
                s.is_active = (v == "active")
                updates[k] = v
            elif k == "supplier_id":
                continue
            elif hasattr(s, k) and v is not None:
                setattr(s, k, v)
                updates[k] = v

        if updates:
            _append_supplier_log(session, supplier_id, tenant_id, "supplier_updated", payload={"updated_fields": updates})
            session.add(s)
            session.commit()
            session.refresh(s)
        return _serialize_supplier(session, s)

    @staticmethod
    def archive_supplier(session: Session, supplier_id: str, tenant_id: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        s.status = "archived"
        s.is_active = False
        _append_supplier_log(session, supplier_id, tenant_id, "supplier_archived")
        session.add(s)
        session.commit()
        return {"status": "success", "supplier_id": supplier_id}

    @staticmethod
    def update_supplier_rating(session: Session, supplier_id: str, tenant_id: str, rating_manual: float, reason: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        old_rating = s.rating_manual
        s.rating_manual = rating_manual
        _append_supplier_log(
            session,
            supplier_id,
            tenant_id,
            "rating_manually_updated",
            payload={"old_rating": old_rating, "new_rating": rating_manual, "reason": reason},
        )
        session.add(s)
        session.commit()
        return {"status": "success", "supplier_id": supplier_id, "rating_manual": rating_manual}

    @staticmethod
    def get_supplier_items(session: Session, supplier_id: str, tenant_id: str) -> list[dict[str, Any]]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        items = session.exec(
            select(SupplierCatalogItem).where(
                SupplierCatalogItem.supplier_id == supplier_id,
                SupplierCatalogItem.tenant_id == tenant_id,
            ).order_by(col(SupplierCatalogItem.part_name).asc())
        ).all()
        return [
            {
                "item_id": item.catalog_id,
                "part_name": item.part_name,
                "oem_number": item.oem_number,
                "brand": item.brand,
                "price": item.price,
                "currency": item.currency,
                "stock_qty": item.stock_qty,
                "delivery_days": item.delivery_days,
                "category": item.category,
            }
            for item in items
        ]

    @staticmethod
    def get_supplier_tables(session: Session, supplier_id: str, tenant_id: str) -> list[dict[str, Any]]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        tables = session.exec(
            select(SupplierTable).where(
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            ).order_by(col(SupplierTable.uploaded_at).desc())
        ).all()
        return [_serialize_table(t) for t in tables]

    @staticmethod
    def create_supplier_table(session: Session, supplier_id: str, tenant_id: str, payload_data: dict[str, Any]) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")

        table = _create_supplier_table_entry(
            session=session,
            supplier_id=supplier_id,
            tenant_id=tenant_id,
            name=payload_data["name"],
            source_type=payload_data.get("source_type", "excel"),
            filename=payload_data.get("filename", ""),
            uploaded_by=payload_data.get("uploaded_by", "admin"),
            rows=payload_data.get("rows", []),
            mapped_columns_json=payload_data.get("mapped_columns_json"),
            validation_summary_json=payload_data.get("validation_summary_json"),
            status=payload_data.get("status", "active"),
        )
        _append_supplier_log(
            session,
            supplier_id,
            tenant_id,
            "table_created_direct",
            table_id=table.table_id,
            payload={"row_count": table.row_count},
        )
        session.commit()
        session.refresh(table)
        return _serialize_table(table)

    @staticmethod
    def import_supplier_table(
        session: Session,
        supplier_id: str,
        tenant_id: str,
        file_obj: Any,
        original_filename: str,
        content_type: Optional[str],
        name: Optional[str] = None,
        replace_table_id: Optional[str] = None,
        status: str = "active",
        principal_tenant_id: str = "admin",
    ) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")

        original_table: SupplierTable | None = None
        if replace_table_id:
            original_table = session.exec(
                select(SupplierTable).where(
                    SupplierTable.table_id == replace_table_id,
                    SupplierTable.supplier_id == supplier_id,
                    SupplierTable.tenant_id == tenant_id,
                )
            ).first()
            if not original_table:
                raise HTTPException(status_code=404, detail="Table not found")

        artifact_id = f"art_{uuid.uuid4().hex[:12]}"
        stored_path: str | None = None
        try:
            stored_path, safe_filename, size_bytes = storage.save_file(
                tenant_id=tenant_id,
                artifact_id=artifact_id,
                file_obj=file_obj,
                original_filename=original_filename or f"{supplier_id}-table-upload.bin",
            )
            raw_rows, file_type = _parse_supplier_table_file(stored_path, original_filename or safe_filename, content_type)
            normalized_rows, mapped_columns, validation_summary = _extract_supplier_table_rows(raw_rows)

            if not normalized_rows:
                raise HTTPException(status_code=422, detail="Импорт не дал ни одной валидной строки")

            artifact = UploadArtifact(
                artifact_id=artifact_id,
                tenant_id=tenant_id,
                original_filename=original_filename or safe_filename,
                safe_filename=safe_filename,
                stored_path=stored_path,
                content_type=content_type,
                detected_mime=file_type,
                size_bytes=size_bytes,
                sha256=storage.calculate_sha256(stored_path),
                uploaded_by=principal_tenant_id,
                status="attached",
                metadata_json=json.dumps(
                    {
                        "supplier_id": supplier_id,
                        "replace_table_id": replace_table_id,
                        "imported_rows": len(normalized_rows),
                    },
                    ensure_ascii=False,
                ),
                created_at=_utcnow(),
            )
            session.add(artifact)

            table_name = (name or "").strip() or (original_table.name if original_table else Path(original_filename or safe_filename).stem or "Imported table")
            validation_summary["artifact_id"] = artifact_id
            if original_table:
                validation_summary["replaced_table_id"] = original_table.table_id

            table = _create_supplier_table_entry(
                session,
                supplier_id=supplier_id,
                tenant_id=tenant_id,
                name=table_name,
                source_type=file_type,
                filename=original_filename or safe_filename,
                uploaded_by=principal_tenant_id,
                rows=normalized_rows,
                mapped_columns_json=mapped_columns,
                validation_summary_json=validation_summary,
                status=status,
            )

            s.last_feed_at = _utcnow()
            s.last_sync_status = "synced"
            session.add(s)

            _append_supplier_log(
                session,
                supplier_id=supplier_id,
                tenant_id=tenant_id,
                event_type="supplier_table_imported" if not original_table else "supplier_table_reimported",
                actor_id=principal_tenant_id,
                table_id=table.table_id,
                payload={
                    "artifact_id": artifact_id,
                    "filename": original_filename,
                    "rows": len(normalized_rows),
                    "source_type": file_type,
                    "replace_table_id": replace_table_id,
                },
            )
            session.commit()
            session.refresh(table)
            return {
                "status": "success",
                "artifact_id": artifact_id,
                "table": _serialize_table(table),
                "import_summary": validation_summary,
            }
        except HTTPException:
            session.rollback()
            if stored_path:
                storage.delete_file(stored_path)
            raise
        except Exception as exc:
            session.rollback()
            if stored_path:
                storage.delete_file(stored_path)
            raise HTTPException(status_code=500, detail=f"Supplier table import failed: {exc}") from exc

    @staticmethod
    def get_supplier_table(session: Session, supplier_id: str, table_id: str, tenant_id: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        table = session.exec(
            select(SupplierTable).where(
                SupplierTable.table_id == table_id,
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).first()
        if not table:
            raise HTTPException(status_code=404, detail="Supplier table not found")
        return _serialize_table(table)

    @staticmethod
    def patch_supplier_table(
        session: Session,
        supplier_id: str,
        table_id: str,
        tenant_id: str,
        payload_data: dict[str, Any],
    ) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        table = session.exec(
            select(SupplierTable).where(
                SupplierTable.table_id == table_id,
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).first()
        if not table:
            raise HTTPException(status_code=404, detail="Supplier table not found")

        updates = {}
        for k, v in payload_data.items():
            if k == "is_active" and v is not None:
                table.is_active = v
                updates[k] = v
            elif k == "name" and v:
                table.name = v
                updates[k] = v
            elif k == "status" and v:
                table.status = v
                updates[k] = v

        if updates:
            _append_supplier_log(
                session,
                supplier_id,
                tenant_id,
                "table_updated",
                table_id=table_id,
                payload={"updated_fields": updates},
            )
            session.add(table)
            session.commit()
            session.refresh(table)
        return _serialize_table(table)

    @staticmethod
    def activate_supplier_table(session: Session, supplier_id: str, table_id: str, tenant_id: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        table = session.exec(
            select(SupplierTable).where(
                SupplierTable.table_id == table_id,
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).first()
        if not table:
            raise HTTPException(status_code=404, detail="Supplier table not found")

        all_tables = session.exec(
            select(SupplierTable).where(
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).all()
        for t in all_tables:
            t.is_active = (t.table_id == table_id)
            session.add(t)

        _append_supplier_log(session, supplier_id, tenant_id, "table_activated", table_id=table_id)
        session.commit()
        session.refresh(table)
        return _serialize_table(table)

    @staticmethod
    def replace_supplier_table(
        session: Session,
        supplier_id: str,
        table_id: str,
        tenant_id: str,
        payload_data: dict[str, Any]
    ) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        old_table = session.exec(
            select(SupplierTable).where(
                SupplierTable.table_id == table_id,
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).first()
        if not old_table:
            raise HTTPException(status_code=404, detail="Supplier table not found")

        new_table = _create_supplier_table_entry(
            session=session,
            supplier_id=supplier_id,
            tenant_id=tenant_id,
            name=payload_data.get("name") or "Replaced table",
            source_type=payload_data.get("source_type") or old_table.source_type,
            filename=payload_data.get("filename") or old_table.filename,
            uploaded_by=payload_data.get("uploaded_by") or "admin",
            rows=payload_data.get("rows") or [],
            mapped_columns_json=payload_data.get("mapped_columns_json"),
            validation_summary_json=payload_data.get("validation_summary_json"),
            status=payload_data.get("status") or "active",
        )

        session.exec(
            delete(SupplierCatalogItem).where(
                col(SupplierCatalogItem.supplier_id) == supplier_id,
                col(SupplierCatalogItem.tenant_id) == tenant_id,
            )
        )

        rows = session.exec(
            select(SupplierTableRow).where(
                SupplierTableRow.table_id == new_table.table_id,
                SupplierTableRow.tenant_id == tenant_id,
            )
        ).all()

        for index, row in enumerate(rows, start=1):
            new_item = SupplierCatalogItem(
                tenant_id=tenant_id,
                catalog_id=f"ITEM-{new_table.table_id[:6]}-{index}",
                supplier_id=supplier_id,
                part_name=row.part_name,
                oem_number=row.oem_number,
                brand=row.brand,
                price=row.price,
                currency=row.currency,
                stock_qty=row.stock_qty,
                delivery_days=row.delivery_days,
                category=row.category,
            )
            session.add(new_item)

            session.add(
                PriceHistoryLedger(
                    tenant_id=tenant_id,
                    catalog_id=new_item.catalog_id,
                    price=row.price,
                    currency=row.currency,
                    recorded_at=_utcnow(),
                )
            )

        _append_supplier_log(
            session,
            supplier_id,
            tenant_id,
            "catalog_replaced_from_table",
            table_id=new_table.table_id,
            payload={"items_added": len(rows), "previous_table_id": table_id},
        )
        session.commit()
        session.refresh(new_table)
        return _serialize_table(new_table)

    @staticmethod
    def get_supplier_table_rows(
        session: Session,
        supplier_id: str,
        table_id: str,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
        q: str = "",
    ) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        table = session.exec(
            select(SupplierTable).where(
                SupplierTable.table_id == table_id,
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).first()
        if not table:
            raise HTTPException(status_code=404, detail="Supplier table not found")

        statement = select(SupplierTableRow).where(
            SupplierTableRow.table_id == table_id,
            SupplierTableRow.tenant_id == tenant_id,
        )
        query_text = q.strip().lower()
        if query_text:
            statement = statement.where(
                col(SupplierTableRow.part_name).like(f"%{query_text}%")
                | col(SupplierTableRow.oem_number).like(f"%{query_text}%")
                | col(SupplierTableRow.brand).like(f"%{query_text}%")
            )
        # Fetch total count matching the statement before limit/offset
        from sqlmodel import func
        # Count using a query over statement
        total = len(session.exec(statement).all()) # simple for sqlite, or we can use select(func.count()).select_from(statement)
        
        rows = session.exec(statement.order_by(col(SupplierTableRow.row_key).asc()).limit(limit).offset(offset)).all()
        return {
            "total": total,
            "rows": [_serialize_row(row) for row in rows]
        }

    @staticmethod
    def get_supplier_table_row(session: Session, supplier_id: str, table_id: str, row_key: str, tenant_id: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        row = _find_supplier_table_row(session, supplier_id, table_id, row_key, tenant_id)
        if not row:
            raise HTTPException(status_code=404, detail="Supplier table row not found")
        return _serialize_row(row)

    @staticmethod
    def patch_supplier_table_row(
        session: Session,
        supplier_id: str,
        table_id: str,
        row_key: str,
        tenant_id: str,
        payload_data: dict[str, Any],
    ) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        row = _find_supplier_table_row(session, supplier_id, table_id, row_key, tenant_id)
        if not row:
            raise HTTPException(status_code=404, detail="Supplier table row not found")

        changed = _apply_row_patch(row, payload_data)
        if changed:
            _append_supplier_log(
                session,
                supplier_id,
                tenant_id,
                "row_updated",
                table_id=table_id,
                payload={"row_key": row_key, "changed_fields": changed},
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        return _serialize_row(row)

    @staticmethod
    def bulk_update_supplier_table_rows(
        session: Session,
        supplier_id: str,
        table_id: str,
        tenant_id: str,
        payload_data: dict[str, Any],
    ) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        table = session.exec(
            select(SupplierTable).where(
                SupplierTable.table_id == table_id,
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).first()
        if not table:
            raise HTTPException(status_code=404, detail="Supplier table not found")

        row_keys = payload_data.get("row_keys", [])
        if not row_keys:
            raise HTTPException(status_code=400, detail="row_keys list is empty")

        rows = session.exec(
            select(SupplierTableRow).where(
                SupplierTableRow.table_id == table_id,
                SupplierTableRow.row_key.in_(row_keys), # type: ignore
                SupplierTableRow.tenant_id == tenant_id,
            )
        ).all()

        updated_count = 0
        for row in rows:
            changed = _apply_row_patch(row, payload_data)
            if changed:
                session.add(row)
                updated_count += 1

        if updated_count > 0:
            _append_supplier_log(
                session,
                supplier_id,
                tenant_id,
                "rows_bulk_updated",
                table_id=table_id,
                payload={"row_keys_count": len(row_keys), "updated_count": updated_count},
            )
            session.commit()
        return {"status": "success", "updated_count": updated_count}

    @staticmethod
    def get_supplier_analytics(session: Session, supplier_id: str, tenant_id: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")

        items = session.exec(
            select(SupplierCatalogItem).where(
                SupplierCatalogItem.supplier_id == supplier_id,
                SupplierCatalogItem.tenant_id == tenant_id,
            )
        ).all()

        tables = session.exec(
            select(SupplierTable).where(
                SupplierTable.supplier_id == supplier_id,
                SupplierTable.tenant_id == tenant_id,
            )
        ).all()

        total_parts = len(items)
        avg_price = sum(item.price for item in items) / total_parts if total_parts else 0.0
        min_price = min((item.price for item in items), default=0.0)
        max_price = max((item.price for item in items), default=0.0)

        # Count in categories
        categories_count = {}
        for item in items:
            if item.category:
                categories_count[item.category] = categories_count.get(item.category, 0) + 1

        return {
            "supplier_id": supplier_id,
            "summary": {
                "table_count": len(tables),
                "active_table_count": len([t for t in tables if t.is_active]),
                "total_parts_in_catalog": total_parts,
                "avg_price": round(avg_price, 2),
                "min_price": min_price,
                "max_price": max_price,
            },
            "categories_distribution": categories_count,
        }

    @staticmethod
    def get_supplier_logs(session: Session, supplier_id: str, tenant_id: str) -> dict[str, Any]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        logs = session.exec(
            select(SupplierActivityLog).where(
                SupplierActivityLog.supplier_id == supplier_id,
                SupplierActivityLog.tenant_id == tenant_id,
            ).order_by(col(SupplierActivityLog.created_at).desc())
        ).all()
        serialized = [_serialize_log(l) for l in logs]
        return {
            "total": len(serialized),
            "logs": serialized
        }

    @staticmethod
    def get_supplier_reliability_history(session: Session, supplier_id: str, tenant_id: str) -> list[dict[str, Any]]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        logs = session.exec(
            select(SupplierReliabilityLog).where(
                col(SupplierReliabilityLog.supplier_id) == supplier_id,
                col(SupplierReliabilityLog.tenant_id) == tenant_id,
            ).order_by(col(SupplierReliabilityLog.logged_at).desc())
        ).all()
        return [
            {
                "log_id": f"rel_{log.id}",
                "reliability_score": log.reliability_score,
                "event_type": log.event_type,
                "reason": log.reason,
                "logged_at": log.logged_at.isoformat() if isinstance(log.logged_at, datetime) else str(log.logged_at),
            }
            for log in logs
        ]

    @staticmethod
    def get_supplier_price_history(session: Session, supplier_id: str, tenant_id: str) -> list[dict[str, Any]]:
        s = _find_supplier_by_tenant(session, supplier_id, tenant_id)
        if not s:
            raise HTTPException(status_code=404, detail="Supplier not found")
        catalog_item_ids = session.exec(
            select(SupplierCatalogItem.catalog_id).where(
                col(SupplierCatalogItem.supplier_id) == supplier_id,
                col(SupplierCatalogItem.tenant_id) == tenant_id,
            )
        ).all()
        if not catalog_item_ids:
            return []
        logs = session.exec(
            select(PriceHistoryLedger).where(
                col(PriceHistoryLedger.catalog_id).in_(catalog_item_ids),
                col(PriceHistoryLedger.tenant_id) == tenant_id,
            ).order_by(col(PriceHistoryLedger.recorded_at).desc())
        ).all()
        return [
            {
                "ledger_id": f"led_{log.id}",
                "catalog_id": log.catalog_id,
                "price": log.price,
                "currency": log.currency,
                "recorded_at": log.recorded_at.isoformat() if isinstance(log.recorded_at, datetime) else str(log.recorded_at),
            }
            for log in logs
        ]
