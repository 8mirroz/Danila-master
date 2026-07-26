import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from database import engine
from main import app
from pricing import compute_price, PricingContext, check_margin_guard, calculate_invoice
from matcher import match_part_from_db
from suppliers import seed_database

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    yield


def test_adversarial_malformed_payloads():
    """1. Отправка неверных типов и пустых запросов на API эндпоинты."""
    # Пустой JSON
    resp = client.post("/api/requests", json={}, headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-a"})
    # Должен возвращаться код 422 Unprocessable Entity
    assert resp.status_code == 422

    # Некорректные типы полей (например, строка вместо dict в pricing_evidence)
    payload = {
        "source": "ADVERSARIAL_QA",
        "text": "Тормозные колодки",
        "pricing_evidence_json": "not-a-json-string-but-raw-text"
    }
    resp = client.post("/api/requests", json=payload, headers={"Authorization": "Bearer test-token", "X-Tenant-ID": "tenant-a"})
    # Схема валидации должна отсекать или принимать как строку, проверим что API устойчив
    assert resp.status_code in (200, 422)


def test_adversarial_boundary_pricing():
    """2. Граничные значения и аномалии в расчетах цен."""
    # Отрицательная цена покупки
    ctx = PricingContext(purchase_price=-100.0)
    result = compute_price(ctx)
    assert result.client_price < 0 or len(result.violations) > 0

    # Нулевая цена покупки
    guard_res = check_margin_guard(purchase_price=0.0, sale_price=100.0)
    assert guard_res["passed"] is False
    assert "закупочная цена должна быть > 0" in guard_res["violation"]

    # Отрицательное количество товаров в инвойсе
    items = [{"price": 100.0, "qty": -5, "weight_kg": 2.0}]
    invoice = calculate_invoice(items)
    # Итог должен быть отрицательным, но математика не должна бросать ZeroDivisionError
    assert invoice["subtotal"] == -500.0


def test_adversarial_tenant_isolation_leak():
    """3. Попытка несанкционированного доступа без токена к чужому тенанту."""
    # Запрос с кастомным тенантом без Bearer токена
    resp = client.get("/api/requests", headers={"X-Tenant-ID": "private-tenant"})
    # Если PARTSOPS_API_TOKEN задан (а он задан как test-token в pytest),
    # неавторизованный запрос возвращает 401 при обращении к приватным эндпоинтам.
    # Так как /api/requests требует авторизации:
    assert resp.status_code == 401


def test_adversarial_matching_determinism():
    """4. Проверка детерминированности алгоритма сопоставления при многократном запуске."""
    with Session(engine) as session:
        first_run = match_part_from_db("Тормозные диски BMW", session, tenant_id="default")
        for i in range(10):
            next_run = match_part_from_db("Тормозные диски BMW", session, tenant_id="default")
            assert len(first_run) == len(next_run)
            if first_run and next_run:
                assert first_run[0]["item"]["catalog_id"] == next_run[0]["item"]["catalog_id"]
                assert first_run[0]["score"] == next_run[0]["score"]
