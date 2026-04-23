#!/usr/bin/env bash
set -euo pipefail

# Get project root (script is in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"



cd "$PROJECT_ROOT/mcp-server"

deactivate || true

source .venv/bin/activate

python src/server.py