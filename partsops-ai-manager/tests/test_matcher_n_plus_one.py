"""Tests for matcher N+1 fix and SQL prefilter scale path."""
import pytest
from unittest.mock import patch
from sqlmodel import Session, delete

from database import engine, init_db
from suppliers import SupplierCatalogItem, Supplier
from matcher import extract_search_tokens, match_part_from_db, normalize_oem


@pytest.fixture
def session():
    init_db()
    with Session(engine) as s:
        s.exec(delete(SupplierCatalogItem))
        s.exec(delete(Supplier))
        s.commit()

        sup = Supplier(supplier_id="sup1", name="Test Supplier", reliability_score=0.90)
        s.add(sup)

        item1 = SupplierCatalogItem(
            catalog_id="cat1",
            supplier_id="sup1",
            part_name="Тормозные колодки BMW X5",
            brand="ATE",
            oem_number="34116852253",
            price=1000.0,
        )
        item2 = SupplierCatalogItem(
            catalog_id="cat2",
            supplier_id="sup1",
            part_name="Тормозные колодки Toyota Camry",
            brand="TRW",
            oem_number="04465-33471",
            price=2000.0,
        )
        item3 = SupplierCatalogItem(
            catalog_id="cat3",
            supplier_id="sup1",
            part_name="Тормозные колодки Audi Q7",
            brand="Brembo",
            oem_number="8E0698151",
            price=1500.0,
        )
        # Noise rows that must not force full-table scoring when OEM is present
        for i in range(40):
            s.add(
                SupplierCatalogItem(
                    catalog_id=f"noise-{i}",
                    supplier_id="sup1",
                    part_name=f"Случайная позиция {i}",
                    brand="Other",
                    oem_number=f"NOISE{i:05d}",
                    price=100.0 + i,
                )
            )
        s.add_all([item1, item2, item3])
        s.commit()
        yield s


def test_matcher_does_not_trigger_n_plus_one(session):
    query_count = 0
    original_exec = session.exec

    def counting_exec(stmt):
        nonlocal query_count
        query_count += 1
        return original_exec(stmt)

    with patch.object(session, "exec", side_effect=counting_exec):
        match_part_from_db("Тормозные колодки BMW X5", session, threshold=50.0, limit=3)

    assert query_count <= 2, f"Expected <= 2 queries, got {query_count}"


def test_normalize_and_extract_tokens():
    assert normalize_oem("34116-852-253") == "34116852253"
    tokens = extract_search_tokens("колодки 34116852253 BOSCH")
    assert "34116852253" in tokens
    assert any(t.upper() == "BOSCH" for t in tokens)


def test_oem_query_prefers_exact_catalog_row(session):
    results = match_part_from_db("34116852253", session, threshold=40.0, limit=5)
    assert results
    assert results[0]["item"]["oem_number"] == "34116852253"
    # Prefilter should not return only noise rows when OEM is specific
    oems = {r["item"]["oem_number"] for r in results}
    assert "34116852253" in oems


def test_russian_name_query_uses_fallback_pool(session):
    """Without strong OEM tokens, matcher must still find name matches (fallback path)."""
    from matcher import extract_strong_oem_tokens

    assert extract_strong_oem_tokens("Тормозные колодки BMW X5") == []
    results = match_part_from_db("Тормозные колодки BMW X5", session, threshold=40.0, limit=5)
    assert results
    names = " ".join(r["item"]["name"] for r in results).lower()
    assert "колодк" in names or "bmw" in names
