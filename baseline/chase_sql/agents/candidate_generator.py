from typing import Any, Dict, List

from baseline.chess_sql.agents.base import ChessSubAgent
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.utils import code_block_extractor, load_baseline_prompt, render_current_time_prompt


# CHASE-SQL uses several diverse generators so the selection agent has genuinely
# different candidates to choose from. Each entry is (strategy_name, prompt_file).
CHASE_STRATEGIES = [
    ("divide_and_conquer", "generate_divide_conquer.md"),
    ("query_plan", "generate_query_plan.md"),
]


class ChaseCandidateGenerator(ChessSubAgent):
    """CHASE-SQL candidate generator.

    Reuses the CHESS sub-agent LLM plumbing (token counting, trace messages) and
    produces one candidate SQL per prompting strategy. It also exposes a query
    fixer used when a candidate fails or returns an empty result.
    """

    def __init__(self, llm, current_time: str) -> None:
        super().__init__(
            llm=llm,
            current_time=current_time,
            name="CHASE Candidate Generator",
            task="generate diverse candidate SQL queries with different reasoning strategies",
        )
        self.strategy_prompts = {
            name: load_baseline_prompt("chase_sql", prompt_file)
            for name, prompt_file in CHASE_STRATEGIES
        }
        self.fix_prompt = load_baseline_prompt("chase_sql", "fix_query.md")

    def _user_prompt(self, state: ChessSQLAgentState) -> str:
        return (
            f"Question:\n{state.user_request or state.question}\n\n"
            f"Retrieved context:\n{state.retrieved_context}\n\n"
            f"Selected schema:\n{state.selected_schema}"
        )

    async def generate_all(self, state: ChessSQLAgentState) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for name, _ in CHASE_STRATEGIES:
            system_prompt = render_current_time_prompt(self.strategy_prompts[name], state.current_time)
            response = await self.ainvoke(
                system_prompt,
                self._user_prompt(state),
                chess_state=state,
                trace_agent=f"CHASE Candidate Generator.{name}",
            )
            sql = code_block_extractor(response)
            if sql:
                candidates.append({"strategy": name, "sql": sql, "result": ""})

        state.candidate_sqls = [c["sql"] for c in candidates]
        # ChaseSQLAgentState carries candidate_records; guard for plain CHESS state.
        if hasattr(state, "candidate_records"):
            state.candidate_records = candidates
        return candidates

    async def fix(self, state: ChessSQLAgentState, sql: str, result: str) -> str:
        system_prompt = render_current_time_prompt(self.fix_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Selected schema:\n{state.selected_schema}\n\n"
                f"SQL:\n```sql\n{sql}\n```\n\n"
                f"Execution result (error or empty):\n{result}"
            ),
            chess_state=state,
            trace_agent="CHASE Candidate Generator.fix",
        )
        return code_block_extractor(response)
