import os
from client import PostgresClient
from logger import logger
import pandas as pd
import anyio

async def query_commodities_available(client: PostgresClient) -> str:

    query = """
        SELECT DISTINCT indicator_code, indicator_name
        FROM commodities_daily
        ORDER BY indicator_code
    """
    logger.info(f"Querying available commodities")
    results = await client.aexecute_query(query)
    df = pd.DataFrame([dict(row) for row in results])
    if df.empty:
        return "[FAIL] No commodities data found. The commodities data might not be available in the database."
    
    return f"[SUCCESS] Available commodities:\n\n{df.to_markdown(index=False)}"


def register_tool(mcp, client: PostgresClient):

    @mcp.tool()
    async def get_commodities_available() -> str:
        """
        Fetch available commodities to provide filtering options for `get_commodities_value`.
        
        Returns:
            Available commodities
        """
        return await query_commodities_available(client)