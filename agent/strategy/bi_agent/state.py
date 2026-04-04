import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

from core.state import AgentState
from .. import Text2SQLAgentState, Text2ChartAgentState



@dataclass
class BIAgentState(AgentState):
    current_iteration: int = 0
    text2sql_state: Text2SQLAgentState = field(default_factory=Text2SQLAgentState)
    text2chart_state: Text2ChartAgentState = field(default_factory=Text2ChartAgentState)
    # messages inherited from AgentState - override default value
    messages: List[Dict[str, Any]] = field(default_factory=list)