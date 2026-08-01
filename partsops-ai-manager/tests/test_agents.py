"""
Tests: Agent Swarm Nodes and Workflows (v3)
"""
import pytest
from sqlmodel import SQLModel, create_engine, Session, delete
from sqlalchemy.pool import StaticPool

from models import PartRequest, RequestState, SupplierOffer, RequestEvent, MatchEvidence, ERPSyncLog, GoldenSample
from suppliers import Supplier, SupplierCatalogItem, Invoice, seed_database
import database

from database import engine
from agents import (
    IntakeState,
    intake_classifier_node,
    vin_inspector_node,
    parts_extractor_node,
    supplier_scatter_gather_node,
    pricing_guard_node,
    process_intake_request
)


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed if empty
        from sqlmodel import select
        suppliers = session.exec(select(Supplier)).all()
        if not suppliers:
            seed_database(session)
    yield
    SQLModel.metadata.drop_all(engine)


class TestIntakeClassifier:
    def test_classifier_passed_for_valid_parts(self):
        state = {"raw_request": "Нужны тормозные колодки на BMW X5", "agent_trace": []}
        result = intake_classifier_node(state)
        assert result["is_spam"] is False
        assert result["validation_status"] == "PASSED"
        assert len(result["agent_trace"]) > 0

    def test_classifier_failed_for_spam(self):
        state = {"raw_request": "привет как дела сколько стоит", "agent_trace": []}
        result = intake_classifier_node(state)
        assert result["is_spam"] is True
        assert result["validation_status"] == "FAILED"


class TestVINInspector:
    def test_vin_not_found(self):
        state = {"raw_request": "Нужны передние колодки на BMW X5", "agent_trace": []}
        result = vin_inspector_node(state)
        assert result["vehicle_vin"] is None
        assert result["vin_validity"] == "unknown"

    def test_vin_found_and_decoded(self):
        # 17 characters VIN candidate
        state = {"raw_request": "Ищу колодки для VIN WBA3C3C50EF123456 срочно", "agent_trace": []}
        result = vin_inspector_node(state)
        assert result["vehicle_vin"] == "WBA3C3C50EF123456"
        assert result["vin_validity"] == "valid"
        assert result["vehicle_make"] == "BMW"
        assert result["vehicle_model"] in ("X5", "3 Series")
        assert result["vehicle_year"] in (2018, 2014)

    def test_vin_decode_exception_no_mock_vehicle(self):
        """B12: LLM decode failure must not assign mock BMW X5 / Toyota Camry from WBA."""
        from unittest.mock import patch

        # VIN present, no brand/model keywords in free text
        state = {
            "raw_request": "Ищу колодки для VIN WBA3C3C50EF123456 срочно",
            "agent_trace": [],
        }
        with patch("app.agents.legacy_intake_pipeline.call_llm", side_effect=Exception("llm down")):
            result = vin_inspector_node(state)

        assert result["vehicle_vin"] == "WBA3C3C50EF123456"
        assert result["vin_validity"] == "unknown"
        assert result["vehicle_make"] is None
        assert result["vehicle_model"] is None
        assert result["vehicle_year"] is None
        assert any("decode failed" in t for t in result["agent_trace"])
        assert not any("Assigned mock" in t for t in result["agent_trace"])

    def test_vin_decode_exception_keeps_text_brand_heuristic(self):
        """B12: text keyword brand extraction still allowed after VIN decode failure."""
        from unittest.mock import patch

        state = {
            "raw_request": "Колодки BMW X5 VIN WBA3C3C50EF123456",
            "agent_trace": [],
        }
        with patch("app.agents.legacy_intake_pipeline.call_llm", side_effect=Exception("llm down")):
            result = vin_inspector_node(state)

        assert result["vin_validity"] == "unknown"
        assert result["vehicle_make"] == "BMW"
        assert result["vehicle_model"] == "X5"
        assert any("Extracted from text" in t for t in result["agent_trace"])


class TestPartsExtractor:
    def test_keyword_extraction_brakepads(self):
        state = {"raw_request": "тармозные калодки передние", "agent_trace": []}
        result = parts_extractor_node(state)
        parts = result["extracted_parts"]
        assert len(parts) == 1
        assert parts[0]["name"] in ("Тормозные колодки", "Тормозные колодки передние")

    def test_unknown_parts_fallback(self):
        state = {"raw_request": "какой-то непонятный текст без запчастей", "agent_trace": []}
        result = parts_extractor_node(state)
        parts = result["extracted_parts"]
        assert len(parts) == 1
        assert parts[0]["name"] == "Неизвестная деталь"


class TestSupplierScatterGather:
    def test_matching_scatter_gather(self):
        state = {
            "extracted_parts": [{"name": "Тормозные колодки", "quantity": 1}],
            "agent_trace": []
        }
        result = supplier_scatter_gather_node(state)
        parts = result["extracted_parts"]
        assert len(parts) == 1
        assert parts[0]["best_match"] is not None
        assert parts[0]["match_score"] > 50
        assert result["validation_status"] == "PASSED"


