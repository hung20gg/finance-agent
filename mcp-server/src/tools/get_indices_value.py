import os
from client import PostgresClient
from logger import logger
import pandas as pd
import anyio


async def query_indices_available(client: PostgresClient) -> str:
    
    query = """
        SELECT DISTINCT index_name
        FROM indices_daily
        ORDER BY index_name
    """
    logger.info(f"Querying available indices")
    results = await client.aexecute_query(query)
    df = pd.DataFrame([dict(row) for row in results])
    if df.empty:
        return "[FAILED] No indices data found. The indices data might not be available in the database."
    
    return f"[SUCCESS] Available indices:\n\n{df.to_markdown(index=False)}"


def register_tool(mcp, client: PostgresClient):
    
    @mcp.tool()
    async def get_indices_available() -> str:
        """
        Fetch available stock indices from BigQuery.
        
        Returns:
            Available indices as a string or error message
        """
        return await query_indices_available(client)