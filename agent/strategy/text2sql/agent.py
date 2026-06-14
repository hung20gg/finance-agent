from langgraph.graph import StateGraph, START, END
import os
from typing import Dict, Any, AsyncIterable, List


from core.agent import BaseAgentMCP, BaseAgentMCPConfig, conditional_weave_op
from core.logger import logger
from .state import Text2SQLAgentState


current_dir = os.path.dirname(os.path.abspath(__file__))
prompt_path = os.path.join(current_dir, '..', "..", "prompt", "text2sql_system_prompt.md")
with open(prompt_path, "r", encoding="utf-8") as file:
    TEXT2SQL_SYSTEM_PROMPT = file.read()

class Text2SQLAgentConfig(BaseAgentMCPConfig):
    agent_type: str = "text2sql"
    max_tool_calls: int = 8

class Text2SQLAgent(BaseAgentMCP[Text2SQLAgentState, Text2SQLAgentConfig]):
    
    def __init__(self, config: Text2SQLAgentConfig) -> None:
        super().__init__(config=config)
        self.state_class = Text2SQLAgentState

    def _render_system_prompt(self, state: Text2SQLAgentState) -> str:
        # Use direct token replacement so literal braces in the prompt (e.g. \boxed{})
        # are preserved and never interpreted as format placeholders.
        return (
            TEXT2SQL_SYSTEM_PROMPT
            .replace("{current_time}", str(state.current_time))
            .replace("{maximum_iterations}", str(self.config.max_tool_calls))
        )

    async def _run_preprocessors(self, state: Text2SQLAgentState) -> List[str]:
        """Auto-inject RAG examples on the first iteration (Option C).
        
        The get_example_sql tool remains available for the LLM to call
        manually in subsequent iterations if it needs examples for a
        refined or different query.
        """
        parts = []
        if await self.mcp_client.has_tool("get_example_sql"):
            try:
                tool_result = await self.mcp_client.call_tool(
                    "get_example_sql", {"query": state.user_request}
                )
                example_sql = tool_result.content[0].text
                parts.append(
                    f"Example SQL to solve the problem:\n"
                    f"<Example_sql>{example_sql}</Example_sql>"
                )
            except Exception as e:
                logger.warning(f"Failed to auto-inject example SQL: {e}")
        return parts

    @conditional_weave_op(call_display_name="Text2SQL Tool Calling")
    async def tool_calling(self, state: Text2SQLAgentState) -> Text2SQLAgentState:
        
        
        
        if len(state.messages) == 0:
            
            state.messages.append(
                {
                    "role": "system",
                    "content": self._render_system_prompt(state)
                }
            )
        if state.messages[0]['role'] != 'system':
            state.messages.insert(0,
                {
                    "role": "system",
                    "content": self._render_system_prompt(state)
                }
            )

        if state.current_iteration == 0:
            print(f"[DEBUG] Messages before tool calling: {state.user_request}")

            user_prompt = state.user_request

            # Run configurable preprocessors (auto-inject context before LLM)
            context_parts = await self._run_preprocessors(state)
            if context_parts:
                user_prompt = f"## User request:\n\n<User_request>{state.user_request}</User_request>\n\n"
                user_prompt += "\n\n".join(context_parts)

            state.messages.append(
                {
                    "role": "user",
                    "content": user_prompt
                }
            )

        state.current_iteration += 1
        return await super().tool_calling(state)


    @conditional_weave_op(call_display_name="Finalize Text2SQL Agent State")
    async def finalize(self, state: Text2SQLAgentState) -> Text2SQLAgentState:

        state.current_iteration = 0  # Reset iteration for next invocation
        return await super().finalize(state)

    def build_graph(self) -> StateGraph:

        workflow = StateGraph(Text2SQLAgentState)

        workflow.add_node('llm', self.tool_calling)
        workflow.add_node("tools", self.tool_execute)
        workflow.add_node("finalize", self.finalize)

        workflow.set_entry_point("llm")
        workflow.add_conditional_edges(
            "llm",
            self.is_tool_calling_finished,
            {
                'end': 'finalize',
                'continue': 'tools'
            }

        )
        workflow.add_edge("tools", "llm")
        workflow.add_edge("finalize", END)
        graph = workflow.compile()

        return graph

    @conditional_weave_op(call_display_name="Invoke Text2SQL Agent")
    async def ainvoke(self, state: Text2SQLAgentState) -> Text2SQLAgentState:
        return await super().ainvoke(state)
    
    @conditional_weave_op(call_display_name="Stream Text2SQL Agent")
    async def astream(self, state: Text2SQLAgentState, stream_mode="custom") -> AsyncIterable[Dict[str, Any]]:
        async for chunk in super().astream(state, stream_mode=stream_mode):
            yield chunk
