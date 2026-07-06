from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from agent.core.logger import logger
from baseline.chase_sql.agents.candidate_generator import ChaseCandidateGenerator
from baseline.chase_sql.agents.selection_agent import ChaseSelectionAgent
from baseline.chase_sql.state import ChaseSQLAgentState
from baseline.chess_sql.agent import ChessSQLAgent
from baseline.utils import is_failed_or_empty_result


class ChaseSQLAgentConfig(BaseModel):
    agent_type: str = "chase_sql"
    model_name: str
    urls: Optional[List[str]] = None
    streaming: bool = False
    max_fix_attempts: int = 1


class ChaseSQLAgent(ChessSQLAgent):
    """CHASE-SQL baseline.

    Inherits the CHESS-SQL infrastructure (information retriever, schema
    selector, execution helpers, final formatter) and swaps the single
    candidate generator plus unit tester for CHASE-SQL's multi-strategy
    candidate generation and pairwise selection.

    Design note (compile time vs inference time): the CHESS information
    retriever and schema selector are reused as-is here, so schema and value
    resolution still happen per query. In our finance setting these can instead
    be prepared once at build ("compile") time from the fixed database schema
    and the Fuzzy Search metadata, then injected into the state before
    ``candidate generation``; the graph below is written so that only
    ``generate_candidates`` onward is CHASE specific.
    """

    async def generate_candidates(self, state: ChaseSQLAgentState) -> Dict[str, Any]:
        logger.info("CHASE-SQL stage started: generate_candidates")
        generator = ChaseCandidateGenerator(self.llm, state.current_time)
        await generator.generate_all(state)
        logger.info(
            "CHASE-SQL generated %d candidate(s)", len(state.candidate_records)
        )
        return {
            "candidate_sqls": state.candidate_sqls,
            "candidate_records": state.candidate_records,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def execute_candidates(self, state: ChaseSQLAgentState) -> Dict[str, Any]:
        logger.info("CHASE-SQL stage started: execute_candidates")
        generator = ChaseCandidateGenerator(self.llm, state.current_time)
        for record in state.candidate_records:
            result = await self.mcp_tools.execute_code(record["sql"])
            attempts = 0
            while is_failed_or_empty_result(result) and attempts < self.config.max_fix_attempts:
                fixed_sql = await generator.fix(state, record["sql"], result)
                if fixed_sql and fixed_sql != record["sql"]:
                    record["sql"] = fixed_sql
                    result = await self.mcp_tools.execute_code(fixed_sql)
                attempts += 1
            record["result"] = result
            self._append_execute_messages(state, record["sql"], result)
        logger.info("CHASE-SQL stage finished: execute_candidates")
        return {
            "candidate_records": state.candidate_records,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            "num_tools_calls": state.num_tools_calls,
            **self._token_usage_update(state),
        }

    async def select_candidate(self, state: ChaseSQLAgentState) -> Dict[str, Any]:
        logger.info("CHASE-SQL stage started: select_candidate")
        records = state.candidate_records
        if not records:
            state.sql_query = ""
            state.sql_result = ""
            return {
                "sql_query": state.sql_query,
                "sql_result": state.sql_result,
                "trace_messages": state.trace_messages,
                **self._token_usage_update(state),
            }

        # prefer candidates that executed successfully; fall back to all
        valid = [r for r in records if not is_failed_or_empty_result(r["result"])] or records

        if len(valid) == 1:
            best = valid[0]
            state.selected_index = records.index(best)
            state.selection_rationale = "single valid candidate"
        else:
            selector = ChaseSelectionAgent(self.llm, state.current_time)
            best = valid[0]
            reasons: List[str] = []
            for challenger in valid[1:]:
                winner_idx, reason = await selector.compare(state, best, challenger)
                if winner_idx == 1:
                    best = challenger
                reasons.append(reason)
            state.selected_index = records.index(best)
            state.selection_rationale = " | ".join(r for r in reasons if r)

        state.sql_query = best["sql"]
        state.sql_result = best["result"]
        logger.info("CHASE-SQL selected candidate index=%d", state.selected_index)
        return {
            "sql_query": state.sql_query,
            "sql_result": state.sql_result,
            "selected_index": state.selected_index,
            "selection_rationale": state.selection_rationale,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(ChaseSQLAgentState)
        workflow.add_node("information_retriever", self.information_retriever)
        workflow.add_node("schema_selector", self.schema_selector)
        workflow.add_node("generate_candidates", self.generate_candidates)
        workflow.add_node("execute_candidates", self.execute_candidates)
        workflow.add_node("select_candidate", self.select_candidate)
        workflow.add_node("final_formatter", self.final_formatter)

        workflow.set_entry_point("information_retriever")
        workflow.add_edge("information_retriever", "schema_selector")
        workflow.add_edge("schema_selector", "generate_candidates")
        workflow.add_edge("generate_candidates", "execute_candidates")
        workflow.add_edge("execute_candidates", "select_candidate")
        workflow.add_edge("select_candidate", "final_formatter")
        workflow.add_edge("final_formatter", END)
        return workflow.compile()

    async def ainvoke(self, state: ChaseSQLAgentState) -> ChaseSQLAgentState:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Starting baseline CHASE-SQL invocation with thread ID: {self.session_id}")
        result = await self.graph.ainvoke(state)
        if result is None:
            raise ValueError("Workflow execution returned None.")
        if isinstance(result, ChaseSQLAgentState):
            return result
        return ChaseSQLAgentState(**result)
