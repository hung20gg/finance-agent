import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict

from agent.core.env_config import load_env_config
from agent.core.logger import logger
from agent.core.mcp_client import MCPClient
from agent.llm import get_llm_wrapper
from baseline.din_sql.state import DINSQLAgentState
from baseline.utils import (
    code_block_extractor,
    extract_entity_answer,
    extract_json_object,
    extract_tool_text,
    load_baseline_prompt,
    load_prompt_file,
)


load_env_config()

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
FINAL_FORMATTER_PROMPT = load_baseline_prompt("answer_formatter.md")
FINANCE_TABLES = [
    "dim_company",
    "dim_industry",
    "dim_exchange",
    "dim_financial_ratio",
    "dim_financial_statement_category",
    "dim_market_index",
    "dim_commodity_indicator",
    "dim_macro_indicator",
    "dim_country",
    "fact_financial_ratio",
    "fact_financial_statement",
    "fact_stock_daily",
    "fact_stock_monthly",
    "fact_index_daily",
    "fact_index_monthly",
    "fact_commodity_daily",
    "fact_commodity_monthly",
    "fact_macro",
    "fact_industry_financial_statement",
    "fact_industry_financial_ratio",
]


class DINSQLAgentConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent_type: str = "din_sql"
    model_name: str
    urls: Optional[List[str]] = None
    streaming: bool = False
    include_tables: Optional[List[str]] = None
    exclude_tables: Optional[List[str]] = None
    use_dynamic_examples: bool = True
    self_correction_prompt: str = "gentle"


class DINSQLAgent:
    """DIN-SQL baseline adapted to the repository baseline interface.

    The graph follows the paper's modules in order:
    schema linking -> classification/decomposition -> class-specific SQL generation
    -> zero-shot self-correction.
    """

    def __init__(self, config: DINSQLAgentConfig) -> None:
        logger.info(f"Initializing baseline DIN-SQL agent with config: {config}")
        self.config = config
        self.llm = get_llm_wrapper(config.model_name)
        self.mcp_client = MCPClient(config.urls)
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

    def _get_question_text(self, state: DINSQLAgentState) -> str:
        return state.user_request or state.question

    @staticmethod
    def _update_token_usage(state: DINSQLAgentState, response: Any) -> None:
        if not isinstance(response, dict):
            return

        prompt_tokens = int(response.get("prompt_tokens") or 0)
        completion_tokens = int(response.get("completion_tokens") or 0)

        state.total_tokens = prompt_tokens + completion_tokens
        state.total_prompt_tokens += prompt_tokens
        state.total_output_tokens += completion_tokens

    @staticmethod
    def _token_usage_update(state: DINSQLAgentState) -> Dict[str, int]:
        return {
            "total_tokens": state.total_tokens,
            "total_prompt_tokens": state.total_prompt_tokens,
            "total_output_tokens": state.total_output_tokens,
        }

    @staticmethod
    def _append_trace_message(
        state: DINSQLAgentState,
        message: Dict[str, Any],
        agent_name: str,
    ) -> None:
        traced_message = deepcopy(message)
        traced_message["agent"] = agent_name
        state.trace_messages.append(traced_message)

    @staticmethod
    def _normalize_query_class(label: str) -> str:
        normalized = (label or "").strip().upper().replace("_", "-")
        if normalized == "NON-NESTED":
            return "NON-NESTED"
        if normalized == "NESTED":
            return "NESTED"
        return "EASY"

    @staticmethod
    def _extract_sql(text: str) -> str:
        # Treat an empty or literal "None" response as no SQL produced
        if not text or text.strip().lower() == "none":
            return ""

        parsed = extract_json_object(text) or {}
        sql = parsed.get("sql")
        if isinstance(sql, str) and sql.strip():
            return sql.strip()

        code = code_block_extractor(text)
        if code and code != text:
            return code.strip()

        sql_match = re.search(r"SQL\s*:\s*(.*)", text, flags=re.IGNORECASE | re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        return text.strip()

    @staticmethod
    def _load_prompt(name: str) -> str:
        return load_prompt_file(PROMPT_DIR / name)

    @staticmethod
    def _render_prompt(template: str, values: Dict[str, Any]) -> str:
        rendered = template
        for key, value in values.items():
            if isinstance(value, (dict, list)):
                value_text = json.dumps(value, ensure_ascii=False, indent=2)
            else:
                value_text = str(value)
            rendered = rendered.replace("{" + key + "}", value_text)
        return rendered

    async def _invoke_module(
        self,
        state: DINSQLAgentState,
        stage_name: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for message in messages:
            self._append_trace_message(state, message, f"DIN-SQL.{stage_name}")

        response = await self.llm.ainvoke(messages, detail=True)
        if isinstance(response, dict):
            self._update_token_usage(state, response)
            response_text = response.get("content") or ""
        elif response is None:
            logger.warning(
                "DIN-SQL module '%s' received None from LLM — likely an API error.",
                stage_name,
            )
            response_text = ""
        else:
            response_text = str(response)

        self._append_trace_message(
            state,
            {"role": "assistant", "content": response_text},
            f"DIN-SQL.{stage_name}",
        )
        return response_text

    async def _load_mcp_schema_context(self) -> str:
        tables = list(self.config.include_tables or FINANCE_TABLES)
        excluded = set(self.config.exclude_tables or ["dim_data_catalog"])
        tables = [table for table in tables if table not in excluded]
        has_metadata_tool = await self.mcp_client.has_tool("get_table_metadata")

        parts = []
        for table_name in tables:
            metadata = ""
            if has_metadata_tool:
                try:
                    tool_result = await self.mcp_client.call_tool(
                        "get_table_metadata",
                        {"table_name": table_name},
                    )
                    metadata = extract_tool_text(tool_result)
                except Exception as exc:
                    logger.warning(
                        "DIN-SQL failed to load MCP metadata for %s: %s",
                        table_name,
                        exc,
                    )
            parts.append(f"Table {table_name}, metadata:\n{metadata or 'No metadata available.'}")
        parts.append("Foreign_keys:\n")
        return "\n\n".join(parts)

    async def _load_examples(self, question_text: str) -> str:
        static_examples = self._load_prompt("static_examples.md").strip()
        if not self.config.use_dynamic_examples:
            return static_examples
        try:
            if await self.mcp_client.has_tool("get_example_sql"):
                tool_result = await self.mcp_client.call_tool(
                    "get_example_sql",
                    {"query": question_text},
                )
                dynamic_examples = extract_tool_text(tool_result)
            else:
                dynamic_examples = ""
        except Exception as exc:
            logger.warning("DIN-SQL failed to load dynamic examples: %s", exc)
            dynamic_examples = ""
        if dynamic_examples.strip():
            return (
                f"{static_examples}\n\n"
                f"Additional retrieved SQL examples:\n{dynamic_examples.strip()}"
            )
        return static_examples

    async def prepare_context(self, state: DINSQLAgentState) -> Dict[str, Any]:
        logger.info("DIN-SQL stage started: prepare_context")
        question_text = self._get_question_text(state)
        if not question_text:
            raise ValueError("DINSQLAgentState.user_request is empty.")

        state.messages = [
            {
                "role": "system",
                "content": (
                    "DIN-SQL baseline. Follow schema linking, classification and "
                    "decomposition, class-specific SQL generation, and self-correction."
                ),
            },
            {"role": "user", "content": question_text},
        ]
        for message in state.messages:
            self._append_trace_message(state, message, "DIN-SQL")

        state.schema_context = await self._load_mcp_schema_context()
        state.examples_text = await self._load_examples(question_text)

        logger.info("DIN-SQL stage finished: prepare_context")
        return {
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            "schema_context": state.schema_context,
            "examples_text": state.examples_text,
            **self._token_usage_update(state),
        }

    async def schema_linking(self, state: DINSQLAgentState) -> Dict[str, Any]:
        logger.info("DIN-SQL stage started: schema_linking")
        question_text = self._get_question_text(state)
        prompt = self._render_prompt(
            self._load_prompt("schema_linking.md"),
            {
                "current_time": state.current_time,
                "schema_context": state.schema_context,
                "examples_text": state.examples_text,
                "question": question_text,
            },
        )
        response = await self._invoke_module(
            state,
            "schema_linking",
            "You are the DIN-SQL schema linking module.",
            prompt,
        )
        parsed = extract_json_object(response) or {}
        schema_links = parsed.get("schema_links", [])
        if isinstance(schema_links, list):
            state.schema_links = [str(item) for item in schema_links]
        else:
            state.schema_links = [str(schema_links)] if schema_links else []

        logger.info("DIN-SQL stage finished: schema_linking")
        return {
            "schema_links": state.schema_links,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def classify_decompose(self, state: DINSQLAgentState) -> Dict[str, Any]:
        logger.info("DIN-SQL stage started: classify_decompose")
        question_text = self._get_question_text(state)
        prompt = self._render_prompt(
            self._load_prompt("classify_decompose.md"),
            {
                "current_time": state.current_time,
                "schema_context": state.schema_context,
                "examples_text": state.examples_text,
                "question": question_text,
                "schema_links": state.schema_links,
            },
        )
        response = await self._invoke_module(
            state,
            "classify_decompose",
            "You are the DIN-SQL classification and decomposition module.",
            prompt,
        )
        parsed = extract_json_object(response) or {}
        state.query_class = self._normalize_query_class(str(parsed.get("label", "")))

        join_tables = parsed.get("join_tables", [])
        if isinstance(join_tables, list):
            state.join_tables = [str(table) for table in join_tables if str(table).strip()]

        sub_questions = parsed.get("sub_questions", [])
        if isinstance(sub_questions, list):
            state.sub_questions = [
                str(question) for question in sub_questions if str(question).strip()
            ]

        logger.info("DIN-SQL stage finished: classify_decompose")
        return {
            "query_class": state.query_class,
            "join_tables": state.join_tables,
            "sub_questions": state.sub_questions,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def generate_sql(self, state: DINSQLAgentState) -> Dict[str, Any]:
        logger.info("DIN-SQL stage started: generate_sql")
        question_text = self._get_question_text(state)
        prompt_file = {
            "EASY": "generate_easy.md",
            "NON-NESTED": "generate_non_nested.md",
            "NESTED": "generate_nested.md",
        }.get(state.query_class or "EASY", "generate_easy.md")

        prompt = self._render_prompt(
            self._load_prompt(prompt_file),
            {
                "current_time": state.current_time,
                "schema_context": state.schema_context,
                "examples_text": state.examples_text,
                "question": question_text,
                "schema_links": state.schema_links,
                "join_tables": state.join_tables,
                "sub_questions": state.sub_questions,
            },
        )
        response = await self._invoke_module(
            state,
            "generate_sql",
            "You are the DIN-SQL SQL generation module.",
            prompt,
        )
        parsed = extract_json_object(response) or {}
        intermediate = parsed.get("intermediate_representation", "")
        if isinstance(intermediate, str):
            state.intermediate_representation = intermediate.strip()
        subquery_sqls = parsed.get("subquery_sqls", {})
        if isinstance(subquery_sqls, dict):
            state.subquery_sqls = {
                str(key): str(value) for key, value in subquery_sqls.items()
            }
        state.generated_sql = self._extract_sql(response)
        state.sql_query = state.generated_sql

        logger.info("DIN-SQL stage finished: generate_sql")
        return {
            "intermediate_representation": state.intermediate_representation,
            "subquery_sqls": state.subquery_sqls,
            "generated_sql": state.generated_sql,
            "sql_query": state.sql_query,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def self_correct(self, state: DINSQLAgentState) -> Dict[str, Any]:
        logger.info("DIN-SQL stage started: self_correct")
        question_text = self._get_question_text(state)
        prompt_name = "self_correction_gentle.md"
        if self.config.self_correction_prompt.lower() == "generic":
            prompt_name = "self_correction_generic.md"

        prompt = self._render_prompt(
            self._load_prompt(prompt_name),
            {
                "current_time": state.current_time,
                "schema_context": state.schema_context,
                "question": question_text,
                "sql_query": state.sql_query,
            },
        )
        response = await self._invoke_module(
            state,
            "self_correct",
            "You are the DIN-SQL self-correction module.",
            prompt,
        )
        corrected_sql = self._extract_sql(response)
        state.corrected_sql = corrected_sql or state.generated_sql
        state.sql_query = state.corrected_sql

        logger.info("DIN-SQL stage finished: self_correct")
        return {
            "corrected_sql": state.corrected_sql,
            "sql_query": state.sql_query,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def execute_sql(self, state: DINSQLAgentState) -> Dict[str, Any]:
        logger.info("DIN-SQL stage started: execute_sql")
        if not state.sql_query:
            logger.warning("DIN-SQL execute_sql: SQL query is empty — skipping execution and recording failure.")
            state.sql_result = "[FAILED] SQL generation produced no query."
            failed_message = {"role": "assistant", "content": state.sql_result}
            state.messages.append(failed_message)
            self._append_trace_message(state, failed_message, "DIN-SQL.execute_sql")
            return {
                "messages": state.messages,
                "trace_messages": state.trace_messages,
                "sql_result": state.sql_result,
                "num_tools_calls": state.num_tools_calls,
                **self._token_usage_update(state),
            }
        if not await self.mcp_client.has_tool("execute_code"):
            raise ValueError(
                "DIN-SQL requires MCP tool 'execute_code'. Start the MCP server "
                "on MCP_SERVER_URL, or set MCP_SERVER_URL to the running SSE endpoint."
            )

        tool_result = await self.mcp_client.call_tool(
            "execute_code",
            {"query": state.sql_query},
        )
        state.sql_result = extract_tool_text(tool_result)
        state.num_tools_calls += 1

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
                        "arguments": json.dumps(
                            {"query": state.sql_query},
                            ensure_ascii=False,
                        ),
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
        self._append_trace_message(state, assistant_message, "DIN-SQL.execute_sql")
        self._append_trace_message(state, tool_message, "DIN-SQL.execute_sql")

        logger.info("DIN-SQL stage finished: execute_sql")
        return {
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            "sql_result": state.sql_result,
            "num_tools_calls": state.num_tools_calls,
            **self._token_usage_update(state),
        }

    async def final_formatter(self, state: DINSQLAgentState) -> Dict[str, Any]:
        logger.info("DIN-SQL stage started: final_formatter")
        question_text = self._get_question_text(state)

        if "[entity]" in question_text.lower():
            entity_answer = extract_entity_answer(state.sql_result)
            if entity_answer is not None:
                state.final_answer = f"\\boxed{{{entity_answer}}}"
                final_message = {"role": "assistant", "content": state.final_answer}
                state.messages.append(final_message)
                self._append_trace_message(state, final_message, "DIN-SQL.final_formatter")
                logger.info("DIN-SQL stage finished: final_formatter")
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
                    f"Question: {question_text}\n\n"
                    f"SQL Query:\n```sql\n{state.sql_query}\n```\n\n"
                    f"SQL Result:\n\n{state.sql_result}"
                ),
            },
        ]
        for message in formatter_messages:
            self._append_trace_message(state, message, "DIN-SQL.final_formatter")

        response = await self.llm.ainvoke(formatter_messages, detail=True)
        if isinstance(response, dict):
            self._update_token_usage(state, response)
            state.final_answer = response.get("content", "")
        else:
            state.final_answer = str(response)

        final_message = {"role": "assistant", "content": state.final_answer}
        state.messages.append(final_message)
        self._append_trace_message(state, final_message, "DIN-SQL.final_formatter")
        logger.info("DIN-SQL stage finished: final_formatter")
        return {
            "final_answer": state.final_answer,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(DINSQLAgentState)
        workflow.add_node("prepare_context", self.prepare_context)
        workflow.add_node("schema_linking", self.schema_linking)
        workflow.add_node("classify_decompose", self.classify_decompose)
        workflow.add_node("generate_sql", self.generate_sql)
        workflow.add_node("self_correct", self.self_correct)
        workflow.add_node("execute_sql", self.execute_sql)
        workflow.add_node("final_formatter", self.final_formatter)

        workflow.set_entry_point("prepare_context")
        workflow.add_edge("prepare_context", "schema_linking")
        workflow.add_edge("schema_linking", "classify_decompose")
        workflow.add_edge("classify_decompose", "generate_sql")
        workflow.add_edge("generate_sql", "self_correct")
        workflow.add_edge("self_correct", "execute_sql")
        workflow.add_edge("execute_sql", "final_formatter")
        workflow.add_edge("final_formatter", END)
        return workflow.compile()

    async def ainvoke(self, state: DINSQLAgentState) -> DINSQLAgentState:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Starting baseline DIN-SQL invocation with thread ID: {self.session_id}")
        result = await self.graph.ainvoke(state)
        if result is None:
            raise ValueError("Workflow execution returned None.")
        if isinstance(result, DINSQLAgentState):
            return result
        return DINSQLAgentState(**result)
