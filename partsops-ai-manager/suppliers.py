"""
Supplier model and seed data for the PartsOps AI Manager.
This module provides the Supplier SQLModel table and mock seed data 
for the MVP (Phase 1) testing cycle.
"""
from typing import Optional, List
from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SupplierCatalogItem(SQLModel, table=True):
    """Individual part that a supplier offers."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    catalog_id: str = Field(index=True, unique=True)
    supplier_id: str = Field(index=True)
    part_name: str
    oem_number: str = ""  # OEM part number
    brand: str = ""
    price: float = 0.0
    currency: str = "RUB"
    stock_qty: int = 0
    delivery_days: int = 0
    category: str = ""  # brake, filter, engine, body, etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Seed data
# ──────────────────────────────────────────────

SEED_SUPPLIERS = [
    Supplier(
        supplier_id="SUP-001", name="ООО «АвтоАльянс»",
        contact_person="Иванов Алексей", phone="+7-495-123-4567",
        email="ivanov@autoalliance.ru", city="Москва",
        specialization="BMW,Audi,Mercedes",
        reliability_score=0.92, avg_delivery_days=2,
    ),
    Supplier(
        supplier_id="SUP-002", name="ООО «ЕвроПарт»",
        contact_person="Петрова Мария", phone="+7-812-987-6543",
        email="petrova@europart.ru", city="Санкт-Петербург",
        specialization="BMW,Volkswagen,Skoda",
        reliability_score=0.87, avg_delivery_days=3,
    ),
    Supplier(
        supplier_id="SUP-003", name="ИП Смирнов (JapanAuto)",
        contact_person="Смирнов Дмитрий", phone="+7-383-555-0101",
        email="smirnov@japanauto.ru", city="Новосибирск",
        specialization="Toyota,Honda,Nissan",
        reliability_score=0.78, avg_delivery_days=5,
    ),
    Supplier(
        supplier_id="SUP-004", name="ООО «ТехСнаб»",
        contact_person="Козлов Сергей", phone="+7-343-222-3344",
        email="kozlov@techsnab.ru", city="Екатеринбург",
        specialization="Универсальные,Масла,Фильтры",
        reliability_score=0.95, avg_delivery_days=1,
    ),
    Supplier(
        supplier_id="SUP-005", name="ООО «МоторХаус»",
        contact_person="Никитин Павел", phone="+7-861-777-8899",
        email="nikitin@motorhouse.ru", city="Краснодар",
        specialization="BMW,Mercedes,Porsche",
        reliability_score=0.83, avg_delivery_days=4,
    ),
]

SEED_CATALOG = [
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
                recorded_at=datetime.utcnow() - timedelta(days=60)
            ))
            session.add(PriceHistoryLedger(
                catalog_id=item.catalog_id,
                price=round(item.price * 0.98, 2),
                recorded_at=datetime.utcnow() - timedelta(days=30)
            ))
            session.add(PriceHistoryLedger(
                catalog_id=item.catalog_id,
                price=item.price,
                recorded_at=datetime.utcnow()
            ))

    session.commit()
    return {"added_suppliers": added_suppliers, "added_catalog": added_catalog}
