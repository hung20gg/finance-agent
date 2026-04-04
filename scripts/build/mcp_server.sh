#!/bin/bash
echo "=== Building MCP Server ==="
cd mcp-server
uv pip install -r requirements.txt
cd ..