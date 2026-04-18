import os
from client import PostgresClient
from logger import logger
import pandas as pd
import anyio
from uuid import uuid4
from utils import df_to_markdown



async def tool_execute_code(client: PostgresClient, query: str, limit: int) -> str:
    
    _id = str(uuid4())
    results = await client.aexecute_query(query)
    df = pd.DataFrame([dict(row) for row in results])

    if df.empty:
        return f"SQL ID {_id}:\n\n[FAILED] No data found for the given query."
    
    return f"SQL ID {_id}:\n\n[SUCCESS] Query results:\n\n{df_to_markdown(df[:limit])}"


def register_tool(mcp, client: PostgresClient):
    
    @mcp.tool()
    async def execute_code(query: str) -> str:
        """
        Run the provided SQL query and return the results in a markdown table format. The results will be limited to the first 50 rows to prevent overwhelming the user with too much data.
        
        Returns:
            Query results as a string or error message
        """
        limit = 50
        return await tool_execute_code(client, query, limit)