from fastmcp import Client
import fastmcp
from typing import Dict, List, Any, Optional
import asyncio
import os
from uuid import uuid4
from .env_config import load_env_config, get_env

# Load environment configuration
load_env_config()

def _fastmcp_to_openai_tools(tools) -> list:
    openai_tools = []
    
    for tool in tools:
        tool = tool.model_dump()
        openai_tool = {
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description"),
                "parameters": tool.get("inputSchema", {}),
            }
        }
        openai_tools.append(openai_tool)
    return openai_tools

class MCPClient:
    def __init__(self, urls: Optional[List[str]] = None) -> None:
        if urls is None:
            url = get_env("MCP_SERVER_URL")
            urls = [url] if url else []
        self.clients = [Client(url) for url in urls]
        self.mapping_client_tools: Dict[str, int] = {}
        self.tools: Optional[List[Dict[str, Any]]] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the client and load tools"""
        if not self._initialized:
            if not self.clients:
                # Handle empty URLs case
                self.tools = []
                self._initialized = True
            else:
                for i, self.client in enumerate(self.clients):
                    try:
                        async with self.client:
                            tools = await self.client.list_tools()
                            self.tools = _fastmcp_to_openai_tools(tools)
                            for tool in tools:
                                self.mapping_client_tools[tool.name] = i
                    except Exception as e:
                        from .logger import logger
                        logger.warning(f"Failed to connect to MCP server at index {i}: {e}. Continuing without these tools.")
                        if not self.tools:
                            self.tools = []
                self._initialized = True

    async def _ensure_initialized(self) -> None:
        """Ensure client is initialized before use"""
        if not self._initialized:
            await self.initialize()

    async def has_tool(self, tool_name: str) -> bool:
        await self._ensure_initialized()
        client_index = self.mapping_client_tools.get(tool_name)
        if client_index is None:
            return False
        return True

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        await self._ensure_initialized()
        client_index = self.mapping_client_tools.get(tool_name)
        if client_index is None:
            raise ValueError(f"Tool '{tool_name}' not found in any MCP client")
        
        async with self.clients[client_index]:
            return await self.clients[client_index].call_tool(tool_name, params)

    def call_tool_sync(self, function_name: str, arguments: dict):
        """Synchronous wrapper for call_tool"""
        return asyncio.run(self.call_tool(function_name, arguments))
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get tools (must call initialize first)"""
        if not self._initialized:
            raise RuntimeError("MCPClient not initialized. Call await client.initialize() first")
        return self.tools