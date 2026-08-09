"""
Fuzzy matching engine for part name lookups.
Uses RapidFuzz against SupplierCatalogItem rows in the database.
Primary path: match_part_from_db. Legacy match_part returns [] when the DB
has no catalog items (no silent MOCK_INVENTORY in production). When TESTING=1,
match_part may use an in-memory MOCK_INVENTORY for isolated legacy experiments.

v4 improvements:
  - Keywords loaded from 01_CONFIGS/matcher_keywords.yaml (no hardcoded lists)
  - vehicle_context now accepts List[str] for multi-vehicle queries
  - synonym_map is used to boost Text Score via synonym expansion
  - load_keywords() function with caching for performance
"""
from rapidfuzz import process, fuzz
from typing import List, Dict, Optional, Sequence
from sqlmodel import Session, select

import re
import math
import os
from collections import Counter

# ---------------------------------------------------------------------------
# Keywords loader (cached)
# ---------------------------------------------------------------------------
_KEYWORDS_CACHE: Optional[dict] = None

def load_keywords(config_path: str = None) -> dict:
    """
    Load keyword lists from YAML config file.
    Falls back to hardcoded defaults if file not found or PyYAML not installed.
    Results are cached globally.
    """
    global _KEYWORDS_CACHE
    if _KEYWORDS_CACHE is not None:
        return _KEYWORDS_CACHE

    defaults = {
        "known_brands": ["trw", "ate", "ngk", "brembo", "bosch", "mann",
                         "akebono", "toyota", "castrol", "bilstein"],
        "vehicle_keywords": ["x5", "camry", "bmw", "toyota", "audi",
                             "mercedes", "urus", "lamborghini"],
        "side_keywords": ["передн", "задн", "левы", "прав",
                          "front", "rear", "left", "right"],
        "synonym_map": {
            "колодк": ["pads", "pad", "brake"],
            "фильтр": ["filter", "mann", "bosch"],
            "свеч": ["spark", "ngk"],
            "диск": ["disc", "rotor", "brembo"],
            "амортизатор": ["shock", "absorber", "bilstein"],
            "масло": ["oil", "castrol"],
        },
    }

    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), "01_CONFIGS", "matcher_keywords.yaml"
        )

    if not os.path.exists(config_path):
        _KEYWORDS_CACHE = defaults
        return _KEYWORDS_CACHE

    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        if loaded and isinstance(loaded, dict):
            # Merge – use loaded values where present, fall back to defaults
            result = dict(defaults)
            for key in ("known_brands", "vehicle_keywords", "side_keywords"):
                if key in loaded and isinstance(loaded[key], list):
                    result[key] = loaded[key]
            if "synonym_map" in loaded and isinstance(loaded["synonym_map"], dict):
                result["synonym_map"] = loaded["synonym_map"]
            _KEYWORDS_CACHE = result
            return _KEYWORDS_CACHE
    except Exception:
        pass  # fall through to defaults

    _KEYWORDS_CACHE = defaults
    return _KEYWORDS_CACHE


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def clean_string(s: str) -> str:
    """Remove all non-alphanumeric characters and lowercase."""
    return re.sub(r"[^a-zA-Z0-9а-яА-Я]", "", s).lower()


def normalize_oem(s: str) -> str:
    """Normalize OEM / article tokens for equality and index-friendly compare."""
    if not s:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


def extract_search_tokens(query: str) -> List[str]:
    """
    Extract tokens for soft ranking hints (not hard SQL filter alone).

    - alnum runs of length >= 5 (e.g. 34116852253)
    - digit-heavy OEM (digits >= 4)
    - brands len >= 3
    """
    if not query or not str(query).strip():
        return []
    raw = str(query)
    tokens: List[str] = []
    for m in re.finditer(r"[A-Za-z0-9А-Яа-я]{3,}", raw):
        tok = m.group(0)
        digits = sum(c.isdigit() for c in tok)
        if len(tok) >= 5 or digits >= 4 or (tok.isalpha() and len(tok) >= 3):
            tokens.append(tok)
    seen: set[str] = set()
    out: List[str] = []
    for t in tokens:
        key = t.upper()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out[:12]


def extract_strong_oem_tokens(query: str) -> List[str]:
    """
    Strong OEM tokens safe for hard SQL prefilter (digit-heavy / long alnum).

    Soft brand-only tokens are excluded so fuzzy name matching is not skipped.
    """
    strong: List[str] = []
    for tok in extract_search_tokens(query):
        digits = sum(c.isdigit() for c in tok)
        if digits >= 5 or (len(tok) >= 8 and digits >= 3) or (len(normalize_oem(tok)) >= 8):
            strong.append(tok)
    return strong


# Soft cap: never load unbounded catalogs into memory.
# Scoring remains fuzzy over this candidate pool.
MAX_CATALOG_CANDIDATES = int(os.environ.get("PARTSOPS_MATCHER_MAX_CANDIDATES", "2500"))
MIN_PREFILTER_CANDIDATES = int(os.environ.get("PARTSOPS_MATCHER_MIN_PREFILTER", "3"))


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


# ---------------------------------------------------------------------------
# Synonym-aware cosine similarity
# ---------------------------------------------------------------------------

