#!/usr/bin/env bash
set -euo pipefail

# Get project root (script is in scripts/build/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

cd mcp-server

deactivate || true

uv venv

source .venv/bin/activate

uv pip install -r requirements.txt

uv pip install -r ../data_collection/requirements.txt

cd ../

bash scripts/build/postgres_apt.sh

cd data_collection


# Check if gcp key exist in keys/
if [ ! -f "keys/big-query.json" ]; then
    echo "GCP key not found in keys/big-query.json"
    
    # User will paste the key here for installation
    read -p "Paste GCP key: " gcp_key
    echo "$gcp_key" > keys/big-query.json
fi

# Run the script
bash ./run_all_upload_postgres.sh


cd ../mcp-server

python src/server.py
