"""
PartsOps AI Manager v3 — Core Data Models
Implements Event Store, State Machine, Evidence Objects, ERP Sync Log.
All tables follow append-only event-sourced patterns.

Adds (Automation Build Pack): JobRun, AutomationLock, OutboundMessage,
LLMUsageLog, RequestScore, ApprovalTicket. These are owned by the
`app.automation.*` layer but live in models.py so SQLModel.metadata sees
them at engine init.
"""
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field


# ──────────────────────────────────────────────
# STATE MACHINE
# ──────────────────────────────────────────────

class RequestState(str, Enum):
    NEW = "NEW"
    NORMALIZING = "NORMALIZING"
    PARSING = "PARSING"
    VIN_CHECK = "VIN_CHECK"
    PART_EXTRACTION = "PART_EXTRACTION"
    MATCHING = "MATCHING"
    SUPPLIER_SEARCH = "SUPPLIER_SEARCH"
    OFFER_RANKING = "OFFER_RANKING"
    PRICING_REVIEW = "PRICING_REVIEW"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    ERP_SYNCING = "ERP_SYNCING"
    INVOICE_DRAFTED = "INVOICE_DRAFTED"
    SENT_TO_CLIENT = "SENT_TO_CLIENT"
    PAID = "PAID"
    PURCHASE_ORDERED = "PURCHASE_ORDERED"
    FULFILLED = "FULFILLED"
    CLOSED = "CLOSED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REWORK = "REWORK"
    ERP_SYNC_FAILED = "ERP_SYNC_FAILED"
    CLIENT_REJECTED = "CLIENT_REJECTED"
    EXPIRED = "EXPIRED"
    SUPPLIER_ISSUE = "SUPPLIER_ISSUE"
    RETURN_CASE = "RETURN_CASE"
    NEEDS_MANUAL_PARSE = "NEEDS_MANUAL_PARSE"
    FINANCE_REVIEW = "FINANCE_REVIEW"

# Allowed transitions per state (state_machine.py imports this)
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    RequestState.NEW: [RequestState.NORMALIZING, RequestState.CANCELLED],
    RequestState.NORMALIZING: [RequestState.PARSING, RequestState.NEEDS_MANUAL_PARSE, RequestState.FAILED],
    RequestState.PARSING: [RequestState.VIN_CHECK, RequestState.NEEDS_CLARIFICATION, RequestState.FAILED],
    RequestState.VIN_CHECK: [RequestState.PART_EXTRACTION, RequestState.NEEDS_CLARIFICATION, RequestState.MANUAL_REVIEW],
    RequestState.PART_EXTRACTION: [RequestState.MATCHING, RequestState.NEEDS_CLARIFICATION, RequestState.MANUAL_REVIEW],
    RequestState.MATCHING: [RequestState.SUPPLIER_SEARCH, RequestState.MANUAL_REVIEW, RequestState.NEEDS_CLARIFICATION],
    RequestState.SUPPLIER_SEARCH: [RequestState.OFFER_RANKING, RequestState.MANUAL_REVIEW, RequestState.FAILED],
    RequestState.OFFER_RANKING: [RequestState.PRICING_REVIEW, RequestState.MANUAL_REVIEW],
    RequestState.PRICING_REVIEW: [RequestState.READY_FOR_APPROVAL, RequestState.FINANCE_REVIEW, RequestState.MANUAL_REVIEW],
    RequestState.READY_FOR_APPROVAL: [RequestState.APPROVED, RequestState.CLIENT_REJECTED, RequestState.REWORK],
    RequestState.APPROVED: [RequestState.ERP_SYNCING, RequestState.REWORK],
    RequestState.ERP_SYNCING: [RequestState.INVOICE_DRAFTED, RequestState.ERP_SYNC_FAILED],
    RequestState.INVOICE_DRAFTED: [RequestState.SENT_TO_CLIENT, RequestState.REWORK],
    RequestState.SENT_TO_CLIENT: [RequestState.PAID, RequestState.CLIENT_REJECTED, RequestState.EXPIRED],
    RequestState.PAID: [RequestState.PURCHASE_ORDERED, RequestState.FULFILLED],
    RequestState.PURCHASE_ORDERED: [RequestState.FULFILLED, RequestState.SUPPLIER_ISSUE],
    RequestState.FULFILLED: [RequestState.CLOSED, RequestState.RETURN_CASE],
    RequestState.CLOSED: [],
    RequestState.MANUAL_REVIEW: [
        RequestState.MATCHING, RequestState.SUPPLIER_SEARCH,
        RequestState.APPROVED, RequestState.CANCELLED, RequestState.REWORK,
    ],
    RequestState.NEEDS_CLARIFICATION: [RequestState.PARSING, RequestState.CANCELLED],
    RequestState.FAILED: [RequestState.NORMALIZING, RequestState.CANCELLED],
    RequestState.REWORK: [RequestState.MATCHING, RequestState.SUPPLIER_SEARCH, RequestState.MANUAL_REVIEW],
    RequestState.ERP_SYNC_FAILED: [RequestState.ERP_SYNCING, RequestState.MANUAL_REVIEW],
    RequestState.RETURN_CASE: [RequestState.CLOSED],
    RequestState.SUPPLIER_ISSUE: [RequestState.PURCHASE_ORDERED, RequestState.MANUAL_REVIEW],
    RequestState.NEEDS_MANUAL_PARSE: [RequestState.PARSING, RequestState.CANCELLED],
    RequestState.FINANCE_REVIEW: [RequestState.READY_FOR_APPROVAL, RequestState.REWORK, RequestState.CANCELLED],
    RequestState.CLIENT_REJECTED: [RequestState.CANCELLED, RequestState.REWORK],
    RequestState.EXPIRED: [RequestState.CANCELLED],
}


