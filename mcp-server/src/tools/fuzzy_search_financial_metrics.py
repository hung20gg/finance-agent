import os
from client import PostgresClient
from logger import logger
import pandas as pd
import anyio
import re


MAP_TABLE_COLUMN = {
    'category_code': {
        'table_name': 'financial_statement_dim',
        'column_names': ['category_name', 'category_code'],
        'return_columns': ['category_code', 'category_name']
    },
    'ratio_code': {
        'table_name': 'financial_ratio_dim',
        'column_names': ['ratio_name', 'ratio_code'],
        'return_columns': ['ratio_code', 'ratio_name']
    },
    'stock_code': {
        'table_name': 'company_info',
        'column_names': ['stock_code', 'company_name'],
        'return_columns': ['stock_code', 'company_name']
    }
}


async def fuzzy_search_values(
    client: PostgresClient,
    table_name: str,
    search_value: str,
    limit: int = 10
) -> str:
    
    if table_name not in MAP_TABLE_COLUMN:
        return f"Table '{table_name}' is not supported for fuzzy search. Supported tables: {', '.join(MAP_TABLE_COLUMN.keys())}."
    
    source_table = MAP_TABLE_COLUMN[table_name]['table_name']
    column_names = MAP_TABLE_COLUMN[table_name]['column_names']
    return_columns = MAP_TABLE_COLUMN[table_name]['return_columns']

    sql = f"""
WITH scored AS (
SELECT DISTINCT
    {', '.join(return_columns)},

    (
        -- full text search (primary)
        GREATEST({', '.join([
            f"""
            ts_rank(
                to_tsvector('simple', {col}),
                plainto_tsquery('simple', %(keyword)s)
            )
            """
            for col in column_names
        ])})

        +

        -- keyword containment (VERY IMPORTANT)
        GREATEST({', '.join([
            f"""
            CASE 
                WHEN lower({col}) LIKE '%%' || lower(%(keyword)s) || '%%' THEN 0.75
                ELSE 0
            END
            """
            for col in column_names
        ])})

        +

        -- prefix bonus
        GREATEST({', '.join([
            f"""
            CASE 
                WHEN lower({col}) LIKE lower(%(keyword)s) || '%%' THEN 0.25
                ELSE 0
            END
            """
            for col in column_names
        ])})

        +

        -- weak levenshtein fallback
        0.5 * GREATEST({', '.join([
            f"""
            1.0 - levenshtein(
                lower({col}),
                lower(%(keyword)s)
            )::float
            / GREATEST(length({col}), length(%(keyword)s))
            """
            for col in column_names
        ])})

    ) AS score

FROM {source_table}
)

SELECT *
FROM scored
WHERE score > 0.05
ORDER BY score DESC
LIMIT 10;
"""
    search_pattern = f"%{search_value}%"

    cols_str = ", ".join(column_names)
    logger.info(f"Performing fuzzy search for '{search_value}' in {source_table}.[{cols_str}]")

    try:
        params = {
            "keyword": search_value,                 # raw keyword
            "search_pattern": f"%{search_value}%",
            "prefix": f"{search_value}%",
            "suffix": f"%{search_value}",
            "limit": limit
        }
        results = await client.aexecute_query(sql, params=params)
        if not results:
            return f"No matches found for '{search_value}':"

        df = pd.DataFrame([dict(row) for row in results])
        df_string = df.to_markdown(index=False)
        return f"Fuzzy search results for '{search_value}':\n\n{df_string}"

    except Exception as e:
        logger.error(f"Error performing fuzzy search: {e}")
        return f"[FAIL] Error performing fuzzy search: {e}"
    


def register_tool(mcp, client: PostgresClient):
    
    @mcp.tool()
    
    async def fuzzy_search_financial_metrics( query: str, field: str) -> str:
        """
        This tool helps to find the exact financial ratio code/ category code/ stock code for financial metrics based on a user query.
        It supports fuzzy search on name/description fields, and specifically for stock_code, it also searches the stock_code field.

        Args:
            query: User query to find the exact financial ratio code. Must be in English.
            field: The field to search in, either 'category_code', 'ratio_code', or 'stock_code'.
        Returns:
            Financial code as a string or error message
        """
        return await fuzzy_search_values(client, field, query)
    
