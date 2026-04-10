deactivate 2>/dev/null || true

cd mcp-server || exit 1

source .venv/bin/activate
python src/server.py