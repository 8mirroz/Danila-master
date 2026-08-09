"""Engines — domain-specific automation logic with honest status reporting.

Public functions always include:
- implemented: bool
- status: ok | partial | not_wired | error
- reason: str | None when not fully successful

Root policy lives in package-root policy_engine.py (not engines/policy_engine.py).
Production jobs mostly use inline logic; these engines are reusable adapters.
"""
from __future__ import annotations

from app.automation.engines.vin_query_engine import decode_vin
from app.automation.engines.notification_engine import notify
from app.automation.engines.erp_connector_engine import sync_erp
from app.automation.engines.escalation_engine import escalate
from app.automation.engines.po_generation_engine import generate_po
from app.automation.engines.policy_engine import check_policy
from app.automation.engines.quote_evaluation_engine import score_quotes
from app.automation.engines.quote_score_engine import score_quotes as score_quotes_alias
from app.automation.engines.supplier_discovery_engine import find_suppliers
from app.automation.engines.decision_engine import decide
from app.automation.engines.erp_hub_engine import route_erp
from app.automation.engines.vendor_query_engine import query_vendor

# Avoid unused-import linter on alias re-export
_ = score_quotes_alias

ENGINE_REGISTRY = {
    "vin_query": {
        "module": "app.automation.engines.vin_query_engine",
        "entry": "decode_vin",
        "wired": True,
        "description": "Offline WMI VIN decode (pii.decode_vin_offline)",
    },
    "notification": {
        "module": "app.automation.engines.notification_engine",
        "entry": "notify",
        "wired": True,
        "description": "OutboundMessage outbox enqueue when session provided",
    },
    "erp_connector": {
        "module": "app.automation.engines.erp_connector_engine",
        "entry": "sync_erp",
        "wired": True,
        "description": "Thin adapter to erp_adapter.sync_invoice_draft when session+request_id",
    },
    "escalation": {
        "module": "app.automation.engines.escalation_engine",
        "entry": "escalate",
        "wired": True,
        "description": "Appends STATE_CHANGED escalated event when session+request_id",
    },
    "po_generation": {
        "module": "app.automation.engines.po_generation_engine",
        "entry": "generate_po",
        "wired": True,
        "description": "Local PO draft id only (not sent to ERP)",
    },
    "policy": {
        "module": "app.automation.engines.policy_engine",
        "entry": "check_policy",
        "wired": True,
        "description": "Simple field checks or delegate to root policy_engine",
    },
    "quote_evaluation": {
        "module": "app.automation.engines.quote_evaluation_engine",
        "entry": "score_quotes",
        "wired": True,
        "description": "Local quote ranking by price/score",
    },
    "quote_score": {
        "module": "app.automation.engines.quote_score_engine",
        "entry": "score_quotes",
        "wired": True,
        "description": "Alias of quote_evaluation.score_quotes",
    },
    "supplier_discovery": {
        "module": "app.automation.engines.supplier_discovery_engine",
        "entry": "find_suppliers",
        "wired": True,
        "description": "DB Supplier query when session provided; else not_wired",
    },
    "decision": {
        "module": "app.automation.engines.decision_engine",
        "entry": "decide",
        "wired": True,
        "description": "Score/threshold approve vs review",
    },
    "erp_hub": {
        "module": "app.automation.engines.erp_hub_engine",
        "entry": "route_erp",
        "wired": True,
        "description": "Routes to erp_connector when session+request_id; else not_wired",
    },
    "vendor_query": {
        "module": "app.automation.engines.vendor_query_engine",
        "entry": "query_vendor",
        "wired": True,
        "description": "DB catalog match via matcher when session+query; live scrape stays in crawler",
    },
}

__all__ = [
    "decode_vin",
    "notify",
    "sync_erp",
    "escalate",
    "generate_po",
    "check_policy",
    "score_quotes",
    "find_suppliers",
    "decide",
    "route_erp",
    "query_vendor",
    "ENGINE_REGISTRY",
]
