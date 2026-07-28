from .base_agent import BaseAgent, AgentResult


class CatalogMatcherAgent(BaseAgent):
    name = "catalog_matcher_agent"
    # Scaffold only — not wired to partsops-ai-manager runtime.
    implemented = False

    def run(self, payload):
        return AgentResult(
            ok=False,
            output={
                "agent": self.name,
                "status": "not_implemented",
                "implemented": False,
                "runtime": "devpack_scaffold",
                "hint": "Use partsops-ai-manager app/agents/* for production logic",
            },
            confidence=0.0,
            errors=["Agent is scaffold-only (devpack); not production runtime"],
        )
