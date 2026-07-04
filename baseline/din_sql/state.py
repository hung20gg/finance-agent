from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List


@dataclass
class DINSQLAgentState:
    agent_type: str = "din_sql"
    current_time: str = field(default_factory=lambda: date.today().isoformat())
    user_request: str = ""
    question: str = ""
    db_id: str = "finance"
    messages: List[Dict[str, Any]] = field(default_factory=list)
    trace_messages: List[Dict[str, Any]] = field(default_factory=list)
    num_tools_calls: int = 0

    schema_context: str = ""
    examples_text: str = ""
    schema_links: List[str] = field(default_factory=list)
    query_class: str = ""
    join_tables: List[str] = field(default_factory=list)
    sub_questions: List[str] = field(default_factory=list)
    intermediate_representation: str = ""
    subquery_sqls: Dict[str, str] = field(default_factory=dict)

    generated_sql: str = ""
    corrected_sql: str = ""
    sql_query: str = ""
    sql_result: str = ""
    final_answer: str = ""

    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
