FORBIDDEN_TOOLS = {
    "erp_submit_invoice",
    "erp_delete_invoice",
    "erp_change_payment_status",
    "send_invoice_without_approval",
    "disable_audit_log",
}

ROLE_ALLOWED_TOOLS = {
    "request_parser_agent": {"llm_parse", "document_parse"},
    "supplier_query_agent": {"supplier_api_query", "supplier_csv_import", "supplier_email_parse"},
    "invoice_draft_agent": {"erp_create_invoice_draft", "erp_read_customer", "erp_read_items"},
    "debug_agent": {"trace_read", "replay_read_only", "eval_case_create"},
}

class ToolPermissionGuard:
    def check(self, agent_name: str, tool_name: str) -> bool:
        if tool_name in FORBIDDEN_TOOLS:
            return False
        return tool_name in ROLE_ALLOWED_TOOLS.get(agent_name, set())