# ──────────────────────────────────────────────
# PRIORITY
# ──────────────────────────────────────────────

class RequestPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    URGENT = "urgent"
    VIP = "vip"


# ──────────────────────────────────────────────
# CORE REQUEST (v3 — extended schema)
# ──────────────────────────────────────────────

class PartRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    request_id: str = Field(index=True, unique=True)
    idempotency_key: Optional[str] = Field(default=None, index=True)

    source: str  # telegram|email|web|crm|manual|api
    status: str = Field(default=RequestState.NEW)
    priority: str = Field(default=RequestPriority.NORMAL)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Customer (masked PII for agent layer; raw stored in separate secure field)
    customer_name: Optional[str] = None
    customer_phone_masked: Optional[str] = None   # e.g. +7-***-***-4567
    customer_email_masked: Optional[str] = None   # e.g. jo***@gmail.com
    customer_erp_id: Optional[str] = None

    # Vehicle
    vehicle_vin_masked: Optional[str] = None      # last 6 chars visible
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_generation: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_engine: Optional[str] = None
    vehicle_confidence: Optional[float] = None
    vin_validity: Optional[str] = None            # valid|invalid|partial|unknown

    # Parts (JSON array of part_intent objects)
    parts_json: Optional[str] = None

    # Matching & pricing
    match_evidence_json: Optional[str] = None     # JSON array of MatchEvidence
    pricing_evidence_json: Optional[str] = None   # JSON pricing breakdown
    margin_policy_passed: Optional[bool] = None

    # ERP
    erp_quotation_ref: Optional[str] = None
    erp_invoice_ref: Optional[str] = None
    erp_payment_ref: Optional[str] = None

    # Audit
    audit_chain_complete: bool = Field(default=False)
    raw_input_ref: Optional[str] = None           # blob reference to original text

    # Client Portal (Phase 9) — публичный токен для отслеживания заявки клиентом
    tracking_token: Optional[str] = Field(default=None, index=True, unique=True)
    tracking_token_expires_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# EVENT STORE (append-only log)
# ──────────────────────────────────────────────

