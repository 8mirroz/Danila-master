"""
PartsOps AI Manager v3 — Agent Graph (legacy compatibility shim).

Original intake graph and helpers were moved to
``app.agents.legacy_intake_pipeline``; this file re-exports the same symbols
so existing ``from agents import ...`` call sites keep working without
regression.  New code should import from ``app.agents.*`` instead.
"""
from __future__ import annotations

import importlib
from typing import Any

_LEGACY_ATTRS: set[str] = {
    "IntakeState",
    "intake_classifier_node",
    "vin_inspector_node",
    "parts_extractor_node",
    "supplier_scatter_gather_node",
    "pricing_guard_node",
    "gates_checker_node",
    "process_intake_request",
    "intake_app",
    "full_pipeline_graph",
}


def __getattr__(name: str) -> Any:
    if name in _LEGACY_ATTRS:
        mod = importlib.import_module("app.agents.legacy_intake_pipeline")
        value = getattr(mod, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals().keys()) | _LEGACY_ATTRS)
