"""
Fuzzy matching engine for part name lookups.
Uses RapidFuzz against SupplierCatalogItem rows in the database,
falling back to the in-memory MOCK_INVENTORY if no DB items exist.
"""
from rapidfuzz import process, fuzz
from typing import List, Dict, Optional
from sqlmodel import Session, select


import re
import math
from collections import Counter

def clean_string(s: str) -> str:
    """Remove all non-alphanumeric characters and lowercase."""
    return re.sub(r"[^a-zA-Z0-9а-яА-Я]", "", s).lower()

def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    previous_row = range(len(b) + 1)
    for i, c1 in enumerate(a):
        current_row = [i + 1]
        for j, c2 in enumerate(b):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def jaro_winkler(s1: str, s2: str) -> float:
    from rapidfuzz.distance import JaroWinkler
    return JaroWinkler.normalized_similarity(s1, s2)

def cosine_sim(a: str, b: str) -> float:
    tokens_a = [t for t in a.lower().split() if len(t) > 2]
    tokens_b = [t for t in b.lower().split() if len(t) > 2]
    vocab = set(tokens_a).union(set(tokens_b))
    vec_a = Counter(tokens_a)
    vec_b = Counter(tokens_b)
    dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in vocab)
    mag_a = math.sqrt(sum(v**2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v**2 for v in vec_b.values()))
    if mag_a and mag_b:
        return dot / (mag_a * mag_b)
    return 0.0


