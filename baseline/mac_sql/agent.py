import asyncio
import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from agent.core.env_config import get_env, load_env_config
from agent.llm import get_llm_wrapper
from agent.llm.llm_utils import logger
from baseline.mac_sql.core.chat_manager import ChatManager
from baseline.mac_sql.core.const import SYSTEM_NAME
from baseline.mac_sql.state import MacSQLAgentState
from baseline.utils import extract_entity_answer, load_baseline_prompt


load_env_config()

FORMATER_SYSTEM_PROMPT = load_baseline_prompt("answer_formatter.md")


class MacSQLAgentConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent_type: str = "mac_sql"
    model_name: str
    urls: Optional[List[str]] = None
    streaming: bool = False
    postgres_url: Optional[str] = None
    postgres_schema: str = Field(default="public", alias="schema")
    db_id: str = "finance"
    log_file: str = ""
    include_tables: Optional[List[str]] = None
    exclude_tables: Optional[List[str]] = None
    without_selector: bool = False


class MacSQLAgent:
    def __init__(self, config: MacSQLAgentConfig) -> None:
        logger.info(f"Initializing baseline MAC-SQL agent with config: {config}")
        self.config = config
        self.llm = get_llm_wrapper(config.model_name)
        self._initialized = False
        self.session_id = str(uuid4())
        self.graph = self.build_graph()

    async def initialize(self) -> None:
        if not self._initialized:
            self._initialized = True

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def _get_question_text(self, state: MacSQLAgentState) -> str:
        return state.user_request or state.question

    @staticmethod
    def _update_token_usage(state: MacSQLAgentState, response: Any) -> None:
        if not isinstance(response, dict):
            return

        prompt_tokens = int(response.get("prompt_tokens") or 0)
        completion_tokens = int(response.get("completion_tokens") or 0)

        state.total_tokens = prompt_tokens + completion_tokens
        state.total_prompt_tokens += prompt_tokens
        state.total_output_tokens += completion_tokens

    @staticmethod
    def _token_usage_update(state: MacSQLAgentState) -> Dict[str, int]:
        return {
            "total_tokens": state.total_tokens,
            "total_prompt_tokens": state.total_prompt_tokens,
            "total_output_tokens": state.total_output_tokens,
        }

    @staticmethod
    def _format_sql_result(rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "[FAILED] NO_DATA"

        columns = list(rows[0].keys())
        lines = [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join(["---"] * len(columns)) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
        return "\n".join(lines)

    @staticmethod
    def _append_trace_message(
        state: MacSQLAgentState,
        message: Dict[str, Any],
        agent_name: str,
    ) -> None:
        traced_message = dict(message)
        traced_message["agent"] = agent_name
        state.trace_messages.append(traced_message)

    def _append_execute_messages(self, state: MacSQLAgentState) -> None:
        tool_call_id = f"call_{uuid4().hex}"
        assistant_message = {
            "role": "assistant",
            "content": state.sql_query,
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "execute_code",
                        "arguments": json.dumps({"query": state.sql_query}, ensure_ascii=False),
                    },
                }
            ],
        }
        tool_message = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": state.sql_result,
        }
        state.messages.append(assistant_message)
        state.messages.append(tool_message)
        self._append_trace_message(state, assistant_message, "MAC-SQL.execute_sql")
        self._append_trace_message(state, tool_message, "MAC-SQL.execute_sql")

    def _build_message(self, state: MacSQLAgentState) -> Dict[str, Any]:
        return {
            "idx": 0,
            "db_id": state.db_id or self.config.db_id,
            "query": self._get_question_text(state),
            "evidence": state.evidence,
            "extracted_schema": state.extracted_schema or {},
            "ground_truth": "",
            "difficulty": "",
            "send_to": SYSTEM_NAME,
            **self._token_usage_update(state),
        }

    def _build_manager(self):
        postgres_url = self.config.postgres_url or get_env("POSTGRES_URL")
        if not postgres_url:
            raise ValueError("POSTGRES_URL is not set. Pass postgres_url or define it in the environment.")

        return ChatManager(
            postgres_url=postgres_url,
            schema=self.config.postgres_schema,
            log_path=self.config.log_file,
            model_name=self.config.model_name,
            llm=self.llm,
            include_tables=self.config.include_tables,
            exclude_tables=self.config.exclude_tables,
            without_selector=self.config.without_selector,
        )

    async def run_mac_sql(self, state: MacSQLAgentState) -> Dict[str, Any]:
        question_text = self._get_question_text(state)
        if not question_text:
            raise ValueError("MacSQLAgentState.user_request is empty.")

        state.messages = [
            {
                "role": "system",
                "content": "MAC-SQL baseline. Generate PostgreSQL, execute it, and refine failed SQL.",
            },
            {"role": "user", "content": question_text},
        ]
        for message in state.messages:
            self._append_trace_message(state, message, "MAC-SQL")

        logger.info("MAC-SQL stage started: run_mac_sql")
        manager = self._build_manager()
        message = self._build_message(state)
        await asyncio.to_thread(manager.start, message)
        self._update_token_usage(state, message)

        state.mac_sql_message = message
        state.extracted_schema = message.get("extracted_schema", {})
        state.chosen_db_schem_dict = message.get("chosen_db_schem_dict", {})
        state.desc_str = message.get("desc_str", "")
        state.fk_str = message.get("fk_str", "")
        state.qa_pairs = message.get("qa_pairs", [])
        state.execution_result = message.get("execution_result", [])
        state.sql_query = message.get("pred") or message.get("final_sql", "")
        state.sql_result = self._format_sql_result(state.execution_result)
        self._append_execute_messages(state)

        logger.info("MAC-SQL stage finished: run_mac_sql")
        return {
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            "extracted_schema": state.extracted_schema,
            "chosen_db_schem_dict": state.chosen_db_schem_dict,
            "desc_str": state.desc_str,
            "fk_str": state.fk_str,
            "qa_pairs": state.qa_pairs,
            "execution_result": state.execution_result,
            "mac_sql_message": state.mac_sql_message,
            "sql_query": state.sql_query,
            "sql_result": state.sql_result,
            **self._token_usage_update(state),
        }

    async def final_formatter(self, state: MacSQLAgentState) -> Dict[str, Any]:
        logger.info("MAC-SQL stage started: final_formatter")
        question_text = self._get_question_text(state)

        if "[entity]" in question_text.lower():
            entity_answer = extract_entity_answer(state.sql_result)
            if entity_answer is not None:
                state.final_answer = f"\\boxed{{{entity_answer}}}"
                final_message = {"role": "assistant", "content": state.final_answer}
                state.messages.append(final_message)
                self._append_trace_message(state, final_message, "MAC-SQL.final_formatter")
                return {
                    "final_answer": state.final_answer,
                    "messages": state.messages,
                    "trace_messages": state.trace_messages,
                    **self._token_usage_update(state),
                }

        messages = [
            {
                "role": "system",
                "content": FORMATER_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question_text}\n\n"
                    f"SQL Query:\n```sql\n{state.sql_query}\n```\n\n"
                    f"SQL Result:\n\n{state.sql_result}"
                ),
            },
        ]
        detail_kwargs = {}
        if getattr(self.llm, "model_type", "") != "gemini":
            detail_kwargs["detail"] = True

        final_answer = await self.llm.ainvoke(messages, **detail_kwargs)
        self._update_token_usage(state, final_answer)
        if isinstance(final_answer, dict):
            response_text = final_answer.get("content", "")
        else:
            response_text = final_answer
        state.final_answer = response_text
        final_message = {"role": "assistant", "content": response_text}
        state.messages.append(final_message)
        self._append_trace_message(state, final_message, "MAC-SQL.final_formatter")

        logger.info("MAC-SQL stage finished: final_formatter")
        return {
            "final_answer": state.final_answer,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(MacSQLAgentState)
        workflow.add_node("run_mac_sql", self.run_mac_sql)
        workflow.add_node("final_formatter", self.final_formatter)
        workflow.set_entry_point("run_mac_sql")
        workflow.add_edge("run_mac_sql", "final_formatter")
        workflow.add_edge("final_formatter", END)
        return workflow.compile()

    async def ainvoke(self, state: MacSQLAgentState) -> MacSQLAgentState:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Starting baseline MAC-SQL invocation with thread ID: {self.session_id}")
        result = await self.graph.ainvoke(state)
        if result is None:
            raise ValueError("Workflow execution returned None.")

        if isinstance(result, MacSQLAgentState):
            return result

        return MacSQLAgentState(**result)
