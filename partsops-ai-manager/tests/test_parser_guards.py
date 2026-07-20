"""Tests for supplier parser size/row guards."""
import io
import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, create_engine, Session, select

from database import engine
from models import PartRequest, RequestState
from suppliers import Supplier, SupplierTable, SupplierTableRow, seed_database
from services.supplier_service import SupplierService, _extract_supplier_table_rows
from app.automation.storage import storage
from settings import Settings


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


def test_large_file_rejected_at_storage_level():
    settings = Settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    oversized = b"x" * (max_bytes + 1)
    with pytest.raises(ValueError, match="UPLOAD_FILE_TOO_LARGE"):
        storage.save_file("tenant_test", "art_big", io.BytesIO(oversized), "huge.csv")


def test_parser_rejects_too_many_rows():
    huge_rows = [{"part_name": f"Part {i}", "price": 1.0} for i in range(60000)]
    with pytest.raises(ValueError, match="UPLOAD_TOO_MANY_ROWS"):
        _extract_supplier_table_rows(huge_rows)
