import os
from client import PostgresClient
import anyio
from logger import logger

async def tool_get_table_metadata(client: PostgresClient, table_name: str) -> str:
    
    return client.table_details.get(table_name, f"No metadata found for table {table_name}.")



def register_tool(mcp, client: PostgresClient):
    
    @mcp.tool()
    async def get_table_metadata(table_name: str) -> str:
        """
        Get metadata information for a specific table, including column names and data types.
        
         Args:
             table_name: The name of the table to retrieve metadata for.
         Returns:
             Metadata information as a string or error message
         """
        logger.info("get_table_metadata")
        return await tool_get_table_metadata(client, table_name)