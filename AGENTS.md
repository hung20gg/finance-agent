# AGENTS.md — Finance Agent Repository

## Project Overview

A LangGraph-based financial forecasting AI agent system with multiple agent strategies (ReAct, Text2SQL, Text2Chart, BIAgent), an MCP server for financial data tools backed by PostgreSQL, and a Highcharts rendering server.

### Directory Structure

```
agent/              — Core AI agents (LangGraph-based)
mcp-server/         — FastMCP server exposing financial data via SSE + PostgreSQL
highchart-server/   — Node.js + Puppeteer server for rendering Highcharts to PNG
data_collection/    — Crawlers for Vietnamese stock, commodities, macro data, news
data_processing/    — Training/testing dataset generation for LLM fine-tuning
render/             — Selenium-based HTML/JS rendering for chart visualization
scripts/            — Evaluation and utility scripts
streamlit/          — Streamlit UI (placeholder)
```

**Note:** `data_*` folders belong to other projects — ignore them unless working on data pipelines.

---

## Build / Run / Test Commands

### Package Management

This project uses **uv** for Python dependency management. Each subproject has its own `.venv` and `requirements.txt`.

```bash
# Create venv and install deps for a subproject
cd agent && uv venv && uv pip install -r requirements.txt
cd mcp-server && uv venv && uv pip install -r requirements.txt
```

### Running Agents

```bash
# Quick test of agents (manual, no assertions)
cd agent && python test_agent.py

# Run evaluation pipeline
./generate_answer.sh                          # uses agent/.venv + scripts/evaluate.sh
./scripts/evaluate.sh --model <model> --split test --num_worker 2

# Windows equivalent
powershell -File scripts/evaluate.ps1
```

### Running MCP Server

```bash
cd mcp-server && uv pip install -r requirements.txt
python -m src.server                          # starts SSE server on port 9004
```

### Running Highchart Server

```bash
cd highchart-server && npm install && node index.js  # starts on port 3000
```

### Running a Single Test

There is **no formal test framework** (no pytest). Tests are ad-hoc Python scripts:

```bash
cd agent && python test_agent.py    # runs test_bi_agent() by default
cd agent && python test.py          # other manual test
```

To test a specific agent, edit `test_agent.py` and change the `asyncio.run(...)` call at the bottom, or call the async test functions directly:

```python
asyncio.run(test_react())
asyncio.run(test_text2sql())
```

### Docker

```bash
cd agent && docker build -t finance-agent .
cd mcp-server && docker build -t mcp-server .
```

---

## Code Style Guidelines

### Imports

- **Order:** standard library → third-party → local/relative, separated by blank lines
- **Absolute imports** for cross-module: `from core.agent import ...`, `from llm import get_llm_wrapper`
- **Relative imports** within subpackages: `from .state import Text2SQLAgentState`, `from ..text2sql.agent import ...`
- `sys.path` manipulation is used in entry points to add parent directories — follow existing patterns
- `load_env_config()` must run before other imports in entry points (see `strategy/__init__.py`)

### Type Hints

- Use `typing` module: `Dict`, `List`, `Any`, `Optional`, `Union`, `AsyncIterable`, `TypeVar`, `Generic`, `Annotated`, `TypedDict`
- **State classes:** use `@dataclass` with type-annotated fields and `field(default_factory=...)`
- **Config classes:** use Pydantic `BaseModel` with inheritance from `BaseAgentMCPConfig`
- Generic base classes: `BaseAgentMCP[StateT, ConfigT]` where `StateT = TypeVar("StateT", bound=AgentState)`
- Annotate return types on methods; `-> None` on `__init__`

### Naming Conventions

| Kind | Convention | Examples |
|------|-----------|----------|
| Classes | PascalCase | `BIAgent`, `Text2SQLAgent`, `ReActAgent`, `PostgresClient` |
| Functions/Methods | snake_case | `tool_calling`, `tool_execute`, `build_graph`, `ainvoke` |
| Constants | UPPER_SNAKE_CASE | `TEXT2SQL_TOOL_NAME`, `BI_AGENT_SYSTEM_PROMPT`, `SERVER_URL` |
| Variables | snake_case | `tool_response`, `chart_agent_state`, `function_name` |
| Private methods | `_` prefix | `_render_system_prompt`, `_ensure_pool`, `_tool_execute` |
| Async methods | `async def` or `a` prefix | `ainvoke`, `aexecute_query`, `stream_tool_calling_async` |

### Error Handling

- Use **broad `try/except Exception`** with `logger.error()` — return error strings instead of crashing
- Raise **`ValueError`** for invalid inputs or unknown agent types
- Raise **`ImportError`** with install instructions for optional dependencies
- Graceful degradation: tool execution errors return `"Error executing tool: {e}"`
- Use `logger` from `core.logger` or module-level `logging.getLogger(__name__)`

### Formatting

- **Indentation:** 4 spaces
- **String quotes:** double quotes preferred
- **Blank lines:** 2 between top-level classes/functions, 1 between methods
- **f-strings** for interpolation
- **Docstrings:** Google-style with `Args:` and `Returns:` where applicable (not consistently enforced)

### Async Design

- **Async-first:** use `async def` methods, `asyncio.run()` for entry points
- LangGraph `StateGraph` with nodes: `llm` → `tools` → `finalize` → `END`
- Use `asyncio.gather()` for parallel tool execution
- Async context managers: `async with agent:` calls `initialize()` automatically

### Environment & Configuration

- Centralized `.env` at project root (gitignored); subprojects may have local `.env`
- Config loaded via `env_config.py` with fallback: current env → local `.env` → parent `.env`
- Weave/W&B tracing is optional, controlled by `WEAVE_TRACE_ENABLED` env var

### Prompts

- Stored as `.md` files in `agent/prompt/`
- Written in Vietnamese

### MCP Tools

- Auto-discovered from `src/tools/` via `register_tool` convention
- Tools exposed via FastMCP SSE endpoint

### Linting / Formatting

**No linter or formatter is configured.** No ruff, black, flake8, mypy, or pre-commit hooks exist. Follow the existing code style manually.

### Git

- `.env`, `data/`, `.venv/`, `temp/`, `keys/` are gitignored
- No CI/CD pipeline configured
