import os
from agent.llm import get_llm_wrapper
from agent.core.mcp_client import MCPClient
from agent.core.state import AgentState

from uuid import uuid4
from typing import Optional
from langgraph.graph import StateGraph
from langgraph.config import get_stream_writer
import json
from typing import List, Dict, Any, AsyncIterable, Annotated, TypeVar, Generic
from pydantic import BaseModel, Field
from datetime import datetime, date
from dotenv import load_dotenv
import asyncio


load_dotenv()

from agent.core.logger import logger

import contextlib

weave_trace_enabled = os.getenv("WEAVE_TRACE_ENABLED", "false").lower() == "true"

if weave_trace_enabled:
    import wandb
    import weave
    
    WANDB_API_KEY = os.getenv("WANDB_API_KEY")
    WANDB_NAME = os.getenv("WANDB_NAME", "neu-solution/kltn")
    if WANDB_API_KEY:
        wandb.login(key=WANDB_API_KEY)
    weave.init(WANDB_NAME)

def conditional_weave_op(*args, **kwargs):
    def decorator(func):
        if weave_trace_enabled:
            return weave.op(*args, **kwargs)(func)
        return func
    return decorator

@contextlib.contextmanager
def dummy_context_manager(*args, **kwargs):
    yield None

weave_thread = weave.thread if weave_trace_enabled else dummy_context_manager
weave_attributes = weave.attributes if weave_trace_enabled else dummy_context_manager

class BaseAgentMCPConfig(BaseModel):
    agent_type: str = "base"
    model_name: str
    urls: Optional[List[str]] = None
    streaming: bool = False
    message_saver: Optional[str] = None
    max_tool_calls: int = 10
    remove_think_tag: bool = False

    
StateT = TypeVar("StateT", bound=AgentState)
ConfigT = TypeVar("ConfigT", bound=BaseAgentMCPConfig)

def remove_think_tag_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for message in messages:
        if message.get("role") == "assistant":
            if isinstance(message.get("content"), str):
                message["content"] = message["content"].split('</think>')[-1]

            if isinstance(message.get("content"), list):
                for content in message["content"]:
                    if isinstance(content.get("text"), str):
                        content["text"] = content["text"].split('</think>')[-1]
    return messages