class RequestEvent(SQLModel, table=True):
    """Immutable event log. Never update, only insert."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    event_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)

    event_type: str        # e.g. REQUEST_RECEIVED, STATE_CHANGED, MATCH_CANDIDATE_CREATED
    actor_type: str        # user|agent|system|external
    actor_id: str = Field(default="system")

    occurred_at: datetime = Field(default_factory=datetime.utcnow)

    # JSON payload for event-specific data
    payload_json: Optional[str] = None
    evidence_refs_json: Optional[str] = None   # JSON list of evidence IDs

    # Audit chain integrity
    previous_event_hash: Optional[str] = None
    event_hash: Optional[str] = None


# Canonical event types
class EventType(str, Enum):
    REQUEST_RECEIVED = "REQUEST_RECEIVED"
    DOCUMENT_PARSED = "DOCUMENT_PARSED"
    VIN_VALIDATED = "VIN_VALIDATED"
    PART_INTENT_EXTRACTED = "PART_INTENT_EXTRACTED"
    MATCH_CANDIDATE_CREATED = "MATCH_CANDIDATE_CREATED"
    SUPPLIER_QUERIED = "SUPPLIER_QUERIED"
    OFFER_RECEIVED = "OFFER_RECEIVED"
    PRICE_ANOMALY_DETECTED = "PRICE_ANOMALY_DETECTED"
    MARGIN_POLICY_CHECKED = "MARGIN_POLICY_CHECKED"
    STATE_CHANGED = "STATE_CHANGED"
    MANAGER_APPROVED = "MANAGER_APPROVED"
    MANAGER_REJECTED = "MANAGER_REJECTED"
    MANUAL_CORRECTION_SAVED = "MANUAL_CORRECTION_SAVED"
    ERP_DOCUMENT_CREATED = "ERP_DOCUMENT_CREATED"
    ERP_SYNC_FAILED = "ERP_SYNC_FAILED"
    PAYMENT_STATUS_SYNCED = "PAYMENT_STATUS_SYNCED"
    GOLDEN_SAMPLE_CREATED = "GOLDEN_SAMPLE_CREATED"
    PII_MASKED = "PII_MASKED"
    IDEMPOTENCY_HIT = "IDEMPOTENCY_HIT"
    SLA_BREACHED = "SLA_BREACHED"


# ──────────────────────────────────────────────
# MATCH EVIDENCE
# ──────────────────────────────────────────────

class MatchEvidence(SQLModel, table=True):
    """Evidence object for each part match decision."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    evidence_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    part_intent_id: str = Field(index=True)
    catalog_item_id: Optional[str] = None

    # v3 9-component formula scores
    oem_exact_score: float = Field(default=0.0)
    brand_article_score: float = Field(default=0.0)
    normalized_name_score: float = Field(default=0.0)
    vehicle_compatibility_score: float = Field(default=0.0)
    side_position_score: float = Field(default=0.0)
    quantity_pack_score: float = Field(default=0.0)
    language_synonym_score: float = Field(default=0.0)
    historical_acceptance_score: float = Field(default=0.0)
    supplier_data_quality_score: float = Field(default=0.0)
    final_score: float = Field(default=0.0)

    decision: str = Field(default="manual_review")  # auto_candidate|manual_review|reject
    matched_fields_json: Optional[str] = None
    conflicts_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# ERP SYNC LOG
# ──────────────────────────────────────────────

class ERPSyncLog(SQLModel, table=True):
    """Log of all ERP synchronization attempts."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    sync_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)

    erp_document_type: str    # Customer|Quotation|SalesInvoice|PurchaseOrder|StockEntry
    erp_document_name: Optional[str] = None
    idempotency_key: str = Field(index=True)

    status: str = Field(default="PENDING")  # PENDING|SUCCESS|FAILED|RETRYING
    attempt_count: int = Field(default=0)
    last_error: Optional[str] = None
    erp_response_json: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_attempt_at: Optional[datetime] = None
    succeeded_at: Optional[datetime] = None


# ──────────────────────────────────────────────
# GOLDEN DATASET (Learning Loop)
# ──────────────────────────────────────────────

class GoldenSample(SQLModel, table=True):
    """Approved correction samples for model training and regression."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    sample_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)

    source_text: str
    corrected_parts_json: str       # JSON array of corrected part_intent objects
    corrected_vehicle_json: Optional[str] = None

    correction_reason_tags: Optional[str] = None  # JSON list: wrong_vin|wrong_brand|wrong_side|...

    approved_by: str = Field(default="")
    approved_at: Optional[datetime] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# LEGACY / COMPAT
# ──────────────────────────────────────────────

class SupplierOffer(SQLModel, table=True):
    """Kept for backward compatibility. Use SupplierCatalogItem for new code."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    offer_id: str = Field(index=True)
    request_id: str = Field(index=True)
    supplier_id: str
    part_name: str
    brand: str
    sale_price: float
    stock_qty: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# INTELLIGENCE LAYER (Phase 4)
# ──────────────────────────────────────────────

class PriceHistoryLedger(SQLModel, table=True):
    """Append-only price history of catalog items to track trends and calculate 90d medians."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    catalog_id: str = Field(index=True)
    price: float = Field(default=0.0)
    currency: str = Field(default="RUB")
    recorded_at: datetime = Field(default_factory=datetime.utcnow)


