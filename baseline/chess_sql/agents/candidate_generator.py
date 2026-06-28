from typing import List

from baseline.chess_sql.agents.base import ChessSubAgent
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.utils import code_block_extractor, load_baseline_prompt, render_current_time_prompt


class CandidateGenerator(ChessSubAgent):
    """CHESS candidate generator: generate candidate SQL and revise it."""

    def __init__(self, llm, current_time: str) -> None:
        super().__init__(
            llm=llm,
            current_time=current_time,
            name="Candidate Generator",
            task="generate candidate SQL and revise it when execution feedback indicates a problem",
        )
        self.generate_candidate_prompt = load_baseline_prompt("chess_sql", "generate_candidate.md")
        self.revise_prompt = load_baseline_prompt("chess_sql", "revise.md")
        self.tool_fns = {
            "generate_candidate": self.generate_candidate,
            "revise": self.revise,
        }
        self.tool_descriptions = {
            "generate_candidate": "Generate a PostgreSQL candidate query from selected schema and retrieved context.",
            "revise": "Revise the current SQL using execution feedback.",
        }

    def is_complete(self, state: ChessSQLAgentState) -> bool:
        if not state.sql_query:
            return False
        if state.sql_result and "[FAILED]" in state.sql_result:
            return False
        return True

    async def generate_candidate(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.generate_candidate_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Retrieved context:\n{state.retrieved_context}\n\n"
                f"Selected schema:\n{state.selected_schema}"
            ),
            chess_state=state,
            trace_agent="Candidate Generator.generate_candidate",
        )
        sql = code_block_extractor(response)
        state.candidate_sqls = [sql] if sql else []
        state.sql_query = state.candidate_sqls[0] if state.candidate_sqls else ""
        return f"generate_candidate: {state.sql_query}"

    async def revise(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.revise_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Selected schema:\n{state.selected_schema}\n\n"
                f"Current SQL:\n```sql\n{state.sql_query}\n```\n\n"
                f"Execution result:\n{state.sql_result}"
            ),
            chess_state=state,
            trace_agent="Candidate Generator.revise",
        )
        revised_sql = code_block_extractor(response)
        if revised_sql:
            state.sql_query = revised_sql
            state.candidate_sqls.append(revised_sql)
        return f"revise: {state.sql_query}"
