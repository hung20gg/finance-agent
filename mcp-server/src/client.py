import psycopg
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from collections import defaultdict
from logger import logger
import os
from typing import List, Optional
import asyncio
from env_config import get_env
import pandas as pd
from utils import df_to_markdown

class PostgresClient:
    """Client for authenticating and interacting with PostgreSQL."""
    
    def __init__(self, postgres_url: Optional[str]):
        """
        Initialize Postgres client with connection pool.
        
        Args:
            postgres_url: PostgreSQL connection URL
        """
        self.postgres_url = postgres_url or get_env('POSTGRES_URL')
        if not self.postgres_url:
            raise ValueError("POSTGRES_URL is not provided or set in env variables.")
            
        self.pool = AsyncConnectionPool(conninfo=self.postgres_url, open=False, kwargs={"row_factory": dict_row})
        self._pool_opened = False
        self.tables_names = [
            'commodities_daily',
            'indices_daily',
            'stock_daily',
            'financial_ratio',
            'financial_statement',
            'company_info'
        ]
        self.table_details = defaultdict(str)

        for table in self.tables_names:
            details = self._load_table_details(table)
            logger.info(f"Loaded details for table {table}")

    async def _ensure_pool(self):
        if not self._pool_opened:
            await self.pool.open()
            self._pool_opened = True

    def test_connection(self) -> bool:
        """Test the PostgreSQL connection synchronously."""
        try:
            with psycopg.connect(self.postgres_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"PostgreSQL connection test failed: {e}")
            return False
            
    def execute_query(self, query: str, params: Optional[dict] = None) -> List[dict]:
        """Execute a SQL query synchronously and return the results."""
        try:
            with psycopg.connect(self.postgres_url, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    if cur.description:
                        return cur.fetchall()
                    return []
        except Exception as e:
            logger.error(f"Sync query error: {e}")
            raise
    
    async def aexecute_query(self, query: str, params: Optional[dict] = None) -> List[dict]:
        """Execute a SQL query asynchronously and return the results."""
        await self._ensure_pool()
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                if cur.description:
                    return await cur.fetchall()
                return []
            

    def _load_table_details(self, table_name: str) -> str:

        query = """
            SELECT 
                column_name, 
                dtype, 
                dtype, 
                explaination
            FROM master_data_catalog
            WHERE table_name = %s
         """
        
        open_table_query = f"SELECT * FROM {table_name} LIMIT 2"
        
        try:
            results = self.execute_query(query, params=(table_name,))
            if not results:
                logger.warning(f"No details found for table {table_name} in master_data_catalog.")
                return f"No details found for table {table_name}."
            
            df = pd.DataFrame(results)
            details_str = df_to_markdown(df)

            open_table_results = self.execute_query(open_table_query)
            if open_table_results:
                open_table_df = pd.DataFrame(open_table_results)
                details_str += "\n\nSample data:\n\n" + df_to_markdown(open_table_df)

            self.table_details[table_name] = details_str
            return details_str
        except Exception as e:
            logger.error(f"Error loading table details for {table_name}: {e}")
            return f"Error loading table details for {table_name}: {e}"


