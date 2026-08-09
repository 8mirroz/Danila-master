"""
Supplier model and seed data for the PartsOps AI Manager.
This module provides the Supplier SQLModel table and mock seed data 
for the MVP (Phase 1) testing cycle.
"""
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from sqlmodel import SQLModel, Field
import json


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    supplier_id: str = Field(index=True, unique=True)
    name: str
    contact_person: str = ""
    phone: str = ""
    email: str = ""
    city: str = ""
    specialization: str = ""  # e.g. "BMW,Audi", "Японские авто"
    reliability_score: float = Field(default=0.0)  # 0.0 – 1.0
    avg_delivery_days: int = Field(default=3)
    is_active: bool = Field(default=True)
    status: str = Field(default="active", index=True)
    rating_manual: Optional[float] = Field(default=None)
    rating_auto: float = Field(default=0.0)
    account_owner: str = ""
    payment_terms: str = ""
    delivery_terms: str = ""
    currency_default: str = "RUB"
    notes_internal: str = ""
    last_feed_at: Optional[datetime] = None
    last_sync_status: str = "synced"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SupplierTable(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    table_id: str = Field(index=True, unique=True)
    supplier_id: str = Field(index=True)
    name: str
    source_type: str = "excel"
    filename: str = ""
    version: int = 1
    status: str = Field(default="active", index=True)
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    uploaded_by: str = "seed"
    row_count: int = 0
    mapped_columns_json: str = "{}"
    validation_summary_json: str = "{}"
    is_active: bool = Field(default=True, index=True)


class SupplierTableRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    table_id: str = Field(index=True)
    supplier_id: str = Field(index=True)
    row_key: str = Field(index=True)
    part_name: str
    oem_number: str = ""
    brand: str = ""
    price: float = 0.0
    currency: str = "RUB"
    stock_qty: int = 0
    delivery_days: int = 0
    category: str = ""
    raw_payload_json: str = "{}"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SupplierActivityLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    event_id: str = Field(index=True, unique=True)
    supplier_id: str = Field(index=True)
    table_id: Optional[str] = Field(default=None, index=True)
    event_type: str = Field(index=True)
    actor_id: str = "system"
    payload_json: str = "{}"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class SupplierCatalogItem(SQLModel, table=True):
    """Individual part that a supplier offers."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    catalog_id: str = Field(index=True, unique=True)
    supplier_id: str = Field(index=True)
    part_name: str
    oem_number: str = Field(default="", index=True)  # OEM part number (indexed for matcher prefilter)
    brand: str = Field(default="", index=True)
    price: float = 0.0
    currency: str = "RUB"
    stock_qty: int = 0
    delivery_days: int = 0
    category: str = ""  # brake, filter, engine, body, etc.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Invoice(SQLModel, table=True):
    """Mock ERP Invoice generated from a validated request."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    invoice_number: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    supplier_id: str = ""
    customer_name: str = ""
    items_json: str = "[]"  # JSON list of line items
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    status: str = Field(default="DRAFT")  # DRAFT -> SENT -> PAID -> CLOSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ──────────────────────────────────────────────
# Seed data
# ──────────────────────────────────────────────

SEED_SUPPLIERS = [
    Supplier(
        supplier_id="sup_exist", name="Exist.ru (ООО «Экзист.ру»)",
        contact_person="Отдел продаж Exist API", phone="+7-495-777-0101",
        email="api@exist.ru", city="Москва",
        specialization="Exist API, OEM и Кроссы",
        reliability_score=0.95, avg_delivery_days=1,
        rating_auto=0.95, rating_manual=4.9, account_owner="Scraper System",
        payment_terms="B2B API / Prepaid", delivery_terms="Pick-up / Delivery",
        notes_internal="Авторизованный веб-скрапинг источник Exist.ru",
    ),
    Supplier(
        supplier_id="sup_autodoc", name="Autodoc.ru (ООО «Автодок»)",
        contact_person="Поддержка Autodoc B2B", phone="+7-495-988-7700",
        email="b2b@autodoc.ru", city="Москва",
        specialization="Autodoc API, Прямые дистрибьюторы",
        reliability_score=0.96, avg_delivery_days=2,
        rating_auto=0.96, rating_manual=4.8, account_owner="Scraper System",
        payment_terms="B2B API / Net 14", delivery_terms="Standard Delivery",
        notes_internal="Авторизованный веб-скрапинг источник Autodoc.ru",
    ),
    Supplier(
        supplier_id="sup_rossko", name="Rossko.ru (ООО «Росско»)",
        contact_person="B2B Менеджер Росско", phone="+7-800-500-7788",
        email="info@rossko.ru", city="Санкт-Петербург",
        specialization="Rossko API, Официальные OES бренды",
        reliability_score=0.98, avg_delivery_days=1,
        rating_auto=0.98, rating_manual=5.0, account_owner="Scraper System",
        payment_terms="B2B API / Net 30", delivery_terms="Express Delivery",
        notes_internal="Авторизованный веб-скрапинг источник Rossko.ru",
    ),
    Supplier(
        supplier_id="SUP-001", name="ООО «АвтоАльянс»",
        contact_person="Иванов Алексей", phone="+7-495-123-4567",
        email="ivanov@autoalliance.ru", city="Москва",
        specialization="BMW,Audi,Mercedes",
        reliability_score=0.92, avg_delivery_days=2,
        rating_auto=0.92, rating_manual=4.8, account_owner="Ops North",
        payment_terms="Net 14", delivery_terms="EXW Moscow", notes_internal="Стабильный премиум-поставщик",
    ),
    Supplier(
        supplier_id="SUP-002", name="ООО «ЕвроПарт»",
        contact_person="Петрова Мария", phone="+7-812-987-6543",
        email="petrova@europart.ru", city="Санкт-Петербург",
        specialization="BMW,Volkswagen,Skoda",
        reliability_score=0.87, avg_delivery_days=3,
        rating_auto=0.87, rating_manual=4.4, account_owner="Ops West",
        payment_terms="Net 21", delivery_terms="FCA SPB",
    ),
    Supplier(
        supplier_id="SUP-003", name="ИП Смирнов (JapanAuto)",
        contact_person="Смирнов Дмитрий", phone="+7-383-555-0101",
        email="smirnov@japanauto.ru", city="Новосибирск",
        specialization="Toyota,Honda,Nissan",
        reliability_score=0.78, avg_delivery_days=5,
        status="pending", rating_auto=0.78, rating_manual=3.9, account_owner="Ops East",
        payment_terms="Prepaid", delivery_terms="DAP NSK", last_sync_status="stale",
    ),
    Supplier(
        supplier_id="SUP-004", name="ООО «ТехСнаб»",
        contact_person="Козлов Сергей", phone="+7-343-222-3344",
        email="kozlov@techsnab.ru", city="Екатеринбург",
        specialization="Универсальные,Масла,Фильтры",
        reliability_score=0.95, avg_delivery_days=1,
        rating_auto=0.95, rating_manual=4.9, account_owner="Ops Core",
        payment_terms="Net 7", delivery_terms="Pickup",
    ),
    Supplier(
        supplier_id="SUP-005", name="ООО «МоторХаус»",
        contact_person="Никитин Павел", phone="+7-861-777-8899",
        email="nikitin@motorhouse.ru", city="Краснодар",
        specialization="BMW,Mercedes,Porsche",
        reliability_score=0.83, avg_delivery_days=4,
        status="active", rating_auto=0.83, rating_manual=4.2, account_owner="Ops South",
        payment_terms="Net 10", delivery_terms="CPT Krasnodar",
    ),
]

SEED_CATALOG = [
    # ─── sup_exist: Exist.ru ────
    SupplierCatalogItem(catalog_id="CAT-015", supplier_id="sup_exist",
        part_name="Комплект передних тормозных колодок BMW X5",
        oem_number="34116852253", brand="ATE", price=6200,
        stock_qty=15, delivery_days=1, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-016", supplier_id="sup_exist",
        part_name="Масляный фильтр ДВС BMW N55",
        oem_number="11427953129", brand="Bosch", price=890,
        stock_qty=25, delivery_days=1, category="filter"),
    SupplierCatalogItem(catalog_id="CAT-017", supplier_id="sup_exist",
        part_name="Воздушный фильтр ДВС MANN",
        oem_number="W6103", brand="MANN-FILTER", price=1850,
        stock_qty=30, delivery_days=1, category="filter"),

    # ─── sup_autodoc: Autodoc.ru ────
    SupplierCatalogItem(catalog_id="CAT-018", supplier_id="sup_autodoc",
        part_name="Комплект передних тормозных колодок BMW X5",
        oem_number="34116852253", brand="Brembo", price=5950,
        stock_qty=18, delivery_days=2, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-019", supplier_id="sup_autodoc",
        part_name="Воздушный фильтр ДВС VAG",
        oem_number="04E115561H", brand="VAG OE", price=1390,
        stock_qty=30, delivery_days=2, category="filter"),
    SupplierCatalogItem(catalog_id="CAT-020", supplier_id="sup_autodoc",
        part_name="Масляный фильтр KNECHT/MAHLE",
        oem_number="OC90", brand="KNECHT/MAHLE", price=1180,
        stock_qty=50, delivery_days=2, category="filter"),

    # ─── sup_rossko: Rossko.ru ────
    SupplierCatalogItem(catalog_id="CAT-021", supplier_id="sup_rossko",
        part_name="Комплект передних тормозных колодок BMW X5",
        oem_number="34116852253", brand="TRW", price=6100,
        stock_qty=22, delivery_days=1, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-022", supplier_id="sup_rossko",
        part_name="Масляный фильтр KNECHT/MAHLE",
        oem_number="OC90", brand="KNECHT/MAHLE", price=1220,
        stock_qty=40, delivery_days=1, category="filter"),
    SupplierCatalogItem(catalog_id="CAT-023", supplier_id="sup_rossko",
        part_name="Свеча зажигания иридиевая VAG",
        oem_number="04E115561H", brand="VAG OE", price=1420,
        stock_qty=35, delivery_days=1, category="engine"),

    # ─── SUP-001: АвтоАльянс ────
    SupplierCatalogItem(catalog_id="CAT-001", supplier_id="SUP-001",
        part_name="Тормозные колодки передние BMW X5 (E70)",
        oem_number="34116852253", brand="TRW", price=4500,
        stock_qty=12, delivery_days=1, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-002", supplier_id="SUP-001",
        part_name="Тормозные колодки задние BMW X5 (E70)",
        oem_number="34216776937", brand="TRW", price=3800,
        stock_qty=8, delivery_days=1, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-003", supplier_id="SUP-001",
        part_name="Тормозной диск передний BMW X5",
        oem_number="34116778647", brand="Brembo", price=8900,
        stock_qty=4, delivery_days=2, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-004", supplier_id="SUP-001",
        part_name="Свечи зажигания BMW N55",
        oem_number="12120037607", brand="NGK", price=950,
        stock_qty=50, delivery_days=1, category="engine"),

    # ─── SUP-002: ЕвроПарт ────
    SupplierCatalogItem(catalog_id="CAT-005", supplier_id="SUP-002",
        part_name="Тормозные колодки передние BMW X5",
        oem_number="34116852253", brand="Ate", price=3900,
        stock_qty=20, delivery_days=2, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-006", supplier_id="SUP-002",
        part_name="Масляный фильтр BMW N55/N57",
        oem_number="11427953129", brand="Mann", price=1100,
        stock_qty=30, delivery_days=1, category="filter"),
    SupplierCatalogItem(catalog_id="CAT-007", supplier_id="SUP-002",
        part_name="Воздушный фильтр BMW X5 (F15)",
        oem_number="13717638566", brand="Mann", price=2200,
        stock_qty=15, delivery_days=2, category="filter"),

    # ─── SUP-003: JapanAuto ────
    SupplierCatalogItem(catalog_id="CAT-008", supplier_id="SUP-003",
        part_name="Тормозные колодки передние Toyota Camry",
        oem_number="04465-33471", brand="Akebono", price=3200,
        stock_qty=10, delivery_days=4, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-009", supplier_id="SUP-003",
        part_name="Масляный фильтр Toyota 1.8L/2.0L",
        oem_number="90915-YZZD4", brand="Toyota OE", price=650,
        stock_qty=40, delivery_days=3, category="filter"),

    # ─── SUP-004: ТехСнаб ────
    SupplierCatalogItem(catalog_id="CAT-010", supplier_id="SUP-004",
        part_name="Масло моторное 5W-30 (5л)",
        oem_number="", brand="Castrol Edge", price=4800,
        stock_qty=100, delivery_days=1, category="oil"),
    SupplierCatalogItem(catalog_id="CAT-011", supplier_id="SUP-004",
        part_name="Масляный фильтр универсальный BMW",
        oem_number="11427953129", brand="Bosch", price=890,
        stock_qty=60, delivery_days=1, category="filter"),
    SupplierCatalogItem(catalog_id="CAT-012", supplier_id="SUP-004",
        part_name="Воздушный фильтр салона BMW X5",
        oem_number="64119272642", brand="Bosch", price=1500,
        stock_qty=25, delivery_days=1, category="filter"),

    # ─── SUP-005: МоторХаус ────
    SupplierCatalogItem(catalog_id="CAT-013", supplier_id="SUP-005",
        part_name="Тормозные колодки передние BMW X5 (F15)",
        oem_number="34116852253", brand="Brembo", price=5200,
        stock_qty=6, delivery_days=3, category="brake"),
    SupplierCatalogItem(catalog_id="CAT-014", supplier_id="SUP-005",
        part_name="Амортизатор передний BMW X5",
        oem_number="31316851745", brand="Bilstein", price=12500,
        stock_qty=3, delivery_days=5, category="suspension"),
]


def seed_database(session) -> dict:
    """Insert seed suppliers, catalog items, price history, and reliability logs. Returns counts."""
    from sqlmodel import select
    from models import PriceHistoryLedger, SupplierReliabilityLog
    from datetime import timedelta

    added_suppliers = 0
    added_catalog = 0
    added_tables = 0
    added_rows = 0

    for sup in SEED_SUPPLIERS:
        existing = session.exec(
            select(Supplier).where(Supplier.supplier_id == sup.supplier_id)
        ).first()
        if not existing:
            session.add(Supplier(**sup.model_dump(exclude={"id"})))
            added_suppliers += 1
            
            # Initial reliability log entry
            session.add(SupplierReliabilityLog(
                supplier_id=sup.supplier_id,
                reliability_score=sup.reliability_score,
                event_type="initial",
                reason="Initial seed reliability score"
            ))

    for item in SEED_CATALOG:
        existing = session.exec(
            select(SupplierCatalogItem).where(SupplierCatalogItem.catalog_id == item.catalog_id)
        ).first()
        if not existing:
            session.add(SupplierCatalogItem(**item.model_dump(exclude={"id"})))
            added_catalog += 1
            
            # Seed 3 historical price points (T-60d, T-30d, T-0d)
            session.add(PriceHistoryLedger(
                catalog_id=item.catalog_id,
                price=round(item.price * 0.95, 2),
                recorded_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=60)
            ))
            session.add(PriceHistoryLedger(
                catalog_id=item.catalog_id,
                price=round(item.price * 0.98, 2),
                recorded_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
            ))
            session.add(PriceHistoryLedger(
                catalog_id=item.catalog_id,
                price=item.price,
                recorded_at=datetime.now(timezone.utc).replace(tzinfo=None)
            ))

    table_cache: dict[str, SupplierTable] = {}
    suppliers = session.exec(select(Supplier)).all()
    for sup in suppliers:
        table_id = f"TBL-{sup.supplier_id}"
        existing_table = session.exec(
            select(SupplierTable).where(SupplierTable.table_id == table_id)
        ).first()
        if not existing_table:
            supplier_items = session.exec(
                select(SupplierCatalogItem).where(SupplierCatalogItem.supplier_id == sup.supplier_id)
            ).all()
            existing_table = SupplierTable(
                table_id=table_id,
                supplier_id=sup.supplier_id,
                name=f"Основной прайс {sup.name}",
                filename=f"{sup.supplier_id.lower()}-catalog.xlsx",
                source_type="excel",
                version=1,
                status="active",
                uploaded_by="seed",
                row_count=len(supplier_items),
                mapped_columns_json=json.dumps({
                    "part_name": "part_name",
                    "oem_number": "oem_number",
                    "brand": "brand",
                    "price": "price",
                    "stock_qty": "stock_qty",
                    "delivery_days": "delivery_days",
                }, ensure_ascii=False),
                validation_summary_json=json.dumps({
                    "valid_rows": len(supplier_items),
                    "warnings": [] if sup.status == "active" else ["stale_feed"],
                }, ensure_ascii=False),
            )
            session.add(existing_table)
            added_tables += 1
        table_cache[sup.supplier_id] = existing_table

    session.flush()

    for item in session.exec(select(SupplierCatalogItem)).all():
        table = table_cache.get(item.supplier_id)
        if not table:
            continue
        row_key = f"{table.table_id}:{item.catalog_id}"
        existing_row = session.exec(
            select(SupplierTableRow).where(SupplierTableRow.row_key == row_key)
        ).first()
        if not existing_row:
            session.add(SupplierTableRow(
                table_id=table.table_id,
                supplier_id=item.supplier_id,
                row_key=row_key,
                part_name=item.part_name,
                oem_number=item.oem_number,
                brand=item.brand,
                price=item.price,
                currency=item.currency,
                stock_qty=item.stock_qty,
                delivery_days=item.delivery_days,
                category=item.category,
                raw_payload_json=json.dumps(item.model_dump(exclude={"id"}), ensure_ascii=False, default=str),
            ))
            added_rows += 1

    for sup in suppliers:
        existing_activity = session.exec(
            select(SupplierActivityLog).where(
                SupplierActivityLog.supplier_id == sup.supplier_id,
                SupplierActivityLog.event_type == "supplier_seeded",
            )
        ).first()
        if not existing_activity:
            session.add(SupplierActivityLog(
                event_id=f"SUPLOG-{sup.supplier_id}-SEEDED",
                supplier_id=sup.supplier_id,
                event_type="supplier_seeded",
                actor_id="system",
                payload_json=json.dumps({
                    "status": sup.status,
                    "rating_auto": sup.rating_auto,
                    "last_sync_status": sup.last_sync_status,
                }, ensure_ascii=False),
            ))

    # Seed an initial ERPSyncLog entry if none exists
    from models import ERPSyncLog
    existing_sync = session.exec(select(ERPSyncLog)).first()
    if not existing_sync:
        session.add(ERPSyncLog(
            tenant_id="default",
            sync_id="seed-sync-1",
            request_id="CON-3640A024E2",
            erp_document_type="SalesInvoice",
            idempotency_key="seed-idem-1",
            status="SUCCESS",
            attempt_count=1,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            last_attempt_at=datetime.now(timezone.utc).replace(tzinfo=None),
            succeeded_at=datetime.now(timezone.utc).replace(tzinfo=None)
        ))

    # Optional default email inbox (dev/staging). Enable with SEED_EMAIL_INBOX=1.
    import os
    if os.environ.get("SEED_EMAIL_INBOX", "").strip().lower() in {"1", "true", "yes"}:
        try:
            from services.email_ingest import get_inbox_config, upsert_inbox_config

            if not get_inbox_config(session, "default"):
                upsert_inbox_config(
                    session,
                    tenant_id="default",
                    org_slug="default",
                    address=os.environ.get(
                        "SEED_EMAIL_INBOX_ADDRESS",
                        "rfq+default@inbound.local",
                    ),
                    provider="mailgun",
                    auto_ingest=False,
                )
        except Exception:
            # Email tables may be absent before migration — never block seed.
            pass

    session.commit()
    return {
        "added_suppliers": added_suppliers,
        "added_catalog": added_catalog,
        "added_tables": added_tables,
        "added_rows": added_rows,
    }
