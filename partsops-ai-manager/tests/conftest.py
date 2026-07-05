"""
pytest configuration: Sets TESTING environment flag before any code runs
and cleans up test_database.db after session finish.
"""
import os
import pytest

# Crucial: Set TESTING flag before any imports happen
os.environ["TESTING"] = "1"
os.environ["PARTSOPS_API_TOKEN"] = "test-token"

@pytest.fixture(scope="session", autouse=True)
def clean_test_db():
    # Remove test database if exists before runs
    db_file = "test_database.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
            
    yield
    
    # Clean up after session completes
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
