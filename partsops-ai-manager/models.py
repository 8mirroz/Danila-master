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
import uuid
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
    CONTRACT_AUDITED = "CONTRACT_AUDITED"
    REQUIREMENT_MAPPED = "REQUIREMENT_MAPPED"
    GAP_REGISTERED = "GAP_REGISTERED"
    ADR_RECORDED = "ADR_RECORDED"
    EXPORT_VALIDATED = "EXPORT_VALIDATED"
    CLIENT_APPROVED = "CLIENT_APPROVED"
    PURCHASE_AUTHORIZED = "PURCHASE_AUTHORIZED"
    PURCHASE_RECORDED = "PURCHASE_RECORDED"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"
    CONTRACT_ARCHIVED = "CONTRACT_ARCHIVED"
    OEM_CANDIDATE_VERIFIED = "OEM_CANDIDATE_VERIFIED"
    ANALOG_CANDIDATE_VERIFIED = "ANALOG_CANDIDATE_VERIFIED"
    COMPATIBILITY_EVIDENCE_RECORDED = "COMPATIBILITY_EVIDENCE_RECORDED"
    CONTRACT_WORKFLOW_CHANGED = "CONTRACT_WORKFLOW_CHANGED"
    CONTRACT_EXCEPTION_UPDATED = "CONTRACT_EXCEPTION_UPDATED"


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


class PipelineRun(SQLModel, table=True):
    """Durable, tenant-scoped execution request for the operator pipeline."""
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(unique=True)
    tenant_id: str = Field(default="default", index=True)
    request_id: str = Field(index=True)
    requested_by: str = Field(default="operator")
    requested_lane: Optional[str] = None
    start_from: str
    correlation_id: str = Field(index=True)
    status: str = Field(default="queued", index=True)  # queued|running|completed|failed|blocked
    result_json: Optional[str] = None
    error_message: Optional[str] = None
    lease_owner: Optional[str] = Field(default=None, index=True)
    lease_expires_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineRunEvent(SQLModel, table=True):
    """Append-only, PII-safe event stream that supports SSE replay."""
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    tenant_id: str = Field(default="default", index=True)
    sequence: int = Field(default=1)
    event_type: str
    phase: Optional[str] = None
    message: str = Field(default="")
    payload_json: Optional[str] = None
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
    max_attempts: int = Field(default=3)
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
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


# ──────────────────────────────────────────────
# CONTRACT № 2026.170160 — FLEET & TARIFFS
# ──────────────────────────────────────────────

