import os
import json
from client import PostgresClient
from logger import logger
import pandas as pd
from rapidfuzz import fuzz
from utils import df_to_markdown
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .formulate_fuzzy_search_config import formulate_fuzzy_search_config

# ---------------------------------------------------------------------------
# Search Backend Abstraction
# ---------------------------------------------------------------------------

class SearchBackend(ABC):
    """Abstract base class for fuzzy/semantic search backends.
    
    Subclass this to implement embedding-based or alternative search strategies.
    """

    @abstractmethod
    def search(
        self,
        df: pd.DataFrame,
        query: str,
        search_columns: List[str],
        threshold: int = 50,
        limit: int = 10,
    ) -> Optional[pd.DataFrame]:
        """Return a DataFrame of top matches, or None if no matches found."""
        ...


class RapidFuzzBackend(SearchBackend):
    """Token-based fuzzy search using rapidfuzz WRatio."""

    def search(
        self,
        df: pd.DataFrame,
        query: str,
        search_columns: List[str],
        threshold: int = 50,
        limit: int = 10,
    ) -> Optional[pd.DataFrame]:
        candidates = []
        query_lower = query.lower()

        for _, row in df.iterrows():
            best_score = 0
            for col in search_columns:
                val = str(row[col])
                score = fuzz.WRatio(query_lower, val.lower())
                best_score = max(best_score, score)

            if best_score > threshold:
                candidates.append((best_score, row))

        # Sort descending by score
        candidates.sort(key=lambda x: x[0], reverse=True)

        top_rows = [r for _, r in candidates[:limit]]
        if not top_rows:
            return None

        return pd.DataFrame(top_rows)


# Registry of available backends — extend here when adding embedding search
_BACKEND_REGISTRY: Dict[str, type] = {
    "rapidfuzz": RapidFuzzBackend,
}


def get_search_backend(backend_name: str) -> SearchBackend:
    """Instantiate a search backend by name.
    
    Args:
        backend_name: Key in the backend registry (e.g. 'rapidfuzz', 'embedding').
    
    Returns:
        An instance of the requested SearchBackend.
    
    Raises:
        ValueError: If the backend name is not registered.
    """
    cls = _BACKEND_REGISTRY.get(backend_name)
    if cls is None:
        raise ValueError(
            f"Unknown search backend '{backend_name}'. "
            f"Available backends: {list(_BACKEND_REGISTRY.keys())}"
        )
    return cls()


# ---------------------------------------------------------------------------
# Configuration Loader
# ---------------------------------------------------------------------------

def load_search_config(config_path: str) -> dict:
    """Load the fuzzy search configuration from a JSON file.
    
    Args:
        config_path: Absolute path to fuzzy_search_config.json
    
    Returns:
        Parsed configuration dictionary.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config


# ---------------------------------------------------------------------------
# Data Loader
# ---------------------------------------------------------------------------

def load_all_tables(client: PostgresClient, entities_config: dict) -> Dict[str, pd.DataFrame]:
    """Preload all searchable entity tables into memory.
    
    Args:
        client: PostgresClient instance for database access.
        entities_config: The 'searchable_entities' section of the config.
    
    Returns:
        Mapping from entity key to its preloaded DataFrame.
    """
    data = {}

    for key, cfg in entities_config.items():
        table = cfg["table_name"]
        all_cols = list(set(cfg["search_columns"] + cfg["return_columns"]))
        distinct = "DISTINCT" if cfg.get("distinct", False) else ""

        sql = f"SELECT {distinct} {', '.join(all_cols)} FROM {table}"

        try:
            rows = client.execute_query(sql)
            data[key] = pd.DataFrame([dict(r) for r in rows])
            logger.info(f"Loaded {len(data[key])} rows for fuzzy search entity '{key}' from '{table}'")
        except Exception as e:
            logger.error(f"Failed to load fuzzy search data for '{key}' from '{table}': {e}")
            data[key] = pd.DataFrame()

    return data


# ---------------------------------------------------------------------------
# Tool Registration
# ---------------------------------------------------------------------------

def register_tool(mcp, client: PostgresClient):
    """Register the generic fuzzy_search MCP tool.
    
    Reads configuration from fuzzy_search_config.json, preloads all entity
    tables, and registers a single tool with a dynamically generated
    description and field enum.
    """
    config_path = os.path.join(os.path.dirname(__file__), "fuzzy_search_config.json")

    if not os.path.exists(config_path):
        config = formulate_fuzzy_search_config(client)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    config = load_search_config(config_path)

    backend_name = config.get("search_backend", "rapidfuzz")
    backend = get_search_backend(backend_name)

    entities_config = config["searchable_entities"]
    data_map = load_all_tables(client, entities_config)

    # Build dynamic documentation
    valid_fields = list(entities_config.keys())
    field_descriptions = "\n".join(
        f"  - '{k}': {v['description']}" for k, v in entities_config.items()
    )

    @mcp.tool()
    async def fuzzy_search(query: str, field: str) -> str:
        f"""Search for exact database identifiers using fuzzy text matching.

This tool helps to find the exact database code/identifier for financial metrics,
companies, indices, or commodities based on a natural language query.

Supported fields:
{field_descriptions}

Args:
    query: The search term (name, code, or description). Must be in English.
    field: The entity type to search in. One of: {valid_fields}
Returns:
    Matching records as a markdown table, or error message.
"""
        logger.info(f"fuzzy_search: query='{query}', field='{field}'")

        if field not in entities_config:
            return (
                f"Unknown field '{field}'. "
                f"Valid fields: {valid_fields}"
            )

        cfg = entities_config[field]
        threshold = cfg.get("threshold", 50)
        limit = cfg.get("limit", 10)
        search_columns = cfg["search_columns"]

        df = data_map.get(field)
        if df is None or df.empty:
            return f"No data loaded for field '{field}'. The backing table may be empty."

        result_df = backend.search(df, query, search_columns, threshold, limit)

        if result_df is None:
            return f"No matches found for '{query}' in field '{field}'."

        # Only return the configured return columns
        return_cols = [c for c in cfg["return_columns"] if c in result_df.columns]
        if return_cols:
            result_df = result_df[return_cols]

        return df_to_markdown(result_df)