def match_part_from_db(
    query: str,
    session: Session,
    threshold: float = 55.0,
    limit: int = 5,
    vehicle_context: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> List[Dict]:
    """
    Match a query against SupplierCatalogItem rows in the database
    using the v3 6-component matching score formula.
    
    Args:
        vehicle_context: Optional vehicle make (e.g. "BMW", "Toyota") — 
                         when provided, boosts vehicle_compatibility_score
                         by matching against this keyword in addition to
                         whatever is already in the query text.
    """
    from suppliers import SupplierCatalogItem, Supplier

    catalog_query = select(SupplierCatalogItem)
    supplier_query = select(Supplier)
    if tenant_id is not None:
        catalog_query = catalog_query.where(SupplierCatalogItem.tenant_id == tenant_id)
        supplier_query = supplier_query.where(Supplier.tenant_id == tenant_id)

    catalog_items = session.exec(catalog_query).all()
    if not catalog_items:
        return []

    query_lower = query.lower()
    query_clean = clean_string(query)

    # Inject vehicle_context into query so vehicle_compatibility scoring picks it up
    # Also extract vehicle keywords directly from query text if no context provided
    if vehicle_context:
        vc_lower = vehicle_context.lower()
        if vc_lower not in query_lower:
            query_lower = query_lower + " " + vc_lower
    else:
        # Fallback: detect vehicle keywords already in the raw query
        # so that vehicle_compatibility scoring can use them
        pass  # query_lower already contains whatever the user typed

    # Keywords lists
    vehicle_keywords = ["x5", "camry", "bmw", "toyota", "audi", "mercedes", "urus", "lamborghini"]
    side_keywords = ["передн", "задн", "левы", "прав", "front", "rear", "left", "right"]
    synonym_map = {
        "колодк": ["pads", "pad", "brake"],
        "фильтр": ["filter", "mann", "bosch"],
        "свеч": ["spark", "ngk"],
        "диск": ["disc", "rotor", "brembo"],
        "амортизатор": ["shock", "absorber", "bilstein"],
        "масло": ["oil", "castrol"],
    }

    matches = []
    for item in catalog_items:
        supplier = session.exec(
            supplier_query.where(Supplier.supplier_id == item.supplier_id)
        ).first()
        reliability = supplier.reliability_score if supplier else 0.80

        # 6-Component scoring
        # 1. OEM Exact Score (30%)
        has_oem_in_query = len(re.sub(r"\D", "", query)) >= 5
        oem_score = 100.0
        if has_oem_in_query:
            if item.oem_number:
                item_oem_clean = clean_string(item.oem_number)
                if item_oem_clean and item_oem_clean in query_clean:
                    oem_score = 100.0
                else:
                    oem_score = 0.0
            else:
                oem_score = 0.0

        # 2. Brand/Article Score (20%)
        known_brands = ["trw", "ate", "ngk", "brembo", "bosch", "mann", "akebono", "toyota", "castrol", "bilstein"]
        has_brand_in_query = any(b in query_lower for b in known_brands)
        brand_score = 100.0
        if has_brand_in_query:
            if item.brand:
                brand_clean = clean_string(item.brand)
                if brand_clean and brand_clean in query_clean:
                    brand_score = 100.0
                else:
                    brand_score = float(fuzz.WRatio(item.brand, query))
            else:
                brand_score = 0.0

        # 3. Text/Name Score (Fuzzy Ensemble) (20%)
        a_clean = clean_string(query)
        b_clean = clean_string(item.part_name)
        lev = levenshtein(a_clean, b_clean)
        sim_lev = 1 - lev / max(len(a_clean) or 1, len(b_clean) or 1)
        sim_jw = jaro_winkler(a_clean, b_clean)
        sim_cos = cosine_sim(query, item.part_name)
        text_score = float((0.25 * sim_lev + 0.35 * sim_jw + 0.40 * sim_cos) * 100)

        # 4. Vehicle Compatibility Score (15%)
        item_name_lower = item.part_name.lower()
        mentioned_vehicles = [v for v in vehicle_keywords if v in query_lower]
        vehicle_score = 100.0
        if mentioned_vehicles:
            if not any(v in item_name_lower for v in mentioned_vehicles):
                vehicle_score = 0.0

        # 5. Side Position Score (10%)
        mentioned_sides = [s for s in side_keywords if s in query_lower]
        item_sides = [s for s in side_keywords if s in item_name_lower]
        position_score = 100.0
        if mentioned_sides:
            if not any(s in item_sides for s in mentioned_sides):
                position_score = 0.0

        # 6. Supplier/Data Score (5%)
        supplier_score = reliability * 100.0

        # Weighted calculation
        final_score = (
            0.30 * oem_score +
            0.20 * brand_score +
            0.20 * text_score +
            0.15 * vehicle_score +
            0.10 * position_score +
            0.05 * supplier_score
        )

        # Cross-brand hard filter
        if mentioned_vehicles and vehicle_score == 0.0:
            final_score -= 35.0

        if final_score >= threshold:
            matches.append({
                "item": {
                    "catalog_id": item.catalog_id,
                    "name": item.part_name,
                    "oem_number": item.oem_number,
                    "brand": item.brand,
                    "price": item.price,
                    "stock_qty": item.stock_qty,
                    "delivery_days": item.delivery_days,
                    "category": item.category,
                },
                "supplier": {
                    "supplier_id": item.supplier_id,
                    "name": supplier.name if supplier else "Неизвестный поставщик",
                    "reliability_score": reliability,
                },
                "score": round(final_score, 2),
                "breakdown": {
                    "oem_score": round(oem_score, 1),
                    "brand_score": round(brand_score, 1),
                    "text_score": round(text_score, 1),
                    "vehicle_score": round(vehicle_score, 1),
                    "position_score": round(position_score, 1),
                    "supplier_score": round(supplier_score, 1),
                }
            })

    # Sort matches by final_score descending
    matches.sort(key=lambda m: m["score"], reverse=True)
    
    # Calculate median price for matched items
    if matches:
        prices = sorted([m["item"]["price"] for m in matches])
        n = len(prices)
        if n % 2 == 1:
            median_price = prices[n // 2]
        else:
            median_price = (prices[n // 2 - 1] + prices[n // 2]) / 2.0
            
        for m in matches:
            price = m["item"]["price"]
            if median_price > 0:
                deviation = (price - median_price) / median_price
            else:
                deviation = 0.0
            m["price_deviation_from_median"] = round(deviation, 4)

    return matches[:3]  # Enforce top-3 candidates


# Backward-compatible wrapper for agents.py
def match_part(query: str, threshold: float = 55.0) -> List[Dict]:
    """
    Legacy wrapper – creates its own session. Prefer match_part_from_db
    when a session is already available.
    """
    from database import engine
    from sqlmodel import Session as SyncSession

    with SyncSession(engine) as session:
        results = match_part_from_db(query, session, threshold)
        if results:
            return results

    # Fallback: in-memory mock (for unit tests that don't seed the DB)
    MOCK_INVENTORY = [
        {"id": "1", "name": "Тормозные колодки передние BMW X5", "price": 4500, "supplier": "АвтоАльянс", "stock": 10},
        {"id": "2", "name": "Тормозные колодки задние BMW X5", "price": 3800, "supplier": "АвтоАльянс", "stock": 5},
        {"id": "3", "name": "Масляный фильтр BMW", "price": 1200, "supplier": "ООО «Поставщик»", "stock": 20},
        {"id": "4", "name": "Воздушный фильтр BMW X5", "price": 2500, "supplier": "ООО «Поставщик»", "stock": 15},
        {"id": "5", "name": "Свеча зажигания", "price": 800, "supplier": "АвтоАльянс", "stock": 100},
    ]
    inventory_names = [item["name"] for item in MOCK_INVENTORY]
    results = process.extract(query, inventory_names, scorer=fuzz.WRatio, limit=3)

    matches = []
    for match_str, score, index in results:
        if score >= threshold:
            item = MOCK_INVENTORY[index]
            matches.append({"item": item, "score": score})
    return matches
