import sys
import os
from logging.config import fileConfig

# Add application root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from alembic import context
from sqlmodel import SQLModel
from settings import settings
from database import engine

# Import all models to register them on SQLModel.metadata
from models import (AdaptationDecisionRecord, ClientApproval, ContractArchiveRecord, ContractAuditRun,
                    ContractExceptionRecord, ContractExport, ContractGap, ContractPosition,
                    ContractPurchaseRecord, ContractReceiptVerification, ContractRequirement, ERPSyncLog,
                    GoldenSample, MatchEvidence, OEMCandidate, PartRequest, PriceEvidence,
                    PurchaseAuthorization, RequirementCoverage, RequestEvent, SupplierOffer,
                    Organization, User, Membership, Subscription, UsageEvent,
    IntegrationConnection, ServiceApiKey, OnboardingState, ImportMapping, QuoteDocument, QuoteVersion,
                    AnalogCandidate, CompatibilityEvidence, ContractWorkflowState,
                    ContractWorkflowEvent)  # noqa
from suppliers import Supplier, SupplierCatalogItem, Invoice  # noqa
from models_copilot import CopilotConversation, CopilotMessage, CopilotRun  # noqa

# Alembic Config object
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
