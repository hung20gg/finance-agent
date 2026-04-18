import re
import pandas as pd

def normalize_search_query(query: str) -> str:
    """Escape PostgreSQL ILIKE special characters."""
    return query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

def df_to_markdown(df: pd.DataFrame) -> str:
    # Round numeric columns to at most 5 decimal places
    df = df.round(5)
    text = df.to_markdown(index=False)
    # Reduce 4+ consecutive dashes or spaces to 3
    text = re.sub(r"-{4,}", "---", text)
    text = re.sub(r" {4,}", "   ", text)
    return text