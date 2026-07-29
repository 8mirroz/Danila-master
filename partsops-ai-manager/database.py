from sqlmodel import SQLModel, create_engine, Session
from settings import settings

db_url = settings.DATABASE_URL

# Normalize postgres:// to postgresql:// for SQLAlchemy
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if db_url.startswith("postgresql://"):
    engine = create_engine(
        db_url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        pool_pre_ping=True,
        echo=False
    )
else:
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        poolclass=NullPool,
        echo=False
    )

def init_db():
    # Import all models so SQLModel.metadata knows about them
    from models import (PartRequest, SupplierOffer, RequestEvent, MatchEvidence, ERPSyncLog, GoldenSample,
                        ContractPosition, PriceEvidence, ContractExport, ContractAuditRun,
                        ContractRequirement, RequirementCoverage, ContractGap, AdaptationDecisionRecord,
                        ContractExceptionRecord, ClientApproval, PurchaseAuthorization, OEMCandidate,
                        AnalogCandidate, CompatibilityEvidence, ContractWorkflowState,
                        ContractWorkflowEvent, PipelineRun, PipelineRunEvent)  # noqa
    from suppliers import Supplier, SupplierCatalogItem, Invoice  # noqa
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
