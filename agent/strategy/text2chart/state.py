import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from core.state import AgentState

@dataclass
class EvaluationFeedback:
    score: float
    critique: str

@dataclass
class Text2ChartAgentState(AgentState):
    current_iteration: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    chart_generation: str = ''
    chart_evaluation: Optional[EvaluationFeedback] = field(default=None)
    chart_rendering: str = ''
