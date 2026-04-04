from typing import Annotated, List, TypedDict, Dict, Any
from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import date

@dataclass
class AgentState:
    """The state of the agent."""
    current_time: Annotated[str, "The current date and time in ISO 8601 format"] = field(
        default_factory=lambda: date.today().isoformat()
    )
    user_request: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    number_of_steps: int = 0
    num_tools_calls: int = 0