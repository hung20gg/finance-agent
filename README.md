# Finance Agent

A multi-agent system designed for financial forecasting and business intelligence, specifically focused on the Vietnamese market.

## Project Overview

The Finance Agent project leverages a multi-agent architecture (using LangGraph) to provide advanced financial analysis, chart generation, and data querying capabilities. It integrates with a custom MCP (Model Context Protocol) server for real-time data access and a Highcharts server for visual rendering.

### Key Components

- **AI Agents**: LangGraph-based agents implementing various strategies:
  - **BIAgent**: High-level orchestrator for business intelligence tasks.
  - **ReAct Agent**: Flexible agent using Reasoning and Acting patterns.
  - **Text2SQL**: specialized agent for translating natural language into PostgreSQL queries.
  - **Text2Chart**: Generates chart configurations based on query results.
- **MCP Server**: FastMCP server exposing financial data tools (stock prices, financial statements, macro indicators) via SSE.
- **Highcharts Server**: Node.js service using Puppeteer to render Highcharts configurations into high-quality images.
- **Data Pipeline**: Automated crawlers and processing scripts for collecting and preparing financial datasets.

## Directory Structure

```text
finance-agent/
├── agent/              — Core AI agents logic and strategies
├── mcp-server/         — Financial data tools and SSE server
├── highchart-server/   — Highcharts rendering service
├── data_collection/    — Crawlers for stock, macro, and news data
├── data_processing/    — Training and evaluation dataset generation
├── streamlit/          — Interactive web UI for the agent
├── scripts/            — Evaluation and utility scripts
└── models/             — Local model weights and LoRA adapters
```

## Getting Started

Refer to [AGENTS.md](./AGENTS.md) for detailed setup, configuration, and architectural details.

### Quick Setup

1. **Environment**: Copy `.env.example` to `.env` and configure your API keys and database credentials.
2. **Dependencies**: This project uses `uv` for Python management.
   ```bash
   cd agent && uv venv && uv pip install -r requirements.txt
   cd ../mcp-server && uv venv && uv pip install -r requirements.txt
   ```
3. **Highcharts Server**:
   ```bash
   cd highchart-server && npm install && node index.js
   ```

## Model Serving (vLLM)

The project uses various Qwen-based models fine-tuned for SQL and Chart generation. Below are common serving commands:

### Serve Base Model with SQL Adapters
```bash
vllm serve Qwen/Qwen3-4B-Thinking-2507 \
  --max-model-len 16000 \
  --enable-lora \
  --lora-modules qwen-sql-v2=models/qwen3-4b-v2/lora/sft \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.85
```

### Serve GRPO Fine-tuned 1.7B Model
```bash
vllm serve hung20gg/qwen3-1.7b-sql \
  --max-model-len 20000 \
  --enable-lora \
  --lora-modules qwen-sql-1.7b-grpo=models/qwen3-1.7b-grpo/global_step_240/actor/lora_adapter \
  --max_lora_rank 64 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes \
  --gpu-memory-utilization 0.85
```

## Evaluation

Run the evaluation pipeline to test model performance:
```bash
bash scripts/evaluate.sh --split val --iteration 3
```

---

## Maintenance Notes (Original TODOs)

- With cổ phiếu questions, must include "giá cổ phiếu".
- Remove volatility questions.
- Review YoY and QoQ questions.
- Check % increase/decrease calculations (might be simple subtraction).
- Standard deviation checks.
