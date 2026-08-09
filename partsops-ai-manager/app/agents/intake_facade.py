"""Single public entry for text → structured intake parse.

API routes, RequestService, IntakeAgent and orchestrators should import
``parse_intake_text`` from here (or re-exported via ``app.agents``) instead of
reaching into ``agents`` shim / ``legacy_intake_pipeline`` directly.

The underlying graph remains ``legacy_intake_pipeline.process_intake_request``
until a full graph rewrite; this facade freezes the call contract.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def parse_intake_text(
    text: str,
    *,
    priority: str = "normal",
    vehicle_context: Optional[Dict[str, Any]] = None,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Parse free-text RFQ into structured intake result (parts, vehicle, gates)."""
    from app.agents.legacy_intake_pipeline import process_intake_request

    return process_intake_request(
        text,
        priority=priority,
        vehicle_context=vehicle_context,
        tenant_id=tenant_id,
    )


# Backward-compatible alias used by tests that still name the legacy function
process_intake_request = parse_intake_text