class FleetVehicle(SQLModel, table=True):
    """59 VINs from Contract Appendix 1 — strict fleet registry."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    vin: str = Field(max_length=17, index=True, unique=True)
    make: str
    model: str
    year: int
    engine: Optional[str] = None
    transmission: Optional[str] = None
    fuel_type: Optional[str] = None
    odometer_km: int = Field(default=0)
    fuel_level_percent: int = Field(default=100)
    status: str = Field(default="active", index=True)  # active|maintenance|retired
    contract_ref: str = Field(default="2026.170160")
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceTariff(SQLModel, table=True):
    """Service tariffs from Contract Appendix 2."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    tariff_code: str = Field(index=True, unique=True)
    service_name: str
    category: str  # diagnostics|maintenance|evacuation|on_site
    unit: str = Field(default="per_service")  # per_service|per_km|per_hour
    base_price_rub: float
    vat_rate: float = Field(default=0.20)
    sla_hours: int  # 2, 24, 168
    penalty_rate_per_day_pct: float = Field(default=0.1)  # 0.1% per day
    contract_ref: str = Field(default="2026.170160")
    is_active: bool = Field(default=True, index=True)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContractPenaltyConfig(SQLModel, table=True):
    """Single source of truth for penalty calculation (Contract § SLA & Penalties)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    contract_ref: str = Field(index=True, unique=True)
    contract_total_value_rub: float
    penalty_pct_per_day: float = Field(default=0.001)  # 0.1%
    penalty_rub_per_day: float  # pre-calculated = contract_total * penalty_pct
    max_penalty_pct: float = Field(default=0.10)  # cap at 10%
    currency: str = Field(default="RUB")
    effective_from: datetime
    effective_to: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# CONTRACT OPERATIONS — PRICE EVIDENCE
# ──────────────────────────────────────────────

class ContractPosition(SQLModel, table=True):
    """One immutable contract-list position and its current selection."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    position_id: str = Field(index=True, unique=True)
    position_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True)
    request_id: str = Field(index=True)
    contract_ref: str = Field(index=True)
    line_no: int
    part_number: str
    description: Optional[str] = None
    quantity: int = Field(default=1)
    selected_evidence_id: Optional[str] = None
    review_status: str = Field(default="pending")  # pending|auto_selected|review|approved
    position_version: int = Field(default=1)
    vehicle_identity_status: str = Field(default="unknown")  # identified|partial|unknown|exception
    vehicle_data_source: Optional[str] = None
    vin_checked_at: Optional[datetime] = None
    criticality: str = Field(default="Medium")  # Critical|High|Medium|Low
    delivery_deadline_at: Optional[datetime] = None
    max_delivery_days: Optional[int] = None
    safety_related: bool = Field(default=False)
    warranty_impact: bool = Field(default=False)
    requirement_id: Optional[str] = Field(default=None, index=True)
    completeness_status: str = Field(default="partial")  # complete|partial|missing|blocked
    blocking_status: str = Field(default="blocked")  # clear|blocked|warning
    blocking_error_code: Optional[str] = None
    change_reason: Optional[str] = None
    selected_reason: Optional[str] = None
    calculation_json: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PriceEvidence(SQLModel, table=True):
    """Append-only snapshot proving a price observed by a crawler adapter."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    evidence_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    position_id: str = Field(index=True)
    source: str  # exist.ru|autodoc.ru|rossko.ru
    price: float
    currency: str = Field(default="RUB")
    source_url: str
    captured_at: datetime
    freshness_ttl_hours: int = Field(default=24)
    expires_at: Optional[datetime] = None
    availability_status: str = Field(default="available")  # available|unavailable|unknown|changed
    package_quantity: int = Field(default=1)
    unit: str = Field(default="piece")
    condition: str = Field(default="new")
    vat_included: bool = Field(default=True)
    available_quantity: Optional[int] = None
    warehouse: Optional[str] = None
    delivery_region: Optional[str] = None
    delivery_eta_days: Optional[int] = None
    order_status: str = Field(default="observed")  # observed|rechecked|unavailable|ordered
    screenshot_ref: str
    screenshot_sha256: Optional[str] = None
    screenshot_readability_status: str = Field(default="unknown")  # readable|partial|unreadable|unknown
    screenshot_completeness_status: str = Field(default="partial")  # complete|partial|missing
    screenshot_validation_json: Optional[str] = None
    html_sha256: Optional[str] = None
    adapter_run_id: Optional[str] = None
    parser_version: Optional[str] = None
    retry_count: int = Field(default=0)
    unavailable_reason: Optional[str] = None
    comparability_status: str = Field(default="REQUIRES_REVIEW")
    evidence_status: str = Field(default="pending")  # pending|valid|stale|invalid
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OEMCandidate(SQLModel, table=True):
    """Original manufacturer candidate for a contract position."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    candidate_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    position_id: str = Field(index=True)
    oem_number: str = Field(index=True)
    manufacturer: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    evidence_ref: Optional[str] = None
    confidence: float = Field(default=0.0)
    lifecycle_status: str = Field(default="active")  # active|superseded|obsolete|unknown
    previous_article: Optional[str] = None
    replacement_article: Optional[str] = None
    verification_status: str = Field(default="pending")  # pending|verified|rejected|needs_review
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AnalogCandidate(SQLModel, table=True):
    """Analog or replacement candidate linked to a verified OEM/position."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    candidate_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    position_id: str = Field(index=True)
    oem_candidate_id: Optional[str] = Field(default=None, index=True)
    article: str = Field(index=True)
    brand: str
    manufacturer: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    cross_reference_source: Optional[str] = None
    interchange_type: str = Field(default="unknown")  # direct|conditional|kit|unknown
    lifecycle_status: str = Field(default="active")
    previous_article: Optional[str] = None
    replacement_article: Optional[str] = None
    independent_confirmations: int = Field(default=0)
    compatibility_score: int = Field(default=0)
    evidence_score: int = Field(default=0)
    quality_tier: str = Field(default="PREMIUM_AFTERMARKET")  # OES|PREMIUM_AFTERMARKET|BUDGET|SPEC_MATCH
    risk_score: int = Field(default=15)  # 0-100%
    risk_factors_json: Optional[str] = None
    price_delta_percent: Optional[float] = None
    eta_delta_days: Optional[int] = None
    manual_review_status: str = Field(default="pending")  # pending|approved|rejected|needs_review
    rejection_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CompatibilityEvidence(SQLModel, table=True):
    """Evidence used to score OEM or analog applicability."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    evidence_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    position_id: str = Field(index=True)
    candidate_type: str  # OEM|ANALOG
    candidate_id: str = Field(index=True)
    evidence_type: str  # vin_oem_catalog|official_brand_catalog|tecdoc|cross_reference|spec_match
    source: str
    source_url: Optional[str] = None
    score_points: int = Field(default=0)
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    evidence_ref: Optional[str] = None
    evidence_hash: Optional[str] = None
    readability_status: str = Field(default="unknown")  # readable|partial|unreadable|unknown
    completeness_status: str = Field(default="partial")  # complete|partial|missing
    freshness_status: str = Field(default="current")  # current|stale|unknown
    created_by: str = Field(default="agent")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractExport(SQLModel, table=True):
    """Versioned output document; created only after approved evidence exists."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    export_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    contract_ref: str = Field(index=True)
    template_name: str
    document_version: str = Field(default="v1.0")
    registry_hash: Optional[str] = None
    diff_status: str = Field(default="validated")  # validated|mismatch|manual_override
    content_json: str
    internal_registry_path: Optional[str] = None
    internal_registry_sha256: Optional[str] = None
    client_document_path: Optional[str] = None
    client_document_sha256: Optional[str] = None
    created_by: str = Field(default="system")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractAuditRun(SQLModel, table=True):
    """Contract-control audit run for one request; produces requirements, gaps and gates."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    audit_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    contract_ref: str = Field(index=True)
    input_documents_json: str = Field(default="[]")
    existing_elements_json: str = Field(default="[]")
    status: str = Field(default="completed")  # required|in_progress|completed|blocked
    unresolved_critical_count: int = Field(default=0)
    created_by: str = Field(default="system")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class ContractWorkflowState(SQLModel, table=True):
    """Current contract-specific Workflow v2 stage, separate from the legacy request state."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    workflow_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True, unique=True)
    contract_ref: str = Field(index=True)
    current_stage: str = Field(default="00_CONTRACT_AUDIT_REQUIRED", index=True)
    current_stage_index: int = Field(default=0)
    blocked: bool = Field(default=True)
    blocking_code: Optional[str] = None
    blocking_reason: Optional[str] = None
    updated_by: str = Field(default="system")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ContractWorkflowEvent(SQLModel, table=True):
    """Append-only history of Workflow v2 stage changes and rejected transitions."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    workflow_event_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    from_stage: Optional[str] = None
    to_stage: str
    actor_id: str = Field(default="system")
    reason: str
    allowed: bool = Field(default=True)
    violations_json: str = Field(default="[]")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractRequirement(SQLModel, table=True):
    """Extracted or baseline contract requirement with traceable implementation coverage."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    requirement_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    contract_ref: str = Field(index=True)
    source: str
    clause: Optional[str] = None
    page: Optional[int] = None
    summary: str
    exact_fragment: Optional[str] = None
    requirement_type: str  # CONTRACTUAL_MUST|CONTRACTUAL_CONDITIONAL|INTERNAL_CONTROL|INFERRED|UNRESOLVED
    object_scope: str
    applies_when: Optional[str] = None
    responsible: str = Field(default="agent")
    required_evidence: str = Field(default="audit_event")
    criticality: str = Field(default="High")  # Critical|High|Medium|Low
    coverage_status: str = Field(default="Missing")  # Covered|Partial|Missing|Conflict
    implementation_element: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RequirementCoverage(SQLModel, table=True):
    """Coverage matrix row. A field alone is not enough: data, checks, evidence, owner, gate and test are tracked."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    coverage_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    requirement_id: str = Field(index=True)
    has_data: bool = Field(default=False)
    has_check: bool = Field(default=False)
    has_evidence: bool = Field(default=False)
    has_responsible: bool = Field(default=False)
    has_workflow_gate: bool = Field(default=False)
    has_test: bool = Field(default=False)
    export_covered: bool = Field(default=False)
    status: str = Field(default="Missing")  # Covered|Partial|Missing|Conflict
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractGap(SQLModel, table=True):
    """Gap analysis record created from the contract audit and implementation coverage."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    gap_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    requirement_id: Optional[str] = Field(default=None, index=True)
    category: str
    description: str
    source: str
    risk: str
    probability: str = Field(default="Medium")
    impact: str = Field(default="High")
    priority: str = Field(default="P1")
    proposed_change: str
    affected_tables: str = Field(default="")
    affected_workflow_statuses: str = Field(default="")
    required_tests: str = Field(default="")
    closure_criteria: str
    status: str = Field(default="open")  # open|accepted|closed
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class AdaptationDecisionRecord(SQLModel, table=True):
    """ADR proving why the plan changed after audit or gap analysis."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    adr_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    problem: str
    requirement_id: Optional[str] = Field(default=None, index=True)
    current_state: str
    decision: str
    rationale: str
    alternatives: str = Field(default="")
    affected_components: str = Field(default="")
    change_risk: str = Field(default="Medium")
    migration: str = Field(default="")
    tests: str = Field(default="")
    rollback: str = Field(default="")
    created_by: str = Field(default="system")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractExceptionRecord(SQLModel, table=True):
    """Controlled exception with evidence, owner, retry policy and export impact."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    exception_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    position_id: Optional[str] = Field(default=None, index=True)
    code: str = Field(index=True)
    severity: str = Field(default="BLOCKING")
    description: str
    evidence_ref: Optional[str] = None
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    owner: str = Field(default="operator")
    escalation_due_at: Optional[datetime] = None
    resolution: Optional[str] = None
    export_impact: str = Field(default="blocks_export")
    status: str = Field(default="open")  # open|resolved|accepted
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class ClientApproval(SQLModel, table=True):
    """Documented customer approval. Purchase authorization depends on this record."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    approval_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    export_id: str = Field(index=True)
    approved_by: str
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    evidence_ref: Optional[str] = None
    comment: Optional[str] = None


