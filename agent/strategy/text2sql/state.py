import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

from core.state import AgentState

@dataclass
class Text2SQLAgentState(AgentState):
    current_iteration: int = 0
    query_mode: str = 'any'  # can be 'entity', 'tuple', or 'any'
    # messages inherited from AgentState - override default value
    messages: List[Dict[str, Any]] = field(default_factory=list)
