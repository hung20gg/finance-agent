from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List


@dataclass
class MacSQLAgentState:
    agent_type: str = "mac_sql"
    current_time: str = field(default_factory=lambda: date.today().isoformat())
    user_request: str = ""
    question: str = ""
    evidence: str = ""
    db_id: str = "finance"
    messages: List[Dict[str, Any]] = field(default_factory=list)
    trace_messages: List[Dict[str, Any]] = field(default_factory=list)

    extracted_schema: Dict[str, Any] = field(default_factory=dict)
    chosen_db_schem_dict: Dict[str, Any] = field(default_factory=dict)
    desc_str: str = ""
    fk_str: str = ""
    qa_pairs: List[Any] = field(default_factory=list)
    execution_result: List[Dict[str, Any]] = field(default_factory=list)
    mac_sql_message: Dict[str, Any] = field(default_factory=dict)

    sql_query: str = ""
    sql_result: str = ""
    final_answer: str = ""
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
