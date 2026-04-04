import re

def normalize_search_query(query: str) -> str:
    """Escape PostgreSQL ILIKE special characters."""
    return query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')