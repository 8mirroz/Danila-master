"""Durable pipeline-run API contracts for the Kanban operator flow."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

from database import engine
from main import app
from models import PartRequest, RequestState


client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-token", "X-Tenant-ID": "default"}


@pytest.fixture(autouse=True)
def clean_database():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            PartRequest(
                request_id="REQ-PIPELINE-RUN",
                tenant_id="default",
                source="manual",
                status=RequestState.PART_EXTRACTION,
                customer_name="ООО Тест",
                parts_json=json.dumps([{"name": "Фильтр", "quantity": 1}]),
            )
        )
        session.commit()
    yield
    SQLModel.metadata.drop_all(engine)


def test_start_pipeline_run_is_durable_and_idempotent():
    first = client.post(
        "/api/requests/REQ-PIPELINE-RUN/pipeline-runs",
        json={"requested_lane": "matching"},
        headers=AUTH_HEADERS,
    )
    assert first.status_code == 202
    payload = first.json()
    assert payload["status"] == "queued"
    assert payload["start_from"] == "processing"
    assert payload["run_id"].startswith("PR-")

    second = client.post(
        "/api/requests/REQ-PIPELINE-RUN/pipeline-runs",
        json={"requested_lane": "matching"},
        headers=AUTH_HEADERS,
    )
    assert second.status_code == 200
    assert second.json()["run_id"] == payload["run_id"]
    assert second.json()["idempotent"] is True


def test_pipeline_run_refuses_requests_without_parts():
    with Session(engine) as session:
        request = session.get(PartRequest, 1)
        assert request is not None
        request.parts_json = "[]"
        session.add(request)
        session.commit()

    response = client.post(
        "/api/requests/REQ-PIPELINE-RUN/pipeline-runs",
        json={"requested_lane": "matching"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422
    assert "позици" in str(response.json()["detail"]).lower()
