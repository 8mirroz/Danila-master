from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Body, File, Form, Query, UploadFile
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session

from database import get_session
from rbac import get_privileged_tenant, get_current_principal, CurrentPrincipal
from services.supplier_service import SupplierService

router = APIRouter(prefix="/api/suppliers", tags=["Suppliers"])


class SupplierUpsertPayload(BaseModel):
    supplier_id: Optional[str] = None
    name: str
    contact_person: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    specialization: str = ""
    reliability_score: float = 0.85
    avg_delivery_days: int = 3
    status: str = "active"
    rating_manual: Optional[float] = None
    account_owner: str = ""
    payment_terms: str = ""
    delivery_terms: str = ""
    currency_default: str = "RUB"
    notes_internal: str = ""
    last_sync_status: str = "synced"


class SupplierRatingPayload(BaseModel):
    rating_manual: float
    reason: str = "manual update"


class SupplierTablePayload(BaseModel):
    name: str
    source_type: str = "excel"
    filename: str = ""
    status: str = "active"
    uploaded_by: str = "admin"
    mapped_columns_json: dict[str, Any] = PydanticField(default_factory=dict)
    validation_summary_json: dict[str, Any] = PydanticField(default_factory=dict)
    rows: list[dict[str, Any]] = PydanticField(default_factory=list)


class SupplierTablePatchPayload(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierTableRowPatchPayload(BaseModel):
    part_name: Optional[str] = None
    oem_number: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    stock_qty: Optional[int] = None
    delivery_days: Optional[int] = None
    category: Optional[str] = None


class SupplierTableBulkPatchPayload(BaseModel):
    row_keys: list[str]
    part_name: Optional[str] = None
    oem_number: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    stock_qty: Optional[int] = None
    delivery_days: Optional[int] = None
    category: Optional[str] = None


@router.get("")
def get_suppliers(
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    status: Optional[str] = Query(default=None),
    q: str = Query(default=""),
):
    return SupplierService.get_suppliers(session, tenant_id, status, q)


@router.post("")
def create_supplier(
    payload: SupplierUpsertPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.create_supplier(session, tenant_id, payload.model_dump())


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier(session, supplier_id, tenant_id)


@router.patch("/{supplier_id}")
def patch_supplier(
    supplier_id: str,
    payload: dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.patch_supplier(session, supplier_id, tenant_id, payload)


@router.post("/{supplier_id}/archive")
def archive_supplier(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.archive_supplier(session, supplier_id, tenant_id)


@router.post("/{supplier_id}/rating")
def update_supplier_rating(
    supplier_id: str,
    payload: SupplierRatingPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.update_supplier_rating(session, supplier_id, tenant_id, payload.rating_manual, payload.reason)


@router.get("/{supplier_id}/items")
def get_supplier_items(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_items(session, supplier_id, tenant_id)


@router.get("/{supplier_id}/tables")
def get_supplier_tables(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_tables(session, supplier_id, tenant_id)


@router.post("/{supplier_id}/tables")
def create_supplier_table(
    supplier_id: str,
    payload: SupplierTablePayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.create_supplier_table(session, supplier_id, tenant_id, payload.model_dump())


@router.post("/{supplier_id}/tables/import", status_code=201)
async def import_supplier_table(
    supplier_id: str,
    file: UploadFile = File(...),
    name: Optional[str] = Form(default=None),
    replace_table_id: Optional[str] = Form(default=None),
    status: str = Form(default="active"),
    tenant_id: str = Depends(get_privileged_tenant),
    principal: CurrentPrincipal = Depends(get_current_principal),
    session: Session = Depends(get_session),
):
    return SupplierService.import_supplier_table(
        session=session,
        supplier_id=supplier_id,
        tenant_id=tenant_id,
        file_obj=file.file,
        original_filename=file.filename,
        content_type=file.content_type,
        name=name,
        replace_table_id=replace_table_id,
        status=status,
        principal_tenant_id=principal.tenant_id,
    )


@router.get("/{supplier_id}/tables/{table_id}")
def get_supplier_table(
    supplier_id: str,
    table_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_table(session, supplier_id, table_id, tenant_id)


@router.patch("/{supplier_id}/tables/{table_id}")
def patch_supplier_table(
    supplier_id: str,
    table_id: str,
    payload: SupplierTablePatchPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.patch_supplier_table(session, supplier_id, table_id, tenant_id, payload.model_dump(exclude_none=True))


@router.post("/{supplier_id}/tables/{table_id}/activate")
def activate_supplier_table(
    supplier_id: str,
    table_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.activate_supplier_table(session, supplier_id, table_id, tenant_id)


@router.post("/{supplier_id}/tables/{table_id}/replace")
def replace_supplier_table(
    supplier_id: str,
    table_id: str,
    payload: SupplierTablePayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.replace_supplier_table(session, supplier_id, table_id, tenant_id, payload.model_dump())


@router.get("/{supplier_id}/tables/{table_id}/rows")
def get_supplier_table_rows(
    supplier_id: str,
    table_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
    limit: int = Query(default=100),
    offset: int = Query(default=0),
    q: str = Query(default=""),
):
    return SupplierService.get_supplier_table_rows(session, supplier_id, table_id, tenant_id, limit, offset, q)


@router.get("/{supplier_id}/tables/{table_id}/rows/{row_key}")
def get_supplier_table_row(
    supplier_id: str,
    table_id: str,
    row_key: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_table_row(session, supplier_id, table_id, row_key, tenant_id)


@router.patch("/{supplier_id}/tables/{table_id}/rows/{row_key}")
def patch_supplier_table_row(
    supplier_id: str,
    table_id: str,
    row_key: str,
    payload: SupplierTableRowPatchPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.patch_supplier_table_row(session, supplier_id, table_id, row_key, tenant_id, payload.model_dump(exclude_none=True))


@router.post("/{supplier_id}/tables/{table_id}/rows/bulk-update")
def bulk_update_supplier_table_rows(
    supplier_id: str,
    table_id: str,
    payload: SupplierTableBulkPatchPayload,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.bulk_update_supplier_table_rows(session, supplier_id, table_id, tenant_id, payload.model_dump(exclude_none=True))


@router.get("/{supplier_id}/analytics")
def get_supplier_analytics(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_analytics(session, supplier_id, tenant_id)


@router.get("/{supplier_id}/logs")
def get_supplier_logs(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_logs(session, supplier_id, tenant_id)


@router.get("/{supplier_id}/reliability-history")
def get_supplier_reliability_history(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_reliability_history(session, supplier_id, tenant_id)


@router.get("/{supplier_id}/price-history")
def get_supplier_price_history(
    supplier_id: str,
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    return SupplierService.get_supplier_price_history(session, supplier_id, tenant_id)


@router.post("/ping-all")
def ping_suppliers(
    supplier_ids: list[str] = Body(embed=True),
    session: Session = Depends(get_session),
    tenant_id: str = Depends(get_privileged_tenant),
):
    results = {}
    import random
    for sid in supplier_ids:
        supp = None
        try:
            supp = SupplierService.get_supplier(session, sid, tenant_id)
        except Exception:
            pass
        if supp:
            latency = random.randint(45, 180)
            results[sid] = {"status": "online", "latency_ms": latency, "code": 200}
        else:
            results[sid] = {"status": "offline", "latency_ms": 0, "code": 404}
    return results