def cosine_sim_with_synonyms(
    a: str, b: str, synonym_map: dict
) -> float:
    """
    Like cosine_sim, but expands Russian tokens in query 'a' with their
    English synonyms from synonym_map so that e.g. "колодки" matches "pads".
    """
    tokens_a_raw = [t for t in a.lower().split() if len(t) > 2]
    tokens_b = [t for t in b.lower().split() if len(t) > 2]

    # Expand tokens_a with synonyms
    tokens_a = list(tokens_a_raw)
    for tok in tokens_a_raw:
        # Check if any key in synonym_map is a substring of tok
        # (e.g. "колодк" in "колодки")
        for rus_key, eng_syns in synonym_map.items():
            if rus_key in tok:
                tokens_a.extend(eng_syns)

    vocab = set(tokens_a).union(set(tokens_b))
    vec_a = Counter(tokens_a)
    vec_b = Counter(tokens_b)
    dot = sum(vec_a.get(t, 0) * vec_b.get(t, 0) for t in vocab)
    mag_a = math.sqrt(sum(v**2 for v in vec_a.values()))
    mag_b = math.sqrt(sum(v**2 for v in vec_b.values()))
    if mag_a and mag_b:
        return dot / (mag_a * mag_b)
    return 0.0


# ---------------------------------------------------------------------------
# Main matching function
# ---------------------------------------------------------------------------

def match_part_from_db(
    query: str,
    session: Session,
    threshold: float = 55.0,
    limit: int = 5,
    vehicle_context: Optional[Sequence[str]] = None,
    tenant_id: Optional[str] = None,
) -> List[Dict]:
    """
    Match a query against SupplierCatalogItem rows in the database
    using the v4 6-component matching score formula with YAML keywords.

    Args:
        query: Search query (part name, OEM, brand, vehicle, etc.)
        session: Active DB session
        threshold: Minimum score to include in results (default 55.0)
        limit: Max results (default 5)
        vehicle_context: Optional list of vehicle makes (e.g. ["BMW", "Toyota"]).
                         Multiple values are joined into the query for scoring.
        tenant_id: Optional tenant filter
    """
    from suppliers import SupplierCatalogItem, Supplier
    from sqlalchemy import or_

    # Load keywords from config
    kw = load_keywords()
    vehicle_keywords: list = kw["vehicle_keywords"]
    side_keywords: list = kw["side_keywords"]
    synonym_map: dict = kw["synonym_map"]
    known_brands: list = kw["known_brands"]

    base_catalog = select(SupplierCatalogItem)
    supplier_query = select(Supplier)
    if tenant_id is not None:
        base_catalog = base_catalog.where(SupplierCatalogItem.tenant_id == tenant_id)
        supplier_query = supplier_query.where(Supplier.tenant_id == tenant_id)

    # Deterministic order before any LIMIT (stable across SQLite/Postgres).
    try:
        base_catalog = base_catalog.order_by(SupplierCatalogItem.catalog_id)  # type: ignore[arg-type]
    except Exception:
        pass

    # Hard SQL prefilter only for strong OEM tokens. Brand/name fuzzy needs broader pool.
    strong_oems = extract_strong_oem_tokens(query)
    catalog_items: list = []
    if strong_oems:
        clauses = []
        for tok in strong_oems:
            like = f"%{tok}%"
            clauses.append(SupplierCatalogItem.oem_number.ilike(like))  # type: ignore[attr-defined]
            norm = normalize_oem(tok)
            if norm and len(norm) >= 5:
                clauses.append(SupplierCatalogItem.oem_number.ilike(f"%{norm}%"))  # type: ignore[attr-defined]
        filtered = base_catalog.where(or_(*clauses)).limit(MAX_CATALOG_CANDIDATES)
        catalog_items = list(session.exec(filtered).all())

    # Fallback: empty / too-thin prefilter → tenant-scoped ordered pool (fuzzy path)
    if len(catalog_items) < MIN_PREFILTER_CANDIDATES:
        fallback = base_catalog.limit(MAX_CATALOG_CANDIDATES)
        catalog_items = list(session.exec(fallback).all())

    if not catalog_items:
        return []

    # Preload suppliers in one query to eliminate N+1
    supplier_ids = list({item.supplier_id for item in catalog_items if item.supplier_id})
    suppliers_by_id: dict[str, Supplier] = {}
    if supplier_ids:
        suppliers = session.exec(
            supplier_query.where(Supplier.supplier_id.in_(supplier_ids))  # type: ignore
        ).all()
        suppliers_by_id = {s.supplier_id: s for s in suppliers}

    query_lower = query.lower()
    query_clean = clean_string(query)

    # Inject vehicle_context(s) into query_lower for scoring
    if vehicle_context:
        for vc in vehicle_context:
            vc_lower = vc.lower().strip()
            if vc_lower and vc_lower not in query_lower:
                query_lower = query_lower + " " + vc_lower

    matches = []
    for item in catalog_items:
        supplier = suppliers_by_id.get(item.supplier_id)
        reliability = supplier.reliability_score if supplier else 0.80

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
        # Use synonym-aware cosine similarity instead of plain cosine
        sim_cos = cosine_sim_with_synonyms(query, item.part_name, synonym_map)
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

    # Apply limit
    return matches[:limit]


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

    # Production: empty catalog → no silent fake inventory
    if os.environ.get("TESTING") != "1":
        return []

    # TESTING-only: in-memory mock for legacy experiments without seeded DB
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
