from .policy_engine import PolicyEngine
from ..model.model_router import ModelRouter

class AgentOrchestrator:
    def __init__(self):
        self.policy = PolicyEngine()
        self.router = ModelRouter()

    def run_request_pipeline(self, request_id: str) -> dict:
        # Skeleton: replace each stage with real agent/tool implementation.
        trace = []
        trace.append({"stage": "create_run", "request_id": request_id})
        trace.append({"stage": "parse", "model": self.router.route("request_parsing")})
        trace.append({"stage": "validate", "gate": "request_schema_gate"})
        trace.append({"stage": "supplier_query"})
        trace.append({"stage": "matching"})
        trace.append({"stage": "ranking"})
        trace.append({"stage": "risk_review"})
        trace.append({"stage": "admin_review_required"})
        return {"request_id": request_id, "status": "ADMIN_REVIEW", "trace": trace}
