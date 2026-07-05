import os
from sqlmodel import SQLModel, create_engine, Session

import os
sqlite_file_name = "test_database.db" if os.environ.get("TESTING") == "1" else "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=False)

def init_db():
    # Import all models so SQLModel.metadata knows about them
    from models import PartRequest, SupplierOffer, RequestEvent, MatchEvidence, ERPSyncLog, GoldenSample  # noqa
    from suppliers import Supplier, SupplierCatalogItem, Invoice  # noqa
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
