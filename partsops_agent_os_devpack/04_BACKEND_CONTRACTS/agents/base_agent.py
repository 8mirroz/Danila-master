from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class AgentResult:
    ok: bool
    output: Dict[str, Any]
    confidence: float = 0.0
    errors: List[str] = field(default_factory=list)

class BaseAgent:
    name = "base_agent"
    allowed_tools = []
    forbidden_tools = []

    def run(self, payload: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError
