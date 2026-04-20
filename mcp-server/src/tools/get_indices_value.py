import os
from client import PostgresClient
from logger import logger
import pandas as pd
from utils import df_to_markdown


def _load_indices_available(client: PostgresClient) -> str:
    """Load available indices using a synchronous connection (safe at startup)."""
    query = """
        SELECT DISTINCT index_name
        FROM indices_daily
        ORDER BY index_name
    """
    logger.info("Querying available indices (sync startup)")
    results = client.execute_query(query)
    df = pd.DataFrame([dict(row) for row in results])
    if df.empty:
        return "[FAILED] No indices data found. The indices data might not be available in the database."
    return f"[SUCCESS] Available indices:\n\n{df_to_markdown(df)}"


def register_tool(mcp, client: PostgresClient):

    available_indices = _load_indices_available(client)

    @mcp.tool()
    async def get_indices_available() -> str:
        """
        Fetch available stock indices from BigQuery.
        
        Returns:
            Available indices as a string or error message
        """
        return available_indices