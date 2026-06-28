import json
from copy import deepcopy
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from agent.core.logger import logger
from agent.core.mcp_client import MCPClient
from agent.llm import get_llm_wrapper
from baseline.chess_sql.agents.candidate_generator import CandidateGenerator
from baseline.chess_sql.agents.information_retriever import InformationRetriever
from baseline.chess_sql.agents.schema_selector import SchemaSelector
from baseline.chess_sql.agents.unit_tester import UnitTester
from baseline.chess_sql.mcp_tools import ChessMCPTools
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.utils import extract_entity_answer, is_failed_or_empty_result, load_baseline_prompt


FINAL_FORMATTER_PROMPT = load_baseline_prompt("chess_sql", "final_formatter.md")


class ChessSQLAgentConfig(BaseModel):
    agent_type: str = "chess_sql"
    model_name: str
    urls: Optional[List[str]] = None
    streaming: bool = False
    max_revision_attempts: int = 1


class ChessSQLAgent:
    def __init__(self, config: ChessSQLAgentConfig) -> None:
        logger.info(f"Initializing baseline CHESS-SQL agent with config: {config}")
        self.config = config
        self.llm = get_llm_wrapper(config.model_name)
        self.mcp_client = MCPClient(config.urls)
        self.mcp_tools = ChessMCPTools(self.mcp_client)
        self._initialized = False
        self.session_id = str(uuid4())
        self.graph = self.build_graph()

    async def initialize(self) -> None:
        if not self._initialized:
            await self.mcp_client.initialize()
            self._initialized = True

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def _get_question_text(self, state: ChessSQLAgentState) -> str:
        return state.user_request or state.question

    def _append_execute_messages(self, state: ChessSQLAgentState, query: str, result: str) -> None:
        tool_call_id = f"call_{uuid4().hex}"
        assistant_message = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "execute_code",
                        "arguments": json.dumps({"query": query}, ensure_ascii=False),
                    },
                }
            ],
        }
        tool_message = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }
        state.messages.append(assistant_message)
        state.messages.append(tool_message)
        self._append_trace_message(state, assistant_message, "CHESS-SQL.execute_sql")
        self._append_trace_message(state, tool_message, "CHESS-SQL.execute_sql")
        state.num_tools_calls += 1

    def _append_trace_message(
        self,
        state: ChessSQLAgentState,
        message: Dict[str, Any],
        agent_name: str,
    ) -> None:
        traced_message = deepcopy(message)
        traced_message["agent"] = agent_name
        state.trace_messages.append(traced_message)

    def _token_usage_update(self, state: ChessSQLAgentState) -> Dict[str, int]:
        return {
            "total_tokens": state.total_tokens,
            "total_prompt_tokens": state.total_prompt_tokens,
            "total_output_tokens": state.total_output_tokens,
        }

    async def information_retriever(self, state: ChessSQLAgentState) -> Dict[str, Any]:
        logger.info("CHESS-SQL stage started: information_retriever")
        question_text = self._get_question_text(state)
        if not question_text:
            raise ValueError("ChessSQLAgentState.user_request is empty.")

        state.messages = [
            {
                "role": "system",
                "content": "CHESS-SQL baseline. Use MCP only through get_table_metadata and execute_code.",
            },
            {"role": "user", "content": question_text},
        ]
        for message in state.messages:
            self._append_trace_message(state, message, "CHESS-SQL")

        agent = InformationRetriever(self.llm, state.current_time)
        state = await agent.run(state)
        logger.info("CHESS-SQL stage finished: information_retriever")
        return {
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            "keywords": state.keywords,
            "retrieved_entities": state.retrieved_entities,
            "retrieved_context": state.retrieved_context,
            **self._token_usage_update(state),
        }

    async def schema_selector(self, state: ChessSQLAgentState) -> Dict[str, Any]:
        logger.info("CHESS-SQL stage started: schema_selector")
        agent = SchemaSelector(self.llm, state.current_time, self.mcp_tools)
        state = await agent.run(state)
        logger.info("CHESS-SQL stage finished: schema_selector")
        return {
            "selected_tables": state.selected_tables,
            "selected_columns": state.selected_columns,
            "schema_metadata": state.schema_metadata,
            "selected_schema": state.selected_schema,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def candidate_generator(self, state: ChessSQLAgentState) -> Dict[str, Any]:
        logger.info("CHESS-SQL stage started: candidate_generator")
        agent = CandidateGenerator(self.llm, state.current_time)
        state = await agent.run(state)
        logger.info("CHESS-SQL stage finished: candidate_generator")
        return {
            "candidate_sqls": state.candidate_sqls,
            "sql_query": state.sql_query,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def execute_sql(self, state: ChessSQLAgentState) -> Dict[str, Any]:
        logger.info("CHESS-SQL stage started: execute_sql")
        if not state.sql_query:
            raise ValueError("SQL query is empty. Did candidate generation fail?")

        state.sql_result = await self.mcp_tools.execute_code(state.sql_query)
        self._append_execute_messages(state, state.sql_query, state.sql_result)
        logger.info("CHESS-SQL stage finished: execute_sql")
        return {
            "sql_result": state.sql_result,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            "num_tools_calls": state.num_tools_calls,
            **self._token_usage_update(state),
        }

    async def unit_tester(self, state: ChessSQLAgentState) -> Dict[str, Any]:
        logger.info("CHESS-SQL stage started: unit_tester")
        tester = UnitTester(self.llm, state.current_time)
        state = await tester.run(state)

        if not tester.passed and state.current_iteration < self.config.max_revision_attempts:
            generator = CandidateGenerator(self.llm, state.current_time)
            await generator.revise(state)
            state.current_iteration += 1

        logger.info("CHESS-SQL stage finished: unit_tester")
        return {
            "unit_tests": state.unit_tests,
            "sql_query": state.sql_query,
            "current_iteration": state.current_iteration,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def _needs_revision(self, state: ChessSQLAgentState) -> str:
        if state.current_iteration >= self.config.max_revision_attempts:
            return "format"
        if is_failed_or_empty_result(state.sql_result):
            return "test"
        return "test"

    def _after_unit_test(self, state: ChessSQLAgentState) -> str:
        if state.current_iteration > 0 and state.current_iteration <= self.config.max_revision_attempts:
            return "execute"
        return "format"

    async def final_formatter(self, state: ChessSQLAgentState) -> Dict[str, Any]:
        logger.info("CHESS-SQL stage started: final_formatter")
        question_text = self._get_question_text(state)
        if "[entity]" in question_text.lower():
            entity_answer = extract_entity_answer(state.sql_result)
            if entity_answer is not None:
                state.final_answer = f"\\boxed{{{entity_answer}}}"
                final_message = {"role": "assistant", "content": state.final_answer}
                state.messages.append(final_message)
                self._append_trace_message(state, final_message, "CHESS-SQL.final_formatter")
                logger.info("CHESS-SQL stage finished: final_formatter")
                return {
                    "final_answer": state.final_answer,
                    "messages": state.messages,
                    "trace_messages": state.trace_messages,
                    **self._token_usage_update(state),
                }

        formatter_messages = [
            {"role": "system", "content": FINAL_FORMATTER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question:\n{question_text}\n\n"
                    f"SQL result:\n{state.sql_result}"
                ),
            },
        ]
        for message in formatter_messages:
            self._append_trace_message(state, message, "CHESS-SQL.final_formatter")
        state.final_answer = await self.llm.ainvoke(formatter_messages)
        final_message = {"role": "assistant", "content": state.final_answer}
        state.messages.append(final_message)
        self._append_trace_message(state, final_message, "CHESS-SQL.final_formatter")
        logger.info("CHESS-SQL stage finished: final_formatter")
        return {
            "final_answer": state.final_answer,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(ChessSQLAgentState)
        workflow.add_node("information_retriever", self.information_retriever)
        workflow.add_node("schema_selector", self.schema_selector)
        workflow.add_node("candidate_generator", self.candidate_generator)
        workflow.add_node("execute_sql", self.execute_sql)
        workflow.add_node("unit_tester", self.unit_tester)
        workflow.add_node("final_formatter", self.final_formatter)

        workflow.set_entry_point("information_retriever")
        workflow.add_edge("information_retriever", "schema_selector")
        workflow.add_edge("schema_selector", "candidate_generator")
        workflow.add_edge("candidate_generator", "execute_sql")
        workflow.add_conditional_edges(
            "execute_sql",
            self._needs_revision,
            {
                "test": "unit_tester",
                "format": "final_formatter",
            },
        )
        workflow.add_conditional_edges(
            "unit_tester",
            self._after_unit_test,
            {
                "execute": "execute_sql",
                "format": "final_formatter",
            },
        )
        workflow.add_edge("final_formatter", END)
        return workflow.compile()

    async def ainvoke(self, state: ChessSQLAgentState) -> ChessSQLAgentState:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Starting baseline CHESS-SQL invocation with thread ID: {self.session_id}")
        result = await self.graph.ainvoke(state)
        if result is None:
            raise ValueError("Workflow execution returned None.")
        if isinstance(result, ChessSQLAgentState):
            return result
        return ChessSQLAgentState(**result)
