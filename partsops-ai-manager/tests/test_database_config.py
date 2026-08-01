import os
from unittest import mock
import pytest

def test_default_settings():
    from settings import settings
    # For testing environment, TESTING is set to 1 in conftest.py
    assert settings.TESTING is True
    assert settings.DATABASE_URL == "sqlite:///test_database.db"
    assert settings.DB_POOL_SIZE == 10
    assert settings.DB_MAX_OVERFLOW == 20
    assert settings.DB_POOL_RECYCLE_SECONDS == 1800
    assert settings.MAX_UPLOAD_SIZE_MB == 15
    assert "pdf" in settings.UPLOAD_ALLOWED_EXTENSIONS
    assert "xlsx" in settings.UPLOAD_ALLOWED_EXTENSIONS
    assert settings.UPLOAD_DIR == "08_DATA/uploads"
    assert settings.ENABLE_STRICT_UPLOAD_VALIDATION is True
    assert settings.ENABLE_STRICT_TENANT_ENFORCEMENT is True

def test_custom_settings():
    custom_env = {
        "TESTING": "0",
        "DATABASE_URL": "postgresql://user:pass@host:5432/db",
        "DB_POOL_SIZE": "15",
        "DB_MAX_OVERFLOW": "30",
        "DB_POOL_RECYCLE_SECONDS": "900",
        "MAX_UPLOAD_SIZE_MB": "25",
        "UPLOAD_ALLOWED_EXTENSIONS": ".pdf, .csv, docx",
        "UPLOAD_DIR": "tmp/uploads",
        "ENABLE_STRICT_UPLOAD_VALIDATION": "false",
        "ENABLE_STRICT_TENANT_ENFORCEMENT": "0"
    }
    with mock.patch.dict(os.environ, custom_env):
        from settings import Settings
        custom_settings = Settings()
        assert custom_settings.TESTING is False
        assert custom_settings.DATABASE_URL == "postgresql://user:pass@host:5432/db"
        assert custom_settings.DB_POOL_SIZE == 15
        assert custom_settings.DB_MAX_OVERFLOW == 30
        assert custom_settings.DB_POOL_RECYCLE_SECONDS == 900
        assert custom_settings.MAX_UPLOAD_SIZE_MB == 25
        assert custom_settings.UPLOAD_ALLOWED_EXTENSIONS == ["pdf", "csv", "docx"]
        assert custom_settings.UPLOAD_DIR == "tmp/uploads"
        assert custom_settings.ENABLE_STRICT_UPLOAD_VALIDATION is False
        assert custom_settings.ENABLE_STRICT_TENANT_ENFORCEMENT is False

def test_production_requires_postgresql_database_url():
    with mock.patch.dict(os.environ, {"TESTING": "0", "PARTSOPS_ENV": "production", "DATABASE_URL": "sqlite:///database.db"}):
        from settings import Settings
        production_settings = Settings()
        with pytest.raises(RuntimeError, match="PostgreSQL DATABASE_URL is required"):
            _ = production_settings.DATABASE_URL
