from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AgentResult:
    ok: bool
    output: Dict[str, Any]
    confidence: float = 0.0
    errors: List[str] = field(default_factory=list)


class BaseAgent:
    """Devpack scaffold base.

    These agents are **contract skeletons only**. Production logic lives in
    `partsops-ai-manager/app/agents/*`. Scaffold agents set implemented=False
    and must not report ok=True success.
    """

    name = "base_agent"
    allowed_tools: List[str] = []
    forbidden_tools: List[str] = []
    implemented: bool = False

    def run(self, payload: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError
