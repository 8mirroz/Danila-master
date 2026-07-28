"""VIN decoding engine — offline WMI decoder (no external HTTP)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def decode_vin(vin: str) -> dict:
    """Decode VIN via offline WMI map. Never reports silent 'stub' when offline works."""
    from pii import decode_vin_offline

    if not vin or not str(vin).strip():
        return {
            "vin": vin,
            "decoded": False,
            "reason": "empty_vin",
            "partial": True,
            "source": "offline_wmi",
            "implemented": True,
            "status": "partial",
            "ok": False,
        }

    cleaned = str(vin).strip().upper()
    raw = decode_vin_offline(cleaned)

    make = raw.get("make")
    model = raw.get("model")
    year = raw.get("year")
    validity = raw.get("vin_validity")

    is_valid = validity == "valid"
    has_real_make = make not in (None, "Unknown")
    # WMI-only (make known, model unknown) is a useful partial decode.
    partial = (not is_valid) or (make == "Unknown") or (model == "Unknown") or (not has_real_make)

    if is_valid:
        reason = None
    else:
        reason = "invalid_or_unknown"

    status = "ok" if is_valid and not partial else ("partial" if has_real_make else "error")
    if is_valid and partial:
        status = "partial"
    elif is_valid:
        status = "ok"

    return {
        "vin": cleaned,
        "decoded": is_valid,
        "partial": partial,
        "make": make,
        "model": model,
        "year": year,
        "vin_validity": validity,
        "reason": reason,
        "source": "offline_wmi",
        "implemented": True,
        "status": status,
        "ok": bool(is_valid or has_real_make),
    }