class SupplierReliabilityLog(SQLModel, table=True):
    """Event log recording supplier reliability changes over time."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    supplier_id: str = Field(index=True)
    reliability_score: float = Field(default=0.0)
    event_type: str = Field(default="initial")  # initial|delivery_feedback|sla_breach|manual_adjustment
    reason: Optional[str] = None
    logged_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# UPLOAD ARTIFACT (binary intakes: PDFs, photos, CSVs, vendor feeds)
# ──────────────────────────────────────────────

class UploadArtifact(SQLModel, table=True):
    """Persistent record of an uploaded file for a tenant.

    Storage backs on disk at 08_DATA/uploads/<tenant>/<artifact_id> with the
    original filename stored separately. Original bytes are never mutated;
    all downstream operators work on the resolved `stored_path`.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    artifact_id: str = Field(index=True, unique=True)
    tenant_id: str = Field(default="default", index=True)
    request_id: Optional[str] = Field(default=None, index=True)

    original_filename: str
    safe_filename: str                   # sanitized for filesystem
    stored_path: str                     # absolute path on disk
    content_type: Optional[str] = None
    detected_mime: Optional[str] = None  # magic-byte sniff result
    size_bytes: int = Field(default=0)
    sha256: str = Field(default="", index=True)  # dedupe + integrity

    source: str = Field(default="upload")  # upload|api|email|telegram
    uploaded_by: str = Field(default="anonymous")
    metadata_json: Optional[str] = None   # free-form introspection hints

    status: str = Field(default="stored") # stored|quarantined|rejected|attached
    rejection_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# AUTOMATION LAYER (Build Pack)
# ──────────────────────────────────────────────

class JobRun(SQLModel, table=True):
    """One execution of a registered job. Audit-only — never affects runtime."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    job_id: str = Field(index=True)
    job_name: str = Field(index=True)
    status: str = Field(default="running")  # running|completed|failed|cancelled
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    dry_run: bool = Field(default=False)
    events_emitted: int = Field(default=0)
    requests_processed: int = Field(default=0)
    requests_skipped: int = Field(default=0)
    error_count: int = Field(default=0)
    error_message: Optional[str] = None
    result_json: Optional[str] = None
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AutomationLock(SQLModel, table=True):
    """Tenant-scoped named lock with TTL-based expiry."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    lock_name: str = Field(index=True)
    owner_key: str = Field(default="")
    acquired_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    released_at: Optional[datetime] = None
    status: str = Field(default="active")  # active|expired|released


class OutboundMessage(SQLModel, table=True):
    """Outbox — every external send lives here before it is dispatched."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    request_id: Optional[str] = Field(default=None, index=True)
    channel: str  # email|telegram|webhook|sms
    recipient: str
    subject: Optional[str] = None
    body_text: str
    payload_json: Optional[str] = None
    idempotency_key: str = Field(index=True, unique=True)
    status: str = Field(default="pending")  # pending|sent|failed|delivered|bounced
    attempts: int = Field(default=0)
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LLMUsageLog(SQLModel, table=True):
    """Per-call LLM usage, persisted for KPI / cost dashboards."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    request_id: Optional[str] = Field(default=None, index=True)
    job_run_id: Optional[str] = Field(default=None, index=True)
    provider: str
    model: str
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0)
    cost_usd: float = Field(default=0.0)
    priority: str = Field(default="normal")
    latency_ms: Optional[int] = None
    status: str = Field(default="ok")  # ok|blocked|error
    correlation_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RequestScore(SQLModel, table=True):
    """Aggregated scores for one request — refreshed by jobs/pipelines."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    request_id: str = Field(index=True)
    priority_score: Optional[float] = None
    confidence_score: Optional[float] = None
    intent_confidence: Optional[float] = None
    field_completeness: Optional[float] = None
    readiness_score: Optional[float] = None
    match_score: Optional[float] = None
    evidence_score: Optional[float] = None
    duplicate_score: Optional[float] = None
    risk_score: Optional[float] = None
    supplier_score: Optional[float] = None
    margin_score: Optional[float] = None
    composite_score: Optional[float] = None
    weak_match_risk: Optional[bool] = None
    supplier_risk: Optional[bool] = None
    return_risk: Optional[bool] = None
    low_margin_risk: Optional[bool] = None
    resolved: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalTicket(SQLModel, table=True):
    """Persistent record for human-approval queue (low-margin / erp_sync)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    ticket_id: str = Field(index=True, unique=True)
    request_id: Optional[str] = Field(default=None, index=True)
    tool_name: str
    reason: str = ""
    role_required: str = "admin"
    requested_by: str = "system"
    status: str = Field(default="pending")  # pending|approved|rejected|cancelled
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    payload_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
