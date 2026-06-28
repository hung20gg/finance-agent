from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List


@dataclass
class ChessSQLAgentState:
    agent_type: str = "chess_sql"
    current_time: str = field(default_factory=lambda: date.today().isoformat())
    user_request: str = ""
    question: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    trace_messages: List[Dict[str, Any]] = field(default_factory=list)
    current_iteration: int = 0
    num_tools_calls: int = 0

    keywords: List[str] = field(default_factory=list)
    retrieved_entities: Dict[str, Any] = field(default_factory=dict)
    retrieved_context: str = ""

    selected_tables: List[str] = field(default_factory=list)
    selected_columns: Dict[str, List[str]] = field(default_factory=dict)
    schema_metadata: Dict[str, str] = field(default_factory=dict)
    selected_schema: str = ""

    candidate_sqls: List[str] = field(default_factory=list)
    unit_tests: List[str] = field(default_factory=list)
    sql_query: str = ""
    sql_result: str = ""
    final_answer: str = ""
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
