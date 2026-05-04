# Finance Agent Core

This directory contains the core logic for the AI agents used in the financial forecasting system.

## Overview

The agents are built using **LangGraph**, which allows for complex, stateful multi-agent workflows. The system is designed to handle financial queries, perform data retrieval via SQL, and generate visual charts.

## Agent Strategies

We implement several specialized agent strategies:

1.  **ReAct Agent**: A general-purpose agent that uses the Reasoning and Acting pattern to solve multi-step problems.
2.  **Text2SQL Agent**: Specifically fine-tuned to translate natural language financial questions into optimized PostgreSQL queries.
3.  **Text2Chart Agent**: Processes data results and generates Highcharts configurations for visualization.
4.  **BIAgent**: An orchestrator that decides which specialized agent to invoke based on the user's intent.

## Structure

- `core/`: Base agent classes, state management, and logging.
- `strategy/`: Implementation of the different agent types (ReAct, SQL, Chart).
- `prompt/`: System and task-specific prompts (in Markdown format).
- `llm/`: Wrappers for different LLM providers and local models.

## Usage

### Testing
You can run a quick test of the agents using the provided script:
```bash
python test_agent.py
```

To test a specific agent or strategy, modify the `asyncio.run()` call in `test_agent.py` to target the desired function (e.g., `test_text2sql()` or `test_react()`).

### Requirements
Ensure you have `uv` installed. Setup the environment with:
```bash
uv venv
uv pip install -r requirements.txt
```

## Configuration
The agents rely on environment variables defined in the root `.env` file. Key configurations include:
- `OPENROUTER_API_KEY`: For accessing cloud-based models.
- `DATABASE_URL`: For SQL-based data retrieval.
- `MCP_SERVER_URL`: Connection to the financial data tool server.