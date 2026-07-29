"""
End-to-End Test Runner for PartsOps AI Manager.

This script:
1. Seeds supplier tables (5 suppliers, 14 catalog items)
2. Sends test requests through the LangGraph pipeline
3. Generates invoices for validated requests
4. Collects metrics and produces a JSON report
5. Identifies improvement areas and generates an update plan

Run: PYTHONPATH=. python tests/test_e2e_cycle.py
"""
import json
import time
import os
import sys
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, SQLModel, create_engine, select
from database import init_db, engine
from suppliers import Supplier, SupplierCatalogItem, Invoice, seed_database
from models import PartRequest
from agents import process_intake_request
from matcher import match_part_from_db

# ──────────────────────────────────────────────
# Test Scenarios
# ──────────────────────────────────────────────
TEST_SCENARIOS = [
    {
        "id": "TC-001",
        "name": "Стандартный запрос — тормозные колодки BMW X5",
        "text": "Нужны тормозные колодки на BMW X5 2018 года, передние",
        "customer": "Андрей Волков",
        "expected_status": "VALIDATED",
        "expected_match": True,
        "expected_category": "brake",
    },
    {
        "id": "TC-002",
        "name": "Составной запрос — колодки + фильтр",
        "text": "Необходимо: тормозные колодки передние и масляный фильтр на BMW X5",
        "customer": "Мария Иванова",
        "expected_status": "VALIDATED",
        "expected_match": True,
        "expected_category": "brake,filter",
    },
    {
        "id": "TC-003",
        "name": "Нераспознаваемый запрос — мусорный текст",
        "text": "привет как дела сколько стоит",
        "customer": "Спам Бот",
        "expected_status": "NEEDS_REVIEW",
        "expected_match": False,
        "expected_category": "",
    },
    {
        "id": "TC-004",
        "name": "Запрос только на фильтр",
        "text": "Нужен масляный фильтр для BMW",
        "customer": "Сергей Козлов",
        "expected_status": "VALIDATED",
        "expected_match": True,
        "expected_category": "filter",
    },
    {
        "id": "TC-005",
        "name": "Запрос на несуществующую деталь (вне каталога)",
        "text": "Нужен передний бампер на Lamborghini Urus",
        "customer": "Олег Мещеряков",
        "expected_status": "NEEDS_REVIEW",
        "expected_match": False,
        "expected_category": "",
    },
    {
        "id": "TC-006",
        "name": "Запрос на английском языке (brake pads)",
        "text": "I need brake pads for BMW X5 front",
        "customer": "John Smith",
        "expected_status": "VALIDATED",
        "expected_match": True,
        "expected_category": "brake",
    },
    {
        "id": "TC-007",
        "name": "Запрос с опечатками",
        "text": "тармозные калодки бмв х5 передние",
        "customer": "Дмитрий Смирнов",
        "expected_status": "VALIDATED",
        "expected_match": True,
        "expected_category": "brake",
    },
]


@dataclass
class TestResult:
    scenario_id: str
    scenario_name: str
    # Pipeline timings (ms)
    agent_time_ms: float = 0
    match_time_ms: float = 0
    invoice_time_ms: float = 0
    total_time_ms: float = 0
    # Outcomes
    actual_status: str = ""
    expected_status: str = ""
    status_correct: bool = False
    match_found: bool = False
    expected_match: bool = False
    match_correct: bool = False
    best_match_score: float = 0.0
    best_match_name: str = ""
    best_supplier: str = ""
    best_price: float = 0.0
    num_alternatives: int = 0
    # Invoice
    invoice_number: str = ""
    invoice_total: float = 0.0
    invoice_items: int = 0
    # Errors
    errors: List[str] = field(default_factory=list)


