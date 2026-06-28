from typing import Any, Dict

from agent.core.mcp_client import MCPClient
from baseline.utils import extract_tool_text


class ChessMCPTools:
    """Restricted MCP wrapper for CHESS-SQL.

    Only `get_table_metadata` and `execute_code` are allowed here.
    """

    def __init__(self, mcp_client: MCPClient) -> None:
        self.mcp_client = mcp_client

    async def get_table_metadata(self, table_name: str) -> str:
        tool_result = await self.mcp_client.call_tool(
            "get_table_metadata",
            {"table_name": table_name},
        )
        return extract_tool_text(tool_result)

    async def execute_code(self, query: str) -> str:
        tool_result = await self.mcp_client.call_tool(
            "execute_code",
            {"query": query},
        )
        return extract_tool_text(tool_result)

    async def call(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if tool_name == "get_table_metadata":
            return await self.get_table_metadata(arguments["table_name"])
        if tool_name == "execute_code":
            return await self.execute_code(arguments["query"])
        raise ValueError(f"CHESS-SQL cannot call MCP tool: {tool_name}")
