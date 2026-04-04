from langgraph.graph import StateGraph, START, END
import os
from typing import Dict, Any, AsyncIterable, Optional, Tuple
import json
import asyncio
import re

from core.agent import BaseAgentMCP, BaseAgentMCPConfig, conditional_weave_op
from core.logger import logger
from .state import BIAgentState
from .const import TEXT2SQL_TOOL, TEXT2CHART_TOOL, TEXT2SQL_TOOL_NAME, TEXT2CHART_TOOL_NAME
from ..text2sql.agent import Text2SQLAgentConfig, Text2SQLAgent
from ..text2sql.state import Text2SQLAgentState
from ..text2chart.state import Text2ChartAgentState
from ..text2chart.agent import Text2ChartAgentConfig, Text2ChartAgent

current_dir = os.path.dirname(os.path.abspath(__file__))
prompt_path = os.path.join(current_dir, '..', "..", "prompt", "bi_react_system_prompt.md")
with open(prompt_path, "r", encoding="utf-8") as file:
    BI_AGENT_SYSTEM_PROMPT = file.read()

class BIAgentConfig(BaseAgentMCPConfig):
    agent_type: str = "bi_agent"
    max_tool_calls: int = 10
    sql_generator_config: Optional[Text2SQLAgentConfig] = None
    chart_generator_config: Optional[Text2ChartAgentConfig] = None
    text2sql_agent_config: Optional[Text2SQLAgentConfig] = None
    text2chart_agent_config: Optional[Text2ChartAgentConfig] = None


def extract_answer_from_sql_response(text: str) -> Any:
    """
    Extracts:
    - \\boxed{value} → returns value
    - JSON block (with or without ```json) → returns dict
    """

    # 1. Try to extract \boxed{}
    boxed_match = re.search(r'\\boxed\{([^}]*)\}', text)
    if boxed_match:
        value = boxed_match.group(1).strip()

        # Try to parse number if possible
        try:
            return json.loads(value)
        except:
            return value

    # 2. Try to extract ```json block
    json_block_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Try to extract ANY JSON-like object
    json_match = re.search(r'(\{.*\})', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    return None

class BIAgent(BaseAgentMCP[BIAgentState, BIAgentConfig]):
    
    def __init__(self, config: BIAgentConfig) -> None:
        super().__init__(config=config)
        
        if not self.config.sql_generator_config and self.config.text2sql_agent_config:
            self.config.sql_generator_config = self.config.text2sql_agent_config

        if not self.config.chart_generator_config and self.config.text2chart_agent_config:
            self.config.chart_generator_config = self.config.text2chart_agent_config

        if self.config.sql_generator_config:
            self.sql_generator = Text2SQLAgent(self.config.sql_generator_config)
        if self.config.chart_generator_config:
            self.chart_generator = Text2ChartAgent(self.config.chart_generator_config)
        
    async def initialize(self):
        await super().initialize()
        if self.config.sql_generator_config:
            await self.sql_generator.initialize()
        if self.config.chart_generator_config:
            await self.chart_generator.initialize()

        self.tools = [
            TEXT2SQL_TOOL,
            TEXT2CHART_TOOL
        ]


    @conditional_weave_op(call_display_name="ReAct Tool Calling")
    async def tool_calling(self, state: BIAgentState) -> BIAgentState:
        
        if len(state.messages) == 0:
            state.messages.append(
                {
                    "role": "system",
                    "content": BI_AGENT_SYSTEM_PROMPT.format(
                        current_time=state.current_time,
                        maximum_iterations=self.config.max_tool_calls
                    )
                }
            )
        if state.messages[0]['role'] != 'system':
            state.messages.insert(0,
                {
                    "role": "system",
                    "content": BI_AGENT_SYSTEM_PROMPT.format(
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

        print(json.dumps(state.messages[1:], indent=2, ensure_ascii=False))
        return await super().tool_calling(state)
    
    async def text2sql_tool_execute(self, state: BIAgentState, tool_call: Dict[str, Any]) -> Tuple[str, Text2SQLAgentState]:

        arguments = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
        
        request = arguments.get("request", "")
        columns = arguments.get("columns", [])
        query_mode = arguments.get("query_mode", "any")

        request += f" [{query_mode}]"  # Append query mode to the request for better understanding of expected output format by the agent
        if len(columns) != 0:
            request += f"\n\nThe expected output should contain the following columns: {', '.join(columns)}."
        
        sql_agent_state = state.text2sql_state
        sql_agent_state.user_request = request
        sql_agent_state = await self.sql_generator.ainvoke(sql_agent_state)
        response = sql_agent_state.messages[-1].get("content", "")
        state.text2sql_state = sql_agent_state

        tool_response = extract_answer_from_sql_response(response)
        if isinstance(tool_response, (list, dict)):
            tool_response = json.dumps(tool_response, ensure_ascii=False)
        
        return tool_response, state

    async def text2chart_tool_execute(self, state: BIAgentState, tool_call: Dict[str, Any]) -> Tuple[str, Text2ChartAgentState]:

        arguments = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
        
        request = arguments.get("request", "")
        data = arguments.get("data", [])
        chart_type = arguments.get("chart_type", "")

        chart_agent_state = state.text2chart_state
        chart_agent_state.user_request = request
        chart_agent_state.data = data
        chart_agent_state.chart_type = chart_type

        chart_agent_state = await self.chart_generator.ainvoke(chart_agent_state)
        tool_response = chart_agent_state.messages[-1].get("content", "")

        state.text2chart_state = chart_agent_state
        
        return tool_response, state


    async def single_tool_execute(self, state: BIAgentState, tool_call: Dict[str, Any]) -> Tuple[Dict[str, Any], BIAgentState]:

        tool_id = None
        tool_response = None
        
        try:
            function = tool_call.get("function", {})
            function_name = function.get("name")
            logger.info(f"[AGENT_CALL]: {function_name} {function.get('arguments')}")
          
            if function_name == TEXT2SQL_TOOL_NAME:
                tool_response, sql_agent_state = await self.text2sql_tool_execute(state, tool_call)
                state.text2sql_state = sql_agent_state

            if function_name == TEXT2CHART_TOOL_NAME:
                tool_response, chart_agent_state = await self.text2chart_tool_execute(state, tool_call)
                state.text2chart_state = chart_agent_state

            print(f"[TOOL RESPONSE]: {tool_response}")


        except Exception as e:          
            logger.error(f"Error executing tool: {e}")
            tool_response = f"Error executing tool: {e}"
        
        return {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": tool_response
        }, state

    @conditional_weave_op(call_display_name="Tool Execute")
    async def tool_execute(self, state: BIAgentState) -> BIAgentState:

        tool_calls = state.messages[-1].get("tool_calls", [])
        
        for tool_call in tool_calls:
            tool_response_message, state = await self.single_tool_execute(state, tool_call)
            state.messages.append(tool_response_message)
            state.num_tools_calls += 1
                
        return state
    

    @conditional_weave_op(call_display_name="Finalize React Agent State")
    async def finalize(self, state: BIAgentState) -> BIAgentState:

        state.current_iteration = 0  # Reset iteration for next invocation
        return await super().finalize(state)


    def build_graph(self) -> StateGraph:

        workflow = StateGraph(BIAgentState)

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
    async def ainvoke(self, state: BIAgentState) -> BIAgentState:
        return await super().ainvoke(state)
    
    @conditional_weave_op(call_display_name="Stream ReAct Agent")
    async def stream(self, state: BIAgentState, stream_mode="custom") -> AsyncIterable[Dict[str, Any]]:
        async for chunk in super().stream(state, stream_mode=stream_mode):
            yield chunk
