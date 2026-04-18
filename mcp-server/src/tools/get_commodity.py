import os
from client import PostgresClient
from logger import logger
import pandas as pd
import anyio
from utils import df_to_markdown


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
    
    return f"[SUCCESS] Available commodities:\n\n{df_to_markdown(df)}"


def register_tool(mcp, client: PostgresClient):

    available_commodities = anyio.run(query_commodities_available, client)

    @mcp.tool()
    async def get_commodities_available() -> str:
        """
        Fetch available commodities to provide filtering options for `get_commodities_value`.
        
        Returns:
            Available commodities
        """
        return available_commodities