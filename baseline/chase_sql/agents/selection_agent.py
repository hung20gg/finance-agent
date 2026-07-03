from typing import Any, Dict, Tuple

from baseline.chess_sql.agents.base import ChessSubAgent
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.utils import extract_json_object, load_baseline_prompt, render_current_time_prompt


class ChaseSelectionAgent(ChessSubAgent):
    """CHASE-SQL selection agent (prompt based, no trained selector).

    The original CHASE-SQL trains a binary selection model. To keep the whole
    pipeline prompt based and training free, we implement the selection as an
    LLM pairwise comparison and run a simple tournament over the candidates.
    """

    def __init__(self, llm, current_time: str) -> None:
        super().__init__(
            llm=llm,
            current_time=current_time,
            name="CHASE Selection Agent",
            task="pick the SQL candidate that best answers the question",
        )
        self.select_prompt = load_baseline_prompt("chase_sql", "select_candidate.md")

    async def compare(
        self,
        state: ChessSQLAgentState,
        candidate_a: Dict[str, Any],
        candidate_b: Dict[str, Any],
    ) -> Tuple[int, str]:
        """Return (0 if A wins else 1, reason)."""
        system_prompt = render_current_time_prompt(self.select_prompt, state.current_time)
        user_prompt = (
            f"Question:\n{state.user_request or state.question}\n\n"
            f"Selected schema:\n{state.selected_schema}\n\n"
            f"Candidate A (strategy={candidate_a.get('strategy')}):\n"
            f"```sql\n{candidate_a.get('sql')}\n```\n"
            f"Execution result A:\n{candidate_a.get('result')}\n\n"
            f"Candidate B (strategy={candidate_b.get('strategy')}):\n"
            f"```sql\n{candidate_b.get('sql')}\n```\n"
            f"Execution result B:\n{candidate_b.get('result')}\n\n"
            'Reply with a JSON object: {"winner": "A" or "B", "reason": "..."}'
        )
        response = await self.ainvoke(
            system_prompt,
            user_prompt,
            chess_state=state,
            trace_agent="CHASE Selection Agent.compare",
        )
        parsed = extract_json_object(response) or {}
        winner = str(parsed.get("winner", "A")).strip().upper()
        reason = str(parsed.get("reason", ""))
        return (1 if winner == "B" else 0, reason)
