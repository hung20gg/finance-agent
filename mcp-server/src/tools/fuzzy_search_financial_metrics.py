# import os
# from client import PostgresClient
# from logger import logger
# import pandas as pd
# import anyio
# import re
# from rapidfuzz import fuzz, process
# from utils import df_to_markdown

# MAP_TABLE_COLUMN = {
#     'category_code': {
#         'table_name': 'financial_statement_dim',
#         'column_names': ['category_name', 'category_code'],
#         'return_columns': ['category_code', 'category_name']
#     },
#     'ratio_code': {
#         'table_name': 'financial_ratio_dim',
#         'column_names': ['ratio_name', 'ratio_code'],
#         'return_columns': ['ratio_code', 'ratio_name']
#     },
#     'stock_code': {
#         'table_name': 'company_info',
#         'column_names': ['stock_code', 'company_name', 'short_name'],
#         'return_columns': ['stock_code', 'company_name', 'short_name']
#     }
# }


# def load_all_tables(client: PostgresClient):
#     data = {}

#     for key, config in MAP_TABLE_COLUMN.items():
#         table = config['table_name']
#         cols = config['column_names']

#         sql = f"""
#         SELECT {', '.join(set(cols + config['return_columns']))}
#         FROM {table}
#         """

#         rows = client.execute_query(sql)  # sync load
#         df = pd.DataFrame([dict(r) for r in rows])

#         data[key] = df

#     return data



# def fuzzy_search_in_memory(df: pd.DataFrame, query: str, column_names, limit=10):
#     candidates = []

#     for _, row in df.iterrows():
#         best_score = 0

#         for col in column_names:
#             val = str(row[col])

#             score = fuzz.WRatio(query.lower(), val.lower())
#             best_score = max(best_score, score)

#         if best_score > 50:  # threshold
#             candidates.append((best_score, row))

#     # sort desc
#     candidates.sort(key=lambda x: x[0], reverse=True)

#     top_rows = [r for _, r in candidates[:limit]]

#     if not top_rows:
#         return None

#     return pd.DataFrame(top_rows)


# async def fuzzy_search_values(data_map, table_name, search_value, limit=10):

#     if table_name not in MAP_TABLE_COLUMN:
#         return f"Unsupported table: {table_name}"

#     df = data_map[table_name]
#     column_names = MAP_TABLE_COLUMN[table_name]['column_names']

#     result_df = fuzzy_search_in_memory(df, search_value, column_names, limit)

#     if result_df is None:
#         return f"No matches found for '{search_value}'"

#     return df_to_markdown(result_df)


# def register_tool(mcp, client: PostgresClient):
    
#     data_map = load_all_tables(client)

#     @mcp.tool()
    
#     async def fuzzy_search_financial_metrics( query: str, field: str) -> str:
#         """
#         This tool helps to find the exact financial ratio code/ category code/ stock code for financial metrics based on a user query.
#         It supports fuzzy search on name/description fields, and specifically for stock_code, it also searches the stock_code field.

#         Args:
#             query: User query to find the exact financial ratio code. Must be in English.
#             field: The field to search in, either 'category_code', 'ratio_code', or 'stock_code'.
#         Returns:
#             Financial code as a string or error message
#         """
        
#         return await fuzzy_search_values(data_map, field, query)
    
