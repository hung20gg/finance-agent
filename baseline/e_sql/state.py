from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List


@dataclass
class ESQLAgentState:
    """E-SQL state.

    E-SQL enriches the question with candidate predicates grounded in the
    database (value linking) before generating and refining the final SQL.
    Kept structurally close to the vanilla baseline so it stays compatible
    with ``scripts/run/run_evaluation.py``.
    """

    agent_type: str = "e_sql"
    current_time: str = field(default_factory=lambda: date.today().isoformat())
    user_request: str = ""
    question: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    trace_messages: List[Dict[str, Any]] = field(default_factory=list)
    num_tools_calls: int = 0

    # E-SQL specific
    candidate_predicates: List[str] = field(default_factory=list)
    probe_results: str = ""
    enriched_question: str = ""
    refine_iteration: int = 0

    sql_query: str = ""
    sql_result: str = ""
    final_answer: str = ""
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
