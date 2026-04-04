from langgraph.graph import StateGraph, START, END
import os
from typing import Dict, Any, AsyncIterable


from core.agent import BaseAgentMCP, BaseAgentMCPConfig, conditional_weave_op
from core.logger import logger
from .state import ReActAgentState


current_dir = os.path.dirname(os.path.abspath(__file__))
prompt_path = os.path.join(current_dir, '..', "..", "prompt", "react_system_prompt.md")
with open(prompt_path, "r", encoding="utf-8") as file:
    REACT_SYSTEM_PROMPT = file.read()

class ReActAgentConfig(BaseAgentMCPConfig):
    agent_type: str = "react"
    max_tool_calls: int = 10

class ReActAgent(BaseAgentMCP[ReActAgentState, ReActAgentConfig]):
    
    def __init__(self, config: ReActAgentConfig) -> None:
        super().__init__(config=config)

    @conditional_weave_op(call_display_name="ReAct Tool Calling")
    async def tool_calling(self, state: ReActAgentState) -> ReActAgentState:
        
        if len(state.messages) == 0:
            state.messages.append(
                {
                    "role": "system",
                    "content": REACT_SYSTEM_PROMPT.format(
                        current_time=state.current_time,
                        maximum_iterations=self.config.max_tool_calls
                    )
                }
            )
        if state.messages[0]['role'] != 'system':
            state.messages.insert(0,
                {
                    "role": "system",
                    "content": REACT_SYSTEM_PROMPT.format(
                        current_time=state.current_time,
                        maximum_iterations=self.config.max_tool_calls
                    )
                }
            )

        if state.current_iteration == 0:
            
            state.messages.append(
                {
                    "role": "user",
                    "content": state.user_request
                }
            )

        state.current_iteration += 1
        return await super().tool_calling(state)

    @conditional_weave_op(call_display_name="Finalize React Agent State")
    async def finalize(self, state: ReActAgentState) -> ReActAgentState:

        state.current_iteration = 0  # Reset iteration for next invocation
        return await super().finalize(state)


    def build_graph(self) -> StateGraph:

        workflow = StateGraph(ReActAgentState)

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

    @conditional_weave_op(call_display_name="Invoke ReAct Agent")
    async def ainvoke(self, state: ReActAgentState) -> ReActAgentState:
        return await super().ainvoke(state)
    
    @conditional_weave_op(call_display_name="Stream ReAct Agent")
    async def stream(self, state: ReActAgentState, stream_mode="custom") -> AsyncIterable[Dict[str, Any]]:
        async for chunk in super().stream(state, stream_mode=stream_mode):
            yield chunk
