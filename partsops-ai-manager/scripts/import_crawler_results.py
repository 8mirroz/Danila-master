"""
Import results from my-crawler/results/aggregated_parts.json into SupplierCatalogItem.

This script bridges the crawler (external marketplace data) with the internal
catalog so that matcher.py can search against newly scraped parts.

Usage:
    python -m scripts.import_crawler_results [--source path/to/aggregated_parts.json]
                                            [--supplier-id SUP-xxx]
                                            [--tenant-id default]
                                            [--dry-run]

If --supplier-id is not provided, the script will create a new supplier
"Crawler Import" (SUP-CRAWLER) for the imported items.

The script deduplicates by OEM number + brand + part_name to avoid duplicates
on repeated runs.
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

# Add parent dir to path so we can import from the project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import engine, init_db
from sqlmodel import Session, select
from suppliers import Supplier, SupplierCatalogItem, SupplierTable, SupplierTableRow
from matcher import clean_string


def parse_args():
    parser = argparse.ArgumentParser(description="Import crawler results into SupplierCatalogItem")
    parser.add_argument(
        "--source",
        default=None,
        help="Path to aggregated_parts.json (default: ../my-crawler/results/aggregated_parts.json)",
    )
    parser.add_argument(
        "--supplier-id",
        default=None,
        help="Supplier ID to assign items to (default: create/use SUP-CRAWLER)",
    )
    parser.add_argument(
        "--tenant-id",
        default="default",
        help="Tenant ID (default: default)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without actually inserting",
    )
    return parser.parse_args()


def resolve_source_path(provided: str | None) -> str:
    if provided:
        path = provided
    else:
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "my-crawler", "results", "aggregated_parts.json"
        )
    path = os.path.abspath(path)
    if not os.path.exists(path):
        # Try alternative: relative to project root
        alt = os.path.join(os.getcwd(), "my-crawler", "results", "aggregated_parts.json")
        if os.path.exists(alt):
            path = alt
        else:
            print(f"Error: source file not found at {path}")
            print(f"Also checked: {alt}")
            sys.exit(1)
    return path


def load_json(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # Some Crawlee exports wrap data in {"items": [...]}
        data = data.get("items", data)
    if not isinstance(data, list):
        print(f"Error: expected a JSON array, got {type(data).__name__}")
        sys.exit(1)
    return data


def ensure_supplier(session: Session, supplier_id: str | None, tenant_id: str) -> Supplier:
    """Get existing supplier or create a new 'Crawler Import' supplier."""
    if supplier_id:
        existing = session.exec(
            select(Supplier).where(
                Supplier.supplier_id == supplier_id,
                Supplier.tenant_id == tenant_id,
            )
        ).first()
        if existing:
            return existing
        print(f"Warning: supplier {supplier_id} not found, creating SUP-CRAWLER instead.")
        supplier_id = None

    # Find or create SUP-CRAWLER
    crawler_sup_id = "SUP-CRAWLER"
    existing = session.exec(
        select(Supplier).where(
            Supplier.supplier_id == crawler_sup_id,
            Supplier.tenant_id == tenant_id,
        )
    ).first()
    if existing:
        return existing

    if not session.in_transaction():
        print("Dry-run: would create supplier SUP-CRAWLER")
        # Return a fake supplier for counting purposes
        return Supplier(
            supplier_id=crawler_sup_id,
            name="Crawler Import",
            tenant_id=tenant_id,
            reliability_score=0.70,
            specialization="Импорт из краулера (exist, autodoc, rossko)",
            is_active=True,
            status="active",
        )

    sup = Supplier(
        supplier_id=crawler_sup_id,
        name="Crawler Import",
        tenant_id=tenant_id,
        reliability_score=0.70,
        specialization="Импорт из краулера (exist, autodoc, rossko)",
        is_active=True,
        status="active",
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    session.add(sup)
    session.flush()
    print(f"Created supplier: {crawler_sup_id} (Crawler Import)")
    return sup


def make_catalog_id(row: dict) -> str:
    """Generate a deterministic catalog_id based on site + article + brand."""
    site = row.get("site", "unknown")
    article = row.get("article", "").strip()
    brand = row.get("brand", "Unknown").strip()
    raw = f"{site}-{article}-{brand}"
    # Short hash to keep IDs readable
    short = str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))[:8].upper()
    return f"CRL-{short}"


def item_exists(session: Session, catalog_id: str) -> bool:
    return session.exec(
        select(SupplierCatalogItem).where(SupplierCatalogItem.catalog_id == catalog_id)
    ).first() is not None


def parse_price(price_str: str) -> float:
    """Parse a price string like "4500 ₽" or "1 200.50" into float."""
    if not price_str or price_str == "——":
        return 0.0
    cleaned = price_str.replace("₽", "").replace(" ", "").replace("\xa0", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_stock(row: dict) -> int:
    """Heuristic: try to extract stock from delivery/stock info."""
    delivery = (row.get("delivery", "") + " " + row.get("stock", "")).lower()
    digits = [int(s) for s in delivery.replace("–", "-").split() if s.isdigit()]
    return digits[0] if digits else 1


def parse_delivery_days(row: dict) -> int:
    """Heuristic: try to extract delivery days from delivery string."""
    delivery = row.get("delivery", "").lower()
    # patterns like "1-2 дня", "3-5 days", "~Завтра"
    match = __import__("re").findall(r"(\d+)", delivery)
    if match:
        return int(match[0])
    if "завтра" in delivery or "tomorrow" in delivery:
        return 1
    return 3


def categorize_part(description: str) -> str:
    """Simple keyword-based categorization."""
    desc = description.lower()
    if any(w in desc for w in ["тормоз", "brake", "колодк", "диск"]):
        return "brake"
    if any(w in desc for w in ["фильтр", "filter"]):
        if "маслян" in desc or "oil" in desc:
            return "oil_filter"
        if "воздуш" in desc or "air" in desc:
            return "air_filter"
        if "салон" in desc or "cabin" in desc or "салона" in desc:
            return "cabin_filter"
        return "filter"
    if any(w in desc for w in ["масло", "oil", "castrol"]):
        return "oil"
    if any(w in desc for w in ["свеч", "spark", "ngk"]):
        return "ignition"
    if any(w in desc for w in ["амортизатор", "shock", "absorber", "bilstein"]):
        return "suspension"
    if any(w in desc for w in ["ремень", "belt"]):
        return "belt"
    if any(w in desc for w in ["цеп", "chain"]):
        return "chain"
    if any(w in desc for w in ["стартер", "starter"]):
        return "starter"
    if any(w in desc for w in ["генератор", "alternator"]):
        return "alternator"
    if any(w in desc for w in ["датчик", "sensor", "лямбда", "lambda"]):
        return "sensor"
    if any(w in desc for w in ["лампа", "lamp", "bulb", "light"]):
        return "lighting"
    if any(w in desc for w in ["стекло", "glass", "зеркало", "mirror"]):
        return "body"
    if any(w in desc for w in ["дворник", "wiper"]):
        return "wiper"
    if any(w in desc for w in ["аккумулятор", "battery"]):
        return "battery"
    if any(w in desc for w in ["антифриз", "antifreeze", "coolant"]):
        return "coolant"
    return "general"


def main():
    args = parse_args()
    source_path = resolve_source_path(args.source)
    print(f"Loading data from: {source_path}")
    rows = load_json(source_path)
    print(f"Loaded {len(rows)} raw records from crawler")

    # Deduplicate: group by (site, article, brand), keep the first entry per group
    seen_keys = set()
    unique_rows = []
    for r in rows:
        key = (r.get("site", ""), r.get("article", ""), r.get("brand", ""))
        if key not in seen_keys:
            seen_keys.add(key)
            unique_rows.append(r)
    print(f"After dedup by (site, article, brand): {len(unique_rows)} unique records")

    init_db()
    stats = {"created": 0, "skipped": 0, "errors": 0}

    with Session(engine) as session:
        supplier = ensure_supplier(session, args.supplier_id, args.tenant_id)
        if not args.dry_run and not session.in_transaction():
            print("Error: supplier creation failed and no transaction active")
            sys.exit(1)

        for row in unique_rows:
            try:
                catalog_id = make_catalog_id(row)

                # Skip if already exists
                if not args.dry_run and item_exists(session, catalog_id):
                    stats["skipped"] += 1
                    continue

                part_name = row.get("description", "") or row.get("article", "")
                oem_number = row.get("article", "")
                brand = row.get("brand", "Unknown")
                price = parse_price(row.get("price", "0"))
                delivery_str = row.get("delivery", "")
                stock_qty = parse_stock(row)
                delivery_days = parse_delivery_days(row)
                category = categorize_part(part_name + " " + brand)

                if not part_name.strip():
                    part_name = f"Запчасть {oem_number}"

                if args.dry_run:
                    print(f"  Would import: [{catalog_id}] {brand} {oem_number} — "
                          f"{part_name[:50]} — {price}₽ — stock:{stock_qty}")
                    stats["created"] += 1
                    continue

                item = SupplierCatalogItem(
                    catalog_id=catalog_id,
                    supplier_id=supplier.supplier_id,
                    tenant_id=args.tenant_id,
                    part_name=part_name.strip(),
                    oem_number=oem_number,
                    brand=brand,
                    price=price,
                    currency="RUB",
                    stock_qty=stock_qty,
                    delivery_days=delivery_days,
                    category=category,
                )
                session.add(item)
                stats["created"] += 1

            except Exception as e:
                print(f"Error processing row: {row.get('article', '?')} — {e}")
                stats["errors"] += 1

        if not args.dry_run:
            session.commit()
            print(f"\nSuccessfully imported {stats['created']} items into catalog "
                  f"(supplier: {supplier.supplier_id})")

    print(f"\nSummary: {stats['created']} created, {stats['skipped']} skipped, {stats['errors']} errors")
    if args.dry_run:
        print("(dry-run — no changes were made)")


if __name__ == "__main__":
    main()