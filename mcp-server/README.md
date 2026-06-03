# Financial MCP Server

A Model Context Protocol (MCP) server that provides a standardized interface for agents to interact with financial data.

## Features

- **FastMCP Framework**: Built using the FastMCP library for efficient tool registration and discovery.
- **Financial Tools**: Provides a wide range of tools for fetching stock prices, financial statements, macro-economic indicators, and more.
- **PostgreSQL Integration**: Directly queries a PostgreSQL database containing structured financial data.
- **SSE Support**: Communicates via Server-Sent Events (SSE) for real-time interaction.

## Tool Categories

- **Stock Data**: Current prices, historical values, and technical indicators.
- **Financial Statements**: Revenue, Net Income, EBITDA, and other key metrics for Vietnamese companies.
- **Macro Data**: Inflation, unemployment rates, and gold prices.
- **News**: Search and retrieve relevant financial news.

## Deployment

### Running Locally
```bash
uv venv
uv pip install -r requirements.txt
python -m src.server
```
The server will start on port `9004` by default.

### Docker
To build and push the Docker image:
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t quanghung20gg/mcp-server-sql:v0.2 \
  . \
  --push
```

## Configuration
Requires a `DATABASE_URL` in the environment to connect to the PostgreSQL instance.