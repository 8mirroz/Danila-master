"""Tests for matcher N+1 fix."""
import pytest
from unittest.mock import patch
from sqlmodel import Session, delete

from database import engine, init_db
from suppliers import SupplierCatalogItem, Supplier
from matcher import match_part_from_db


@pytest.fixture
def session():
    init_db()
    with Session(engine) as s:
        s.exec(delete(SupplierCatalogItem))
        s.exec(delete(Supplier))
        s.commit()

        sup = Supplier(supplier_id="sup1", name="Test Supplier", reliability_score=0.90)
        s.add(sup)

        item1 = SupplierCatalogItem(catalog_id="cat1", supplier_id="sup1", part_name="Тормозные колодки BMW X5", brand="ATE", price=1000.0)
        item2 = SupplierCatalogItem(catalog_id="cat2", supplier_id="sup1", part_name="Тормозные колодки Toyota Camry", brand="TRW", price=2000.0)
        item3 = SupplierCatalogItem(catalog_id="cat3", supplier_id="sup1", part_name="Тормозные колодки Audi Q7", brand="Brembo", price=1500.0)
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
