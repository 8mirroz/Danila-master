from .base_agent import BaseAgent, AgentResult

class OfferRankerAgent(BaseAgent):
    name = "offerrankeragent"

    def run(self, payload):
        # TODO: implement real logic, schema validation, trace and error handling.
        return AgentResult(ok=True, output={"agent": self.name, "status": "stub"}, confidence=0.5)