class BaseAgentMCP(Generic[StateT, ConfigT]):
    def __init__(self, config: ConfigT) -> None:
        logger.info(f"Initializing agent with config: {config}")
        self.config = config
        self.llm = self.initialize_llm(config.model_name)
        self.mcp_client = MCPClient(config.urls)
        self._initialized = False
        self.graph = self.build_graph()
        self.streaming: bool = config.streaming
        self.session_id: str = str(uuid4())
        self.tools: List[Dict[str, Any]] = []
        self.state_class = StateT


    def initialize_llm(self, model_name: str):
        """Initialize a separate LLM instance, e.g. for evaluation"""
        return get_llm_wrapper(model_name)


    async def initialize(self) -> None:
        """Initialize async components"""
        if not self._initialized:
            await self.mcp_client.initialize()
            self._initialized = True
        
        self.tools = self.mcp_client.tools
        # print(json.dumps(self.tools))

    def add_tools(self, tool: Dict[str, Any]) -> None:
        """Add a tool to the agent's tool list"""
        self.tools.append(tool)

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass


    def is_tool_calling_finished(self, state: StateT) -> str:

        if state.num_tools_calls >= self.config.max_tool_calls:
            logger.warning(f"Maximum number of tool calls ({self.config.max_tool_calls}) reached. Skipping tool execution.")
            return 'end'
        
        if len(state.messages[-1].get("tool_calls", [])) == 0:
            return 'end'
        return 'continue'
    
    async def single_tool_execute(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        
        tool_id = None
        tool_response = None
        
        try:
            tool_id = tool_call.get("id")
            function = tool_call.get("function", {})
            function_name = function.get("name")
            logger.info(f"[FUNCTION]: {function_name} {function.get('arguments')}")
            arguments = json.loads(function.get("arguments"))
          
            tool_result = await self.mcp_client.call_tool(function_name, arguments)
            
            #post-process tool result
            response = tool_result.content[0].text
            if response.startswith('{') or response.startswith('['):
                try:
                    response = json.loads(response)
                except json.JSONDecodeError:
                    pass  # Keep original text if JSON parsing fails

                tool_response = json.dumps(response, ensure_ascii=False)
            else:
                tool_response = response or "[ERROR] Tool execution was blocked due to invalid parameters.\n\n"
        
        except Exception as e:          
            logger.exception(f"Error executing tool {function_name}: {e}")
            tool_response = f"Error executing tool {function_name}: {e}"
        
        return {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": tool_response
        }
    
    async def _tool_execute(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tool_responses = []
        tool_responses = await asyncio.gather(*[
            self.single_tool_execute(tool_call) for tool_call in tool_calls
        ])

        return tool_responses


    @conditional_weave_op(call_display_name="Tool Execute")
    async def tool_execute(self, state: StateT) -> StateT:

        tool_response_messages = await self._tool_execute(state.messages[-1].get("tool_calls", []))
        state.messages.extend(tool_response_messages)
        state.num_tools_calls += len(tool_response_messages)
        return state
    

    async def _tool_calling(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:

        content = ""
        tool_calls = []

        if self.config.remove_think_tag:
            messages = remove_think_tag_from_messages(messages)
        
        if not self.streaming:
            tool_responses = await self.llm.tool_calling_async(messages=messages, tools = tools)
            if isinstance(tool_responses, dict):
                content = tool_responses.get('content')
                tool_calls = tool_responses.get('tool_calls')
        else:
            # Get stream writer inside the graph execution context
            stream_writer = get_stream_writer()
            

            try:
                async for chunk in self.llm.stream_tool_calling_async(messages, tools = tools):
                    if isinstance(chunk, dict) and chunk.get('type') == 'content':
                        content += chunk.get('content', '')
                        stream_writer({'type': 'content', 'content': chunk.get('content', ''), 'agent': self.config.agent_type})

                    elif isinstance(chunk, dict) and chunk.get('type') == 'function':
                        tool_calls.append(chunk)
                        stream_writer({'type': 'log', 'log': 'Identified tool call: ' + str(chunk) + '\n', 'agent': self.config.agent_type})
            except Exception as e:
                print(e)

        result = {'content': content}
        if tool_calls:
            result['tool_calls'] = tool_calls
        return result
        
    @conditional_weave_op(call_display_name="Invoke")
    async def llm_ainvoke(self, messages) -> str:
        
        content = ""
        
        if not self.streaming:
            content = await self.llm.ainvoke(messages)

        else:
            # Get stream writer inside the graph execution context
            stream_writer = get_stream_writer()
            async for text in self.llm.astream(messages):
                content += text
                stream_writer({'type': 'content', 'content': text, 'agent': self.config.agent_type})
                
        return content
        


    async def _run_preprocessors(self, state: StateT) -> List[str]:
        """Run pre-LLM context enrichment hooks.
        
        Override in subclasses to inject additional context (e.g. RAG examples,
        entity resolution results) into the user prompt before the first LLM call.
        
        Args:
            state: The current agent state.
        
        Returns:
            A list of context strings to append to the user prompt.
            Empty list means no preprocessing.
        """
        return []


    @conditional_weave_op(call_display_name="Tool Calling")
    async def tool_calling(self, state: StateT) -> StateT:

        tool_calling_result = await self._tool_calling(messages=state.messages, tools=self.tools)
        
        state.messages.append({
            'role': "assistant",
            **tool_calling_result
        })

        return state
    

    @conditional_weave_op(call_display_name="Finalize Agent State")
    async def finalize(self, state: StateT) -> StateT:
        if self.streaming:
            stream_writer = get_stream_writer()
            stream_writer({'type': 'state', 'state': state})
        return state


    def reload_state(self, state_dict: Dict[str, Any]) -> StateT:
        return self.state_class(**state_dict)

            
    def build_graph(self) -> Optional[StateGraph]:
        return None

    @conditional_weave_op(call_display_name="Invoke Agent")
    async def ainvoke(self, state: StateT) -> StateT:

        if not self.graph:
            raise ValueError("Workflow graph is not defined.")
        
        # Run the workflow
        with weave_thread(self.session_id) as thread_ctx:
            with weave_attributes({'type': 'non-stream', 'Agent': self.config.agent_type}):
                logger.info(f"Starting agent invocation with thread ID: {self.session_id}")
                result  = await self.graph.ainvoke(state)
                if result is None:
                    raise ValueError("Workflow execution returned None.")

        return type(state)(**result)

    @conditional_weave_op(call_display_name="Stream Agent")
    async def astream(self, state: StateT, stream_mode="custom") -> AsyncIterable[Dict[str, Any]]:
        
        if not self.graph:
            raise ValueError("Workflow graph is not defined.")
       
        with weave_thread(self.session_id) as thread_ctx:
            with weave_attributes({'type': 'stream', 'Agent': self.config.agent_type}):
                logger.info(f"Starting agent invocation with thread ID: {self.session_id}")
                
                async for chunk in self.graph.astream(state, stream_mode=stream_mode):
                    yield chunk
        

