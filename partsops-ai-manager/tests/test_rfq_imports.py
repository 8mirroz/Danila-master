import json
from pathlib import Path
from sqlmodel import SQLModel, Session
from database import engine
from models import UploadArtifact
from services.rfq_imports import preview, save_mapping
from services.rfq_imports import build_rfq_text, import_idempotency_key

def test_preview_detects_rfq_columns_and_scopes_artifact(tmp_path):
    SQLModel.metadata.drop_all(engine); SQLModel.metadata.create_all(engine)
    source = Path(tmp_path) / "rfq.csv"; source.write_text("Артикул;Наименование;Количество\nA-1;Фильтр;2\n", encoding="utf-8")
    with Session(engine) as session:
        session.add(UploadArtifact(artifact_id="art-rfq", tenant_id="tenant-a", original_filename="rfq.csv", safe_filename="rfq.csv", stored_path=str(source), content_type="text/csv", status="stored")); session.commit()
        result = preview(session, "tenant-a", "art-rfq")
        assert result["valid_positions"] == 1 and result["sample_positions"][0]["quantity"] == 2
        assert result["mapping"]["part_number"] == "Артикул"
        item = save_mapping(session, "tenant-a", "Стандартный RFQ", result["mapping"])
        assert json.loads(item.mapping_json)["description"] == "Наименование"
        assert "A-1 Фильтр x2" in build_rfq_text(result)
        assert import_idempotency_key("art-rfq") == "rfq-import:art-rfq"
