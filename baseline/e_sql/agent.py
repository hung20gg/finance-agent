import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from agent.core.logger import logger
from agent.core.mcp_client import MCPClient
from agent.llm import get_llm_wrapper
from baseline.e_sql.state import ESQLAgentState
from baseline.utils import (
    code_block_extractor,
    extract_entity_answer,
    extract_json_object,
    extract_tool_text,
    is_failed_or_empty_result,
    load_baseline_prompt,
    render_current_time_prompt,
)


PREDICATE_PROMPT = load_baseline_prompt("e_sql", "predicate_generation.md")
ENRICHMENT_PROMPT = load_baseline_prompt("e_sql", "question_enrichment.md")
GENERATE_PROMPT = load_baseline_prompt("e_sql", "generate_sql.md")
REFINE_PROMPT = load_baseline_prompt("e_sql", "refine.md")
FORMATTER_PROMPT = load_baseline_prompt("answer_formatter.md")

MAX_PROBE_QUERIES = 3


class ESQLAgentConfig(BaseModel):
    agent_type: str = "e_sql"
    model_name: str
    urls: Optional[List[str]] = None
    streaming: bool = False
    max_refine_attempts: int = 2


class ESQLAgent:
    """E-SQL baseline (question enrichment + candidate predicate generation + refinement).

    Built on top of the vanilla baseline: a single-pass generator is extended
    with (1) candidate predicate generation that grounds question values in the
    database via probe queries, (2) question enrichment, and (3) an
    execution-feedback refinement loop.
    """

    def __init__(self, config: ESQLAgentConfig) -> None:
        logger.info(f"Initializing baseline E-SQL agent with config: {config}")
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

    def _get_question_text(self, state: ESQLAgentState) -> str:
        return state.user_request or state.question

    @staticmethod
    def _update_token_usage(state: ESQLAgentState, response: Any) -> None:
        if not isinstance(response, dict):
            return
        prompt_tokens = int(response.get("prompt_tokens") or 0)
        completion_tokens = int(response.get("completion_tokens") or 0)
        state.total_tokens = prompt_tokens + completion_tokens
        state.total_prompt_tokens += prompt_tokens
        state.total_output_tokens += completion_tokens

    def _token_usage_update(self, state: ESQLAgentState) -> Dict[str, int]:
        return {
            "total_tokens": state.total_tokens,
            "total_prompt_tokens": state.total_prompt_tokens,
            "total_output_tokens": state.total_output_tokens,
        }

    async def _ainvoke_text(self, state: ESQLAgentState, messages: List[Dict[str, Any]]) -> str:
        response = await self.llm.ainvoke(messages, detail=True)
        if isinstance(response, dict):
            self._update_token_usage(state, response)
            return response.get("content", "")
        return response

    def _trace(self, state: ESQLAgentState, role: str, content: str, agent: str) -> None:
        state.trace_messages.append({"role": role, "content": content, "agent": agent})

    async def _run_probe(self, query: str) -> str:
        try:
            tool_result = await self.mcp_client.call_tool("execute_code", {"query": query})
            return extract_tool_text(tool_result)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("E-SQL probe query failed: %s", exc)
            return f"[FAILED] {exc}"

    # ------------------------------------------------------------------ nodes
    async def predicate_generation(self, state: ESQLAgentState) -> Dict[str, Any]:
        logger.info("E-SQL stage started: predicate_generation")
        question_text = self._get_question_text(state)
        if not question_text:
            raise ValueError("ESQLAgentState.user_request is empty.")

        system_prompt = render_current_time_prompt(PREDICATE_PROMPT, state.current_time)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question:\n{question_text}"},
        ]
        self._trace(state, "user", question_text, "E-SQL.predicate_generation")
        response_text = await self._ainvoke_text(state, messages)
        self._trace(state, "assistant", response_text, "E-SQL.predicate_generation")

        parsed = extract_json_object(response_text) or {}
        predicates = parsed.get("predicates") or []
        probe_queries = parsed.get("probe_queries") or []
        if isinstance(predicates, list):
            state.candidate_predicates = [str(p) for p in predicates]

        probe_texts: List[str] = []
        for probe in probe_queries[:MAX_PROBE_QUERIES]:
            if not isinstance(probe, str) or not probe.strip():
                continue
            result = await self._run_probe(probe)
            state.num_tools_calls += 1
            probe_texts.append(f"-- {probe}\n{result}")
            self._trace(state, "tool", f"{probe}\n{result}", "E-SQL.predicate_generation")
        state.probe_results = "\n\n".join(probe_texts)

        logger.info("E-SQL stage finished: predicate_generation")
        return {
            "candidate_predicates": state.candidate_predicates,
            "probe_results": state.probe_results,
            "trace_messages": state.trace_messages,
            "num_tools_calls": state.num_tools_calls,
            **self._token_usage_update(state),
        }

    async def question_enrichment(self, state: ESQLAgentState) -> Dict[str, Any]:
        logger.info("E-SQL stage started: question_enrichment")
        question_text = self._get_question_text(state)
        system_prompt = render_current_time_prompt(ENRICHMENT_PROMPT, state.current_time)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Original question:\n{question_text}\n\n"
                    f"Candidate predicates:\n{state.candidate_predicates}\n\n"
                    f"Value linking probe results:\n{state.probe_results}"
                ),
            },
        ]
        enriched = await self._ainvoke_text(state, messages)
        state.enriched_question = enriched.strip() or question_text
        self._trace(state, "assistant", state.enriched_question, "E-SQL.question_enrichment")
        logger.info("E-SQL stage finished: question_enrichment")
        return {
            "enriched_question": state.enriched_question,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def _append_execute_call(self, state: ESQLAgentState, sql: str) -> str:
        tool_call_id = f"call_{uuid4().hex}"
        state.messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": "execute_code",
                            "arguments": json.dumps({"query": sql}, ensure_ascii=False),
                        },
                    }
                ],
            }
        )
        return tool_call_id

    async def generate_sql(self, state: ESQLAgentState) -> Dict[str, Any]:
        logger.info("E-SQL stage started: generate_sql")
        question_text = self._get_question_text(state)
        system_prompt = render_current_time_prompt(GENERATE_PROMPT, state.current_time)
        if not state.messages:
            state.messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": state.enriched_question or question_text},
            ]
        gen_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Enriched question:\n{state.enriched_question or question_text}\n\n"
                    f"Candidate predicates:\n{state.candidate_predicates}\n\n"
                    f"Value linking probe results:\n{state.probe_results}"
                ),
            },
        ]
        response_text = await self._ainvoke_text(state, gen_messages)
        state.sql_query = code_block_extractor(response_text)
        self._trace(state, "assistant", response_text, "E-SQL.generate_sql")
        self._append_execute_call(state, state.sql_query)
        logger.info("E-SQL stage finished: generate_sql")
        return {
            "sql_query": state.sql_query,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    async def execute_sql(self, state: ESQLAgentState) -> Dict[str, Any]:
        logger.info("E-SQL stage started: execute_sql")
        if not state.sql_query:
            raise ValueError("SQL query is empty. Did generation fail?")
        tool_result = await self.mcp_client.call_tool("execute_code", {"query": state.sql_query})
        state.sql_result = extract_tool_text(tool_result)
        state.num_tools_calls += 1

        tool_call_id = "execute_code"
        if state.messages and state.messages[-1].get("tool_calls"):
            tool_call_id = state.messages[-1]["tool_calls"][0].get("id", tool_call_id)
        state.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": state.sql_result}
        )
        logger.info("E-SQL stage finished: execute_sql")
        return {
            "sql_result": state.sql_result,
            "messages": state.messages,
            "num_tools_calls": state.num_tools_calls,
            **self._token_usage_update(state),
        }

    async def refine(self, state: ESQLAgentState) -> Dict[str, Any]:
        logger.info("E-SQL stage started: refine (iteration=%d)", state.refine_iteration)
        question_text = self._get_question_text(state)
        system_prompt = render_current_time_prompt(REFINE_PROMPT, state.current_time)
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Question:\n{state.enriched_question or question_text}\n\n"
                    f"Current SQL:\n```sql\n{state.sql_query}\n```\n\n"
                    f"Execution result (error or empty):\n{state.sql_result}"
                ),
            },
        ]
        response_text = await self._ainvoke_text(state, messages)
        refined = code_block_extractor(response_text)
        if refined:
            state.sql_query = refined
        state.refine_iteration += 1
        self._trace(state, "assistant", response_text, "E-SQL.refine")
        self._append_execute_call(state, state.sql_query)
        logger.info("E-SQL stage finished: refine")
        return {
            "sql_query": state.sql_query,
            "refine_iteration": state.refine_iteration,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def _needs_refine(self, state: ESQLAgentState) -> str:
        if is_failed_or_empty_result(state.sql_result) and state.refine_iteration < self.config.max_refine_attempts:
            return "refine"
        return "format"

    async def final_formater(self, state: ESQLAgentState) -> Dict[str, Any]:
        logger.info("E-SQL stage started: final_formater")
        question_text = self._get_question_text(state)
        if "[entity]" in question_text.lower():
            entity_answer = extract_entity_answer(state.sql_result)
            if entity_answer is not None:
                state.final_answer = f"\\boxed{{{entity_answer}}}"
                state.messages.append({"role": "assistant", "content": state.final_answer})
                self._trace(state, "assistant", state.final_answer, "E-SQL.final_formater")
                return {
                    "final_answer": state.final_answer,
                    "messages": state.messages,
                    "trace_messages": state.trace_messages,
                    **self._token_usage_update(state),
                }

        messages = [
            {"role": "system", "content": FORMATTER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {question_text}\n\n"
                    f"SQL Query:\n```sql\n{state.sql_query}\n```\n\n"
                    f"SQL Result:\n\n{state.sql_result}"
                ),
            },
        ]
        final_answer = await self._ainvoke_text(state, messages)
        state.final_answer = final_answer
        state.messages.append({"role": "assistant", "content": final_answer})
        self._trace(state, "assistant", final_answer, "E-SQL.final_formater")
        logger.info("E-SQL stage finished: final_formater")
        return {
            "final_answer": state.final_answer,
            "messages": state.messages,
            "trace_messages": state.trace_messages,
            **self._token_usage_update(state),
        }

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(ESQLAgentState)
        workflow.add_node("predicate_generation", self.predicate_generation)
        workflow.add_node("question_enrichment", self.question_enrichment)
        workflow.add_node("generate_sql", self.generate_sql)
        workflow.add_node("execute_sql", self.execute_sql)
        workflow.add_node("refine", self.refine)
        workflow.add_node("final_formater", self.final_formater)

        workflow.set_entry_point("predicate_generation")
        workflow.add_edge("predicate_generation", "question_enrichment")
        workflow.add_edge("question_enrichment", "generate_sql")
        workflow.add_edge("generate_sql", "execute_sql")
        workflow.add_conditional_edges(
            "execute_sql",
            self._needs_refine,
            {"refine": "refine", "format": "final_formater"},
        )
        workflow.add_edge("refine", "execute_sql")
        workflow.add_edge("final_formater", END)
        return workflow.compile()

    async def ainvoke(self, state: ESQLAgentState) -> ESQLAgentState:
        if not self._initialized:
            await self.initialize()
        logger.info(f"Starting baseline E-SQL invocation with thread ID: {self.session_id}")
        result = await self.graph.ainvoke(state)
        if result is None:
            raise ValueError("Workflow execution returned None.")
        if isinstance(result, ESQLAgentState):
            return result
        return ESQLAgentState(**result)
