"""
Tests for 6-component matcher.py.
"""
import pytest
from sqlmodel import Session
from database import engine, init_db
from suppliers import SupplierCatalogItem, Supplier
from matcher import match_part_from_db

@pytest.fixture
def session():
    init_db()
    with Session(engine) as s:
        # Clear out tables for isolated tests
        s.query(SupplierCatalogItem).delete()
        s.query(Supplier).delete()
        s.commit()
        
        # Insert test supplier
        sup = Supplier(supplier_id="sup1", name="Test Supplier", reliability_score=0.90)
        s.add(sup)
        
        # Insert catalog items with varying prices
        item1 = SupplierCatalogItem(catalog_id="cat1", supplier_id="sup1", part_name="Тормозные колодки BMW X5", brand="ATE", price=1000.0)
        item2 = SupplierCatalogItem(catalog_id="cat2", supplier_id="sup1", part_name="Тормозные колодки Toyota Camry", brand="TRW", price=2000.0)
        item3 = SupplierCatalogItem(catalog_id="cat3", supplier_id="sup1", part_name="Тормозные колодки Audi Q7", brand="Brembo", price=1500.0)
        item4 = SupplierCatalogItem(catalog_id="cat4", supplier_id="sup1", part_name="Тормозные колодки Lada", brand="Brembo", price=1800.0)
        
        # Another exact match for oem
        item5 = SupplierCatalogItem(catalog_id="cat5", supplier_id="sup1", part_name="Оригинальные колодки BMW", brand="BMW", oem_number="34116852253", price=5000.0)
        
        s.add_all([item1, item2, item3, item4, item5])
        s.commit()
        yield s

def test_matcher_top_3_and_median_deviation(session):
    # Query hits "Тормозные колодки" -> returns 4 items natively, but should be limited to top 3
    query = "Тормозные колодки"
    results = match_part_from_db(query, session, threshold=10.0, limit=5) # limit is overridden to top 3 at the end of matcher
    
    assert len(results) <= 3
    
    # Check median logic
    for res in results:
        assert "price_deviation_from_median" in res

def test_oem_match(session):
    # OEM exact match should boost score heavily
    query = "Колодки 34116852253"
    results = match_part_from_db(query, session, threshold=10.0)
    
    assert len(results) > 0
    top_match = results[0]
    assert top_match["item"]["oem_number"] == "34116852253"
    assert top_match["breakdown"]["oem_score"] == 100.0

def test_cross_brand_penalty(session):
    # Search for BMW, but one item is Toyota Camry. Camry should get penalized if BMW is specified.
    query = "Тормозные колодки BMW"
    results = match_part_from_db(query, session, threshold=10.0)
    
    for res in results:
        # Toyota should be heavily penalized or not make it to top 3
        if "Toyota" in res["item"]["name"]:
            assert res["breakdown"]["vehicle_score"] == 0.0
            assert res["score"] < 50.0  # Because of the -35.0 penalty