def run_single_test(scenario: dict, session: Session) -> TestResult:
    result = TestResult(
        scenario_id=scenario["id"],
        scenario_name=scenario["name"],
        expected_status=scenario["expected_status"],
        expected_match=scenario["expected_match"],
    )

    total_start = time.perf_counter()

    # 1. Agent processing
    t0 = time.perf_counter()
    agent_result = None
    try:
        agent_result = process_intake_request(scenario["text"])
        result.agent_time_ms = round((time.perf_counter() - t0) * 1000, 2)
        result.actual_status = "VALIDATED" if agent_result["validation_status"] == "PASSED" else "NEEDS_REVIEW"
    except Exception as e:
        result.errors.append(f"Agent error: {e}")
        result.agent_time_ms = round((time.perf_counter() - t0) * 1000, 2)
        result.actual_status = "ERROR"

    result.status_correct = result.actual_status == result.expected_status

    # 2. Matching (separate timing)
    extracted_parts = agent_result.get("extracted_parts", []) if agent_result is not None else []
    t1 = time.perf_counter()
    try:
        for part in extracted_parts:
            part_name = part.get("name", "")
            if part_name != "Неизвестная деталь":
                matches = match_part_from_db(part_name, session, threshold=50.0, limit=5)
                if matches:
                    result.match_found = True
                    if matches[0]["score"] > result.best_match_score:
                        result.best_match_score = matches[0]["score"]
                        result.best_match_name = matches[0]["item"]["name"]
                        result.best_supplier = matches[0]["supplier"]["name"]
                        result.best_price = matches[0]["item"]["price"]
                    result.num_alternatives = max(result.num_alternatives, len(matches))
        result.match_time_ms = round((time.perf_counter() - t1) * 1000, 2)
    except Exception as e:
        result.errors.append(f"Match error: {e}")
        result.match_time_ms = round((time.perf_counter() - t1) * 1000, 2)

    result.match_correct = result.match_found == result.expected_match

    # 3. Invoice generation (only for VALIDATED)
    if result.actual_status == "VALIDATED":
        import uuid
        request_id = f"REQ-{str(uuid.uuid4())[:8].upper()}"

        # Save request to DB first
        new_request = PartRequest(
            request_id=request_id,
            source="E2E_TEST",
            status=result.actual_status,
            customer_name=scenario["customer"],
            parts_json=json.dumps(extracted_parts, ensure_ascii=False, default=str),
        )
        session.add(new_request)
        session.commit()
        session.refresh(new_request)

        t2 = time.perf_counter()
        try:
            # Build invoice
            parts = extracted_parts
            line_items = []
            subtotal = 0.0
            for part in parts:
                pn = part.get("name", "")
                if pn == "Неизвестная деталь":
                    continue
                ms = match_part_from_db(pn, session, threshold=50.0, limit=1)
                if ms:
                    best = ms[0]
                    qty = int(part.get("quantity", 1))
                    price = best["item"]["price"]
                    line_total = price * qty
                    line_items.append({
                        "part_name": best["item"]["name"],
                        "oem_number": best["item"]["oem_number"],
                        "brand": best["item"]["brand"],
                        "supplier": best["supplier"]["name"],
                        "supplier_id": best["supplier"]["supplier_id"],
                        "unit_price": price,
                        "quantity": qty,
                        "line_total": line_total,
                        "match_score": best["score"],
                    })
                    subtotal += line_total

            tax = round(subtotal * 0.20, 2)
            total = round(subtotal + tax, 2)
            inv_num = f"INV-{str(uuid.uuid4())[:6].upper()}"

            invoice = Invoice(
                invoice_number=inv_num,
                request_id=request_id,
                supplier_id=line_items[0]["supplier_id"] if line_items else "",
                customer_name=scenario["customer"],
                items_json=json.dumps(line_items, ensure_ascii=False),
                subtotal=subtotal,
                tax=tax,
                total=total,
                status="DRAFT",
            )
            session.add(invoice)
            session.commit()

            result.invoice_number = inv_num
            result.invoice_total = total
            result.invoice_items = len(line_items)
            result.invoice_time_ms = round((time.perf_counter() - t2) * 1000, 2)
        except Exception as e:
            result.errors.append(f"Invoice error: {e}")
            result.invoice_time_ms = round((time.perf_counter() - t2) * 1000, 2)

    result.total_time_ms = round((time.perf_counter() - total_start) * 1000, 2)
    return result


def compute_metrics(results: List[TestResult]) -> dict:
    total = len(results)
    status_ok = sum(1 for r in results if r.status_correct)
    match_ok = sum(1 for r in results if r.match_correct)
    validated = [r for r in results if r.actual_status == "VALIDATED"]
    invoiced = [r for r in results if r.invoice_number]
    errors = sum(len(r.errors) for r in results)

    avg_agent_ms = round(sum(r.agent_time_ms for r in results) / total, 2) if total else 0
    avg_match_ms = round(sum(r.match_time_ms for r in results) / total, 2) if total else 0
    avg_total_ms = round(sum(r.total_time_ms for r in results) / total, 2) if total else 0

    avg_match_score = 0
    match_scores = [r.best_match_score for r in results if r.match_found]
    if match_scores:
        avg_match_score = round(sum(match_scores) / len(match_scores), 2)

    return {
        "total_scenarios": total,
        "status_accuracy": round(status_ok / total * 100, 1) if total else 0,
        "match_accuracy": round(match_ok / total * 100, 1) if total else 0,
        "validated_count": len(validated),
        "invoiced_count": len(invoiced),
        "error_count": errors,
        "avg_agent_time_ms": avg_agent_ms,
        "avg_match_time_ms": avg_match_ms,
        "avg_total_time_ms": avg_total_ms,
        "avg_match_score": avg_match_score,
        "total_invoice_value": round(sum(r.invoice_total for r in results), 2),
    }


def generate_improvement_plan(metrics: dict, results: List[TestResult]) -> List[dict]:
    """Analyze metrics and produce actionable improvement items."""
    plan = []

    # 1. Status accuracy
    if metrics["status_accuracy"] < 100:
        failed = [r for r in results if not r.status_correct]
        plan.append({
            "id": "IMP-001",
            "area": "Parser (parse_request_node)",
            "priority": "HIGH",
            "metric_before": f'{metrics["status_accuracy"]}%',
            "target": "100%",
            "description": "Классификатор заявок не совпадает с ожидаемым результатом.",
            "failed_cases": [f"{r.scenario_id}: expected={r.expected_status}, got={r.actual_status}" for r in failed],
            "action": "Расширить словарь ключевых слов в parse_request_node или подключить LLM для extraction.",
        })

    # 2. Match accuracy
    if metrics["match_accuracy"] < 100:
        failed = [r for r in results if not r.match_correct]
        plan.append({
            "id": "IMP-002",
            "area": "Matcher (match_part_from_db)",
            "priority": "HIGH",
            "metric_before": f'{metrics["match_accuracy"]}%',
            "target": "100%",
            "description": "Нечеткий поиск не корректно сопоставляет заявки с каталогом.",
            "failed_cases": [f"{r.scenario_id}: expected_match={r.expected_match}, got={r.match_found}" for r in failed],
            "action": "Снизить порог RapidFuzz или добавить алиасы/синонимы для деталей.",
        })

    # 3. Performance
    if metrics["avg_total_time_ms"] > 100:
        plan.append({
            "id": "IMP-003",
            "area": "Performance",
            "priority": "MEDIUM",
            "metric_before": f'{metrics["avg_total_time_ms"]}ms',
            "target": "<100ms",
            "description": "Среднее время обработки превышает целевой порог.",
            "action": "Кэшировать каталог в памяти, индексировать по категориям.",
        })

    # 4. Match score quality
    if metrics["avg_match_score"] < 80:
        plan.append({
            "id": "IMP-004",
            "area": "Match Quality",
            "priority": "MEDIUM",
            "metric_before": f'{metrics["avg_match_score"]}',
            "target": ">80",
            "description": "Средний скор нечеткого поиска ниже 80 — возможны неточные совпадения.",
            "action": "Добавить нормализацию запроса (удаление стоп-слов, лемматизация).",
        })

    # 5. Error count
    if metrics["error_count"] > 0:
        plan.append({
            "id": "IMP-005",
            "area": "Error Handling",
            "priority": "HIGH",
            "metric_before": str(metrics["error_count"]),
            "target": "0",
            "description": "Обнаружены ошибки при обработке тестовых сценариев.",
            "action": "Добавить try/except обработку и graceful degradation.",
        })

    return plan


def main():
    print("=" * 70)
    print("  PartsOps AI Manager — E2E Test Cycle")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 70)

    # Init DB
    init_db()
    with Session(engine) as session:
        seed_result = seed_database(session)
        print(f"\n[SEED] {seed_result}")

        # Verify seed
        suppliers = session.exec(select(Supplier)).all()
        catalog = session.exec(select(SupplierCatalogItem)).all()
        print(f"[DB] Поставщиков: {len(suppliers)}, Позиций каталога: {len(catalog)}")

        # Run tests
        print(f"\n{'─' * 70}")
        print(f"  Запуск {len(TEST_SCENARIOS)} тестовых сценариев")
        print(f"{'─' * 70}\n")

        results: List[TestResult] = []
        for scenario in TEST_SCENARIOS:
            print(f"  ▸ {scenario['id']}: {scenario['name']}")
            result = run_single_test(scenario, session)
            results.append(result)

            status_icon = "✅" if result.status_correct else "❌"
            match_icon = "✅" if result.match_correct else "❌"
            print(f"    Статус: {status_icon} {result.actual_status} (ожид: {result.expected_status})")
            print(f"    Матч:   {match_icon} score={result.best_match_score} → {result.best_match_name or '—'}")
            if result.invoice_number:
                print(f"    Счет:   {result.invoice_number} = {result.invoice_total}₽ ({result.invoice_items} поз.)")
            print(f"    Время:  {result.total_time_ms}ms (agent={result.agent_time_ms}, match={result.match_time_ms})")
            if result.errors:
                print(f"    ⚠️  Ошибки: {result.errors}")
            print()

        # Metrics
        metrics = compute_metrics(results)
        print(f"{'═' * 70}")
        print("  МЕТРИКИ")
        print(f"{'═' * 70}")
        print(f"  Точность статуса:       {metrics['status_accuracy']}%")
        print(f"  Точность матчинга:      {metrics['match_accuracy']}%")
        print(f"  Средний Match Score:    {metrics['avg_match_score']}")
        print(f"  Валидировано:           {metrics['validated_count']}/{metrics['total_scenarios']}")
        print(f"  Счетов создано:         {metrics['invoiced_count']}")
        print(f"  Сумма счетов:           {metrics['total_invoice_value']}₽")
        print(f"  Среднее время:          {metrics['avg_total_time_ms']}ms")
        print(f"  Ошибок:                 {metrics['error_count']}")

        # Improvement plan
        plan = generate_improvement_plan(metrics, results)
        print(f"\n{'═' * 70}")
        print(f"  ПЛАН УЛУЧШЕНИЙ ({len(plan)} пунктов)")
        print(f"{'═' * 70}")
        for item in plan:
            print(f"\n  [{item['id']}] {item['area']} — {item['priority']}")
            print(f"    До: {item['metric_before']} → Цель: {item['target']}")
            print(f"    {item['description']}")
            print(f"    Действие: {item['action']}")

        # Write report JSON
        report = {
            "timestamp": datetime.now().isoformat(),
            "version": "2.1",
            "seed": {"suppliers": len(suppliers), "catalog_items": len(catalog)},
            "results": [asdict(r) for r in results],
            "metrics": metrics,
            "improvement_plan": plan,
        }
        report_path = os.path.join(os.path.dirname(__file__), "e2e_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n[REPORT] Сохранен: {report_path}")

        return report


if __name__ == "__main__":
    report = main()
