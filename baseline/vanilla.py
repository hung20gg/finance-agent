import os
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel
from langgraph.graph import StateGraph, END

from agent.core.logger import logger
from agent.core.mcp_client import MCPClient
from agent.llm import get_llm_wrapper
from baseline.utils import code_block_extractor, extract_tool_text


current_dir = os.path.dirname(os.path.abspath(__file__))
prompt_path = os.path.join(current_dir, "prompt", "text2sql_vanilla_system_prompt.md")
formater_prompt_path = os.path.join(current_dir, "prompt", "answer_formatter.md")

with open(prompt_path, "r", encoding="utf-8") as file:
    VANILLA_SYSTEM_PROMPT = file.read()

with open(formater_prompt_path, "r", encoding="utf-8") as file:
    FORMATER_SYSTEM_PROMPT = file.read()



@dataclass
class VanillaAgentState:
    agent_type: str = "vanilla"
    current_time: str = field(default_factory=lambda: date.today().isoformat())
    user_request: str = ""
    question: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    sql_query: str = ""
    sql_result: str = ""
    final_answer: str = ""
    total_tokens: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0


class VanillaAgentConfig(BaseModel):
    agent_type: str = "vanilla"
    model_name: str
    urls: Optional[List[str]] = None
    streaming: bool = False


class VanillaAgent:
    def __init__(self, config: VanillaAgentConfig) -> None:
        logger.info(f"Initializing baseline vanilla agent with config: {config}")
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

    def _render_system_prompt(self, state: VanillaAgentState) -> str:
        return VANILLA_SYSTEM_PROMPT.replace("{current_time}", str(state.current_time))

    def _get_question_text(self, state: VanillaAgentState) -> str:
        return state.user_request or state.question

    @staticmethod
    def _get_answer_type(question_text: str) -> str:
        question_lower = question_text.lower()
        if "[tuple]" in question_lower:
            return "tuple"
        if "[entity]" in question_lower:
            return "entity"
        return "text"

    @staticmethod
    def _update_token_usage(state: VanillaAgentState, response: Any) -> None:
        if not isinstance(response, dict):
            return

        prompt_tokens = int(response.get("prompt_tokens") or 0)
        completion_tokens = int(response.get("completion_tokens") or 0)

        state.total_tokens = prompt_tokens + completion_tokens
        state.total_prompt_tokens += prompt_tokens
        state.total_output_tokens += completion_tokens

    @staticmethod
    def _token_usage_update(state: VanillaAgentState) -> Dict[str, int]:
        return {
            "total_tokens": state.total_tokens,
            "total_prompt_tokens": state.total_prompt_tokens,
            "total_output_tokens": state.total_output_tokens,
        }

    async def generate_sql(self, state: VanillaAgentState) -> Dict[str, Any]:
        question_text = self._get_question_text(state)
        if not question_text:
            raise ValueError("VanillaAgentState.user_request is empty.")

        system_prompt = self._render_system_prompt(state)
        logger.info(
            "Generating SQL for baseline vanilla agent. question=%s",
            question_text,
        )
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": f"Question: {question_text}",
            },
        ]

        response = await self.llm.ainvoke(messages, detail=True)
        if isinstance(response, dict):
            self._update_token_usage(state, response)
            response_text = response.get("content", "")
        else:
            response_text = response

        state.sql_query = code_block_extractor(response_text)
        tool_call_id = f"call_{uuid4().hex}"
        state.messages.extend(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question_text},
                {
                    "role": "assistant",
                    "content": response_text,
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
                },
            ]
        )
        logger.info(
            "Generated SQL for baseline vanilla agent. "
        )
        logger.debug(
            "Raw SQL generation response for baseline vanilla agent. response=%s"
        )
        return {
            "sql_query": state.sql_query,
            "messages": state.messages,
            **self._token_usage_update(state),
        }

    async def run_sql(self, state: VanillaAgentState) -> Dict[str, Any]:
        if not state.sql_query:
            raise ValueError("SQL query is empty. Did SQL generation fail?")

        logger.info(
            "Executing SQL for baseline vanilla agent. sql_query=",
        )
        tool_result = await self.mcp_client.call_tool("execute_code", {"query": state.sql_query})
        state.sql_result = extract_tool_text(tool_result)
        if not state.sql_result or "[FAILED]" in state.sql_result:
            logger.warning(
                "SQL execution returned an empty or failed result. sql_result=",
            )
        else:
            logger.info(
                "SQL execution succeeded. sql_result=",
            )

        tool_call_id = "execute_code"
        if state.messages and state.messages[-1].get("tool_calls"):
            tool_call_id = state.messages[-1]["tool_calls"][0].get("id", tool_call_id)

        state.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": state.sql_result,
            }
        )
        return {
            "sql_result": state.sql_result,
            "messages": state.messages,
            **self._token_usage_update(state),
        }

    async def final_formater(self, state: VanillaAgentState) -> Dict[str, Any]:
        question_text = self._get_question_text(state)
        answer_type = self._get_answer_type(question_text)
        logger.info(
            "Formatting final answer for baseline vanilla agent. sql_result="
        )

        messages = [
            {
                "role": "system",
                "content": FORMATER_SYSTEM_PROMPT.replace("{answer_type}", answer_type),
            },
            {
                "role": "user",
                "content": (
                    f"Answer type: [{answer_type}]\n\n"
                    f"Question: {question_text}\n\n"
                    f"SQL Result:\n\n{state.sql_result}"
                ),
            },
        ]

        final_answer = await self.llm.ainvoke(messages)

        state.final_answer = final_answer
        state.messages.append({"role": "assistant", "content": final_answer})
        logger.info(
            "Final answer generated for baseline vanilla agent. final_answer=%s"
        )
        return {
            "final_answer": state.final_answer,
            "messages": state.messages,
            **self._token_usage_update(state),
        }

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(VanillaAgentState)
        workflow.add_node("generate_sql", self.generate_sql)
        workflow.add_node("run_sql", self.run_sql)
        workflow.add_node("final_formater", self.final_formater)
        workflow.set_entry_point("generate_sql")
        workflow.add_edge("generate_sql", "run_sql")
        workflow.add_edge("run_sql", "final_formater")
        workflow.add_edge("final_formater", END)
        return workflow.compile()

    async def ainvoke(self, state: VanillaAgentState) -> VanillaAgentState:
        if not self._initialized:
            await self.initialize()

        logger.info(f"Starting baseline vanilla invocation with thread ID: {self.session_id}")
        result = await self.graph.ainvoke(state)
        if result is None:
            raise ValueError("Workflow execution returned None.")

        if isinstance(result, VanillaAgentState):
            return result

        return VanillaAgentState(**result)
