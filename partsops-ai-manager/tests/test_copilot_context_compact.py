"""Unit tests: compact ContextEnvelope for Hermes (token budget safety)."""
from __future__ import annotations

import json

from services.copilot_context import (
    ContextEnvelope,
    build_hermes_instructions,
    compact_envelope_for_hermes,
)


def _heavy_envelope() -> ContextEnvelope:
    """Envelope with bulky order dumps that must never reach Hermes full-size."""
    parts = [
        {"name": f"Part-{i}", "oem": f"OEM-{i:04d}", "quantity": i + 1}
        for i in range(20)
    ]
    heavy_parts_json = json.dumps(parts, ensure_ascii=False)
    # Simulate other heavy columns that might appear on PartRequest dumps
    selected = {
        "id": 42,
        "request_id": "REQ-COMPACT-01",
        "status": "BLOCKED",
        "customer_name": "ООО Тест",
        "priority": "high",
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_year": 2020,
        "vehicle_vin_masked": "XXXX…1234",
        "source": "email",
        "parts_json": heavy_parts_json,
        "match_evidence_json": json.dumps({"matches": [{"score": 0.9}] * 50}),
        "raw_email_body": "x" * 5000,
        "notes": "operator notes " * 100,
    }
    return ContextEnvelope(
        screen_id="order_details",
        screen_title="Детализация заказа",
        selected_request=selected,
        allowed_next_statuses=["IN_PROGRESS", "CANCELLED", "NEEDS_INFO"],
        evidence_summary={
            "gate_vin_valid": True,
            "gate_price_margin": False,
            "gate_supplier_sla": True,
        },
        blocking_reasons=["Маржа вне порога", "Ждём подтверждение"],
        allowed_user_actions=[
            {"action": "open_request", "label": "Открыть", "request_id": "REQ-COMPACT-01"},
            {"action": "open_screen", "label": "Канбан", "screen_id": "kanban_board"},
        ],
        available_help_sources=[
            {"source_id": f"help-{i}", "title": f"Help {i}", "body": "long " * 200}
            for i in range(6)
        ],
        timestamp="2026-08-08T12:00:00+00:00",
    )


def test_compact_envelope_strips_parts_json_and_heavy_fields():
    envelope = _heavy_envelope()
    compact = compact_envelope_for_hermes(envelope)

    assert "selected_request" in compact
    order = compact["selected_request"]
    assert order is not None
    assert "parts_json" not in order
    assert "match_evidence_json" not in order
    assert "raw_email_body" not in order
    assert "notes" not in order

    # Operator-relevant fields kept
    assert order["request_id"] == "REQ-COMPACT-01"
    assert order["status"] == "BLOCKED"
    assert order["customer_name"] == "ООО Тест"
    assert order["parts_count"] == 20
    assert isinstance(order["parts_preview"], list)
    assert len(order["parts_preview"]) <= 4
    assert "Toyota" in (order.get("vehicle") or "")

    # Help sources capped and body stripped
    assert len(compact["available_help_sources"]) <= 3
    for src in compact["available_help_sources"]:
        assert "body" not in src
        assert "source_id" in src


def test_build_hermes_instructions_shorter_than_full_envelope_dump():
    envelope = _heavy_envelope()
    full_dump = json.dumps(envelope.model_dump(), ensure_ascii=False)
    instructions = build_hermes_instructions(envelope)

    assert len(instructions) < len(full_dump)
    # Compact path must not re-embed raw parts_json payload
    assert "parts_json" not in instructions
    assert "match_evidence_json" not in instructions
    assert "OEM-0000" not in instructions  # raw part rows not dumped
    assert "READ-ONLY" in instructions
    assert "REQ-COMPACT-01" in instructions
    assert "Контекст (JSON):" in instructions
