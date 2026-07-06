from dataclasses import dataclass, field
from typing import Any, Dict, List

from baseline.chess_sql.state import ChessSQLAgentState


@dataclass
class ChaseSQLAgentState(ChessSQLAgentState):
    """CHASE-SQL state.

    Inherits the full CHESS-SQL state (information retrieval, schema selection,
    token counters, message traces) and adds the CHASE specific fields for
    multi-strategy candidate generation and pairwise selection.
    """

    agent_type: str = "chase_sql"

    # one record per generated candidate: {"strategy": str, "sql": str, "result": str}
    candidate_records: List[Dict[str, Any]] = field(default_factory=list)
    selected_index: int = -1
    selection_rationale: str = ""
