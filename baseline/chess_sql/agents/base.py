import json
from dataclasses import dataclass, field
from copy import deepcopy
from typing import Awaitable, Callable, Dict, List

from langgraph.graph import END, StateGraph

from agent.core.logger import logger
from baseline.chess_sql.state import ChessSQLAgentState


ToolFn = Callable[[ChessSQLAgentState], Awaitable[str]]


@dataclass
class ChessSubAgentState:
    chess_state: ChessSQLAgentState
    messages: List[Dict] = field(default_factory=list)
    current_iteration: int = 0
    num_tools_calls: int = 0


class ChessSubAgent:
    def __init__(
        self,
        llm,
        current_time: str,
        name: str,
        task: str,
        max_iterations: int = 6,
    ) -> None:
        self.llm = llm
        self.current_time = current_time
        self.name = name
        self.task = task
        self.max_iterations = max_iterations
        self.tool_fns: Dict[str, ToolFn] = {}
        self.tool_descriptions: Dict[str, str] = {}

    @staticmethod
    def _update_token_usage(state: ChessSQLAgentState, response: Dict) -> None:
        if not isinstance(response, dict):
            return

        prompt_tokens = int(response.get("prompt_tokens") or 0)
        completion_tokens = int(response.get("completion_tokens") or 0)

        state.total_tokens = prompt_tokens + completion_tokens
        state.total_prompt_tokens += prompt_tokens
        state.total_output_tokens += completion_tokens

    def build_tools(self) -> List[Dict]:
        tools = []
        for tool_name, description in self.tool_descriptions.items():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": description,
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                    },
                }
            )
        return tools

    def get_state_summary(self, state: ChessSQLAgentState) -> str:
        return (
            f"Question: {state.user_request or state.question}\n"
            f"Keywords: {state.keywords}\n"
            f"Retrieved entities: {state.retrieved_entities}\n"
            f"Retrieved context: {state.retrieved_context}\n"
            f"Selected tables: {state.selected_tables}\n"
            f"Selected columns: {state.selected_columns}\n"
            f"Selected schema: {state.selected_schema}\n"
            f"Candidate SQLs: {state.candidate_sqls}\n"
            f"Current SQL: {state.sql_query}\n"
            f"SQL result: {state.sql_result}\n"
            f"Unit tests: {state.unit_tests}"
        )

    def is_complete(self, state: ChessSQLAgentState) -> bool:
        return False

    async def ainvoke(
        self,
        system_prompt: str,
        user_prompt: str,
        chess_state: ChessSQLAgentState | None = None,
        trace_agent: str | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if chess_state is not None:
            agent_name = trace_agent or self.name
            for message in messages:
                traced_message = deepcopy(message)
                traced_message["agent"] = agent_name
                chess_state.trace_messages.append(traced_message)

        logger.info("%s LLM invoke started", trace_agent or self.name)
        response = await self.llm.ainvoke(messages, detail=True)
        if isinstance(response, dict):
            self._update_token_usage(chess_state, response)
            response_text = response.get("content", "")
        else:
            response_text = response
        if chess_state is not None:
            chess_state.trace_messages.append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "agent": trace_agent or self.name,
                }
            )
        return response_text

    def _initial_messages(self, state: ChessSQLAgentState) -> List[Dict]:
        return [
            {
                "role": "system",
                "content": (
                    f"You are {self.name}, a CHESS-SQL sub-agent.\n"
                    f"Task: {self.task}\n"
                    "Use the provided function tools to update the shared CHESS state. "
                    "When the task is complete, respond without tool calls."
                ),
            },
            {
                "role": "user",
                "content": f"State summary:\n{self.get_state_summary(state)}",
            },
        ]

    def _append_trace_message(self, state: ChessSubAgentState, message: Dict) -> None:
        traced_message = deepcopy(message)
        traced_message["agent"] = self.name
        state.chess_state.trace_messages.append(traced_message)

    async def tool_calling(self, state: ChessSubAgentState) -> ChessSubAgentState:
        if not state.messages:
            state.messages = self._initial_messages(state.chess_state)
            for message in state.messages:
                self._append_trace_message(state, message)

        logger.info("%s tool-calling LLM invoke started", self.name)
        response = await self.llm.tool_calling_async(
            messages=state.messages,
            tools=self.build_tools(),
            detail=True,
        )
        if not isinstance(response, dict):
            response = {"content": str(response), "tool_calls": []}
        else:
            self._update_token_usage(state.chess_state, response)

        assistant_message = {
            "role": "assistant",
            "content": response.get("content") or "",
            **({"tool_calls": response.get("tool_calls")} if response.get("tool_calls") else {}),
        }
        state.messages.append(assistant_message)
        self._append_trace_message(state, assistant_message)
        state.current_iteration += 1
        return state

    async def single_tool_execute(
        self,
        chess_state: ChessSQLAgentState,
        tool_call: Dict,
    ) -> Dict:
        tool_id = tool_call.get("id")
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")

        try:
            if tool_name not in self.tool_fns:
                raise ValueError(f"Unknown tool: {tool_name}")
            arguments = function.get("arguments") or "{}"
            if isinstance(arguments, str):
                try:
                    json.loads(arguments)
                except json.JSONDecodeError:
                    logger.warning(
                        "%s tool %s received invalid JSON arguments; ignoring arguments for state-only tool.",
                        self.name,
                        tool_name,
                    )
            tool_response = await self.tool_fns[tool_name](chess_state)
        except Exception as e:
            logger.exception(f"{self.name} tool {tool_name} failed: {e}")
            tool_response = f"Error executing tool {tool_name}: {e}"

        return {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": tool_response,
        }

    async def tool_execute(self, state: ChessSubAgentState) -> ChessSubAgentState:
        tool_calls = state.messages[-1].get("tool_calls", [])
        for tool_call in tool_calls:
            tool_response = await self.single_tool_execute(state.chess_state, tool_call)
            state.messages.append(tool_response)
            self._append_trace_message(state, tool_response)
        state.num_tools_calls += len(tool_calls)
        return state

    def is_tool_calling_finished(self, state: ChessSubAgentState) -> str:
        if state.current_iteration >= self.max_iterations:
            return "end"
        if self.is_complete(state.chess_state):
            return "end"
        if not state.messages[-1].get("tool_calls"):
            return "end"
        return "continue"

    def build_graph(self) -> StateGraph:
        workflow = StateGraph(ChessSubAgentState)
        workflow.add_node("llm", self.tool_calling)
        workflow.add_node("tools", self.tool_execute)
        workflow.set_entry_point("llm")
        workflow.add_conditional_edges(
            "llm",
            self.is_tool_calling_finished,
            {
                "continue": "tools",
                "end": END,
            },
        )
        workflow.add_edge("tools", "llm")
        return workflow.compile()

    async def run(self, state: ChessSQLAgentState) -> ChessSQLAgentState:
        graph_state = ChessSubAgentState(chess_state=state)
        result = await self.build_graph().ainvoke(graph_state)
        if isinstance(result, ChessSubAgentState):
            return result.chess_state
        return result["chess_state"]
