from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1] / "04_BACKEND_CONTRACTS"))
from tools.tool_permission_guard import ToolPermissionGuard


def test_forbidden_tool_blocked():
    guard = ToolPermissionGuard()
    assert not guard.check("invoice_draft_agent", "erp_submit_invoice")


def test_allowed_tool_passes():
    guard = ToolPermissionGuard()
    assert guard.check("invoice_draft_agent", "erp_create_invoice_draft")