class PurchaseAuthorization(SQLModel, table=True):
    """Explicit lock release for procurement after customer approval."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    authorization_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    approval_id: str = Field(index=True)
    authorized_by: str
    authorized_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="authorized")
    comment: Optional[str] = None


class ContractPurchaseRecord(SQLModel, table=True):
    """Proof that procurement executed after explicit purchase authorization."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    purchase_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    authorization_id: str = Field(index=True)
    supplier_ref: str
    ordered_by: str
    ordered_at: datetime = Field(default_factory=datetime.utcnow)
    amount_total: float = Field(default=0.0)
    currency: str = Field(default="RUB")
    evidence_ref: Optional[str] = None
    status: str = Field(default="purchased")
    comment: Optional[str] = None


class ContractReceiptVerification(SQLModel, table=True):
    """Receipt verification locks actual delivery evidence to a purchase."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    receipt_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    purchase_id: str = Field(index=True)
    verified_by: str
    verified_at: datetime = Field(default_factory=datetime.utcnow)
    evidence_ref: str
    received_quantity: int = Field(default=0)
    status: str = Field(default="verified")
    discrepancy_note: Optional[str] = None


class ContractArchiveRecord(SQLModel, table=True):
    """Final immutable archive pointer for the completed contract execution package."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    archive_id: str = Field(index=True, unique=True)
    request_id: str = Field(index=True)
    receipt_id: str = Field(index=True)
    archived_by: str
    archived_at: datetime = Field(default_factory=datetime.utcnow)
    archive_ref: str
    registry_hash: Optional[str] = None
    status: str = Field(default="archived")
    comment: Optional[str] = None