class TestPricingGuard:
    def test_pricing_guard_evaluation(self):
        # Setup pre-matched parts state
        state = {
            "extracted_parts": [{
                "name": "Тормозные колодки",
                "quantity": 1,
                "best_match": {
                    "catalog_id": "CAT-001",
                    "name": "Тормозные колодки передние BMW X5 (E70)",
                    "price": 4500.0,
                    "brand": "TRW"
                },
                "supplier": {
                    "supplier_id": "SUP-001",
                    "reliability_score": 0.92
                }
            }],
            "agent_trace": []
        }
        result = pricing_guard_node(state)
        assert result["pricing_evidence"] is not None
        assert result["margin_policy_passed"] is True
        assert result["price_anomaly_detected"] is False
        assert result["pricing_evidence"]["total"] > 5000.0


class TestE2EAgentWorkflow:
    def test_full_agent_workflow(self):
        text = "Нужны тормозные колодки на BMW X5 с VIN WBA3C3C50EF123456"
        res = process_intake_request(text)
        assert res["is_spam"] is False
        assert res["vehicle_vin"] == "WBA3C3C50EF123456"
        assert res["vin_validity"] == "valid"
        assert len(res["extracted_parts"]) > 0
        assert res["validation_status"] == "PASSED"

    def test_process_intake_request_applies_pii_masking(self):
        from unittest.mock import patch
        
        raw_text = "Нужны колодки на BMW WBA3C3C50EF123456 и мой тел +79123456789"
        
        with patch("pii.secure_pre_parse") as mock_secure:
            mock_secure.return_value = {
                "masked_text": "Нужны колодки на BMW [VIN_СКРЫТ] и мой тел [ТЕЛЕФОН_СКРЫТ]",
                "pii_map": {},
                "vehicle_context": {"make": "BMW", "model": "X5", "year": "2018", "vin_validity": "valid"}
            }
            
            process_intake_request(raw_text, vehicle_context=None)
            
            mock_secure.assert_called_once_with(raw_text)

    def test_parse_request_with_llm_system_prompt(self):
        from unittest.mock import patch
        from llm import parse_request_with_llm
        
        with patch("llm.call_llm") as mock_call_llm:
            mock_call_llm.return_value = '{"parts": [], "vehicle": {}, "priority": "normal"}'
            
            parse_request_with_llm("Тормозные колодки BMW")
            
            mock_call_llm.assert_called_once()
            kwargs = mock_call_llm.call_args.kwargs
            system_prompt = kwargs.get("system_prompt", "")
            
            assert "NEVER return or hallucinate prices" in system_prompt
            assert "NEVER return or hallucinate supplier names" in system_prompt


def test_processing_agent_does_not_match_another_organization_catalog():
    """Pipeline matching must use the request organization, not all supplier feeds."""
    from app.agents.base_agent import AgentContext
    from app.agents.processing_agent import ProcessingAgent

    with Session(engine) as session:
        session.exec(delete(SupplierCatalogItem))
        session.exec(delete(Supplier))
        session.add(
            Supplier(
                tenant_id="other-organization",
                supplier_id="SUP-OTHER",
                name="Other organization supplier",
                reliability_score=0.95,
            )
        )
        session.add(
            SupplierCatalogItem(
                tenant_id="other-organization",
                catalog_id="CAT-OTHER",
                supplier_id="SUP-OTHER",
                part_name="Тормозные колодки BMW X5",
                brand="ATE",
                price=1000.0,
            )
        )
        request = PartRequest(
            request_id="REQ-TENANT-ISOLATION",
            tenant_id="request-organization",
            source="test",
            status=RequestState.PART_EXTRACTION,
            customer_name="Tenant test",
            parts_json='[{"name":"Тормозные колодки BMW X5","quantity":1}]',
        )
        session.add(request)
        session.commit()

        result = ProcessingAgent(tenant_id="request-organization")._run_processing_pipeline(
            request,
            [{"name": "Тормозные колодки BMW X5", "quantity": 1}],
            AgentContext(tenant_id="request-organization", request_id=request.request_id),
        )

    assert result["success"] is False
    assert result["errors"] == ["No valid supplier matches found for any parts"]


def test_intake_scatter_gather_does_not_expose_another_organization_catalog():
    """Tenant context must survive the legacy intake path before a request exists."""
    with Session(engine) as session:
        session.exec(delete(SupplierCatalogItem))
        session.exec(delete(Supplier))
        session.add(
            Supplier(
                tenant_id="other-organization",
                supplier_id="SUP-OTHER-INTAKE",
                name="Other organization supplier",
                reliability_score=0.95,
            )
        )
        session.add(
            SupplierCatalogItem(
                tenant_id="other-organization",
                catalog_id="CAT-OTHER-INTAKE",
                supplier_id="SUP-OTHER-INTAKE",
                part_name="Тормозные колодки BMW X5",
                brand="ATE",
                price=1000.0,
            )
        )
        session.commit()

    result = supplier_scatter_gather_node(
        {
            "tenant_id": "request-organization",
            "extracted_parts": [{"name": "Тормозные колодки BMW X5", "quantity": 1}],
            "agent_trace": [],
        }
    )

    assert result["validation_status"] == "FAILED"
    assert result["extracted_parts"][0]["best_match"] is None
