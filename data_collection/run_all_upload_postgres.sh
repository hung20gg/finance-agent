#!/usr/bin/env bash
set -euo pipefail

# Runs all data_collection/*/upload_postgres.py scripts.
# Usage:
#   ./data_collection/run_all_upload_postgres.sh            # sequential (default)
#   ./data_collection/run_all_upload_postgres.sh --parallel # run all at once

MODE="sequential"
if [[ "${1:-}" == "--parallel" ]]; then
  MODE="parallel"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

SCRIPTS=(
#   "commodites/upload_postgres.py"
  "financial_statement/upload_postgres.py"
#   "macro/upload_postgres.py"
#   "stocks/upload_postgres.py"
)

run_one() {
  local relative_script="$1"
  local script_dir
  script_dir="$(dirname "$relative_script")"
  local script_file
  script_file="$(basename "$relative_script")"

  echo "[START] $relative_script"
  (
    cd "$ROOT_DIR/$script_dir"
    "$PYTHON_BIN" "$script_file"
  )
  echo "[DONE ] $relative_script"
}

if [[ "$MODE" == "parallel" ]]; then
  pids=()
  names=()

  for script in "${SCRIPTS[@]}"; do
    run_one "$script" &
    pids+=("$!")
    names+=("$script")
  done

  for i in "${!pids[@]}"; do
    if ! wait "${pids[$i]}"; then
      echo "[FAIL ] ${names[$i]}"
      exit 1
    fi
  done
else
  for script in "${SCRIPTS[@]}"; do
    run_one "$script"
  done
fi

echo "All upload_postgres.py scripts completed successfully."
