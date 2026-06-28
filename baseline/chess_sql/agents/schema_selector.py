import json
from typing import Dict, List

from baseline.chess_sql.agents.base import ChessSubAgent
from baseline.chess_sql.mcp_tools import ChessMCPTools
from baseline.chess_sql.state import ChessSQLAgentState
from baseline.utils import extract_json_object, load_baseline_prompt, render_current_time_prompt


DEFAULT_TABLES = [
    "dim_company",
    "dim_industry",
    "dim_exchange",
    "dim_financial_ratio",
    "dim_financial_statement_category",
    "dim_market_index",
    "dim_commodity_indicator",
    "dim_macro_indicator",
    "dim_country",
    "fact_financial_ratio",
    "fact_financial_statement",
    "fact_stock_daily",
    "fact_stock_monthly",
    "fact_index_daily",
    "fact_index_monthly",
    "fact_commodity_daily",
    "fact_commodity_monthly",
    "fact_macro",
    "fact_industry_financial_statement",
    "fact_industry_financial_ratio",
]


class SchemaSelector(ChessSubAgent):
    """CHESS schema selector: filter columns, select tables, select columns."""

    def __init__(self, llm, current_time: str, mcp_tools: ChessMCPTools) -> None:
        super().__init__(
            llm=llm,
            current_time=current_time,
            name="Schema Selector",
            task="narrow the schema by calling filter_column, select_tables, and select_columns",
        )
        self.mcp_tools = mcp_tools
        self.filter_column_prompt = load_baseline_prompt("chess_sql", "filter_column.md")
        self.select_tables_prompt = load_baseline_prompt("chess_sql", "select_tables.md")
        self.select_columns_prompt = load_baseline_prompt("chess_sql", "select_columns.md")
        self.tool_fns = {
            "filter_column": self.filter_column,
            "select_tables": self.select_tables,
            "select_columns": self.select_columns,
        }
        self.tool_descriptions = {
            "filter_column": "Infer likely relevant columns before metadata is loaded.",
            "select_tables": "Select relevant tables and load their metadata through MCP get_table_metadata(table_name).",
            "select_columns": "Select relevant columns from loaded table metadata.",
        }

    def is_complete(self, state: ChessSQLAgentState) -> bool:
        return bool(state.selected_tables and state.schema_metadata and state.selected_schema)

    async def filter_column(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.filter_column_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Keywords:\n{state.keywords}\n\n"
                f"Retrieved entities:\n{json.dumps(state.retrieved_entities, ensure_ascii=False)}"
            ),
            chess_state=state,
            trace_agent="Schema Selector.filter_column",
        )
        parsed = extract_json_object(response) or {}
        columns = parsed.get("likely_columns", {})
        state.selected_columns = columns if isinstance(columns, dict) else {}
        return f"filter_column: {state.selected_columns}"

    async def select_tables(self, state: ChessSQLAgentState) -> str:
        system_prompt = render_current_time_prompt(self.select_tables_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Retrieved context:\n{state.retrieved_context}\n\n"
                f"Likely columns:\n{json.dumps(state.selected_columns, ensure_ascii=False)}"
            ),
            chess_state=state,
            trace_agent="Schema Selector.select_tables",
        )
        parsed = extract_json_object(response) or {}
        tables = parsed.get("tables", [])
        if not isinstance(tables, list):
            tables = DEFAULT_TABLES
        state.selected_tables = [table for table in tables if table in DEFAULT_TABLES] or DEFAULT_TABLES
        state.schema_metadata = await self.load_table_metadata(state.selected_tables)
        return f"select_tables: {state.selected_tables}"

    async def load_table_metadata(self, tables: List[str]) -> Dict[str, str]:
        metadata = {}
        for table_name in tables:
            metadata[table_name] = await self.mcp_tools.get_table_metadata(table_name)
        return metadata

    async def select_columns(self, state: ChessSQLAgentState) -> str:
        if not state.schema_metadata:
            state.schema_metadata = await self.load_table_metadata(state.selected_tables or DEFAULT_TABLES)

        system_prompt = render_current_time_prompt(self.select_columns_prompt, state.current_time)
        response = await self.ainvoke(
            system_prompt,
            (
                f"Question:\n{state.user_request or state.question}\n\n"
                f"Retrieved context:\n{state.retrieved_context}\n\n"
                f"Table metadata from MCP get_table_metadata(table_name):\n"
                f"{json.dumps(state.schema_metadata, ensure_ascii=False)}"
            ),
            chess_state=state,
            trace_agent="Schema Selector.select_columns",
        )
        parsed = extract_json_object(response) or {}
        columns = parsed.get("columns", {})
        if isinstance(columns, dict) and columns:
            state.selected_columns = columns
        state.selected_schema = self.format_selected_schema(state)
        return f"select_columns: {state.selected_columns}"

    def format_selected_schema(self, state: ChessSQLAgentState) -> str:
        parts = []
        for table_name in state.selected_tables:
            selected_columns = state.selected_columns.get(table_name, [])
            metadata = state.schema_metadata.get(table_name, "")
            parts.append(
                f"## {table_name}\n"
                f"Selected columns: {selected_columns or 'all relevant columns'}\n"
                f"{metadata}"
            )
        return "\n\n".join(parts)
