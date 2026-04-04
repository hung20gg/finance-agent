#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   chmod +x scripts/evaluate.sh
#   ./scripts/evaluate.sh
#   ./scripts/evaluate.sh --model deepinfra:Qwen/Qwen3-235B-A22B-Thinking-2507
#
# Optional overrides:
#   DATASET_PATH=... OUTPUT_FILE=... BASE_MODEL=... AGENT_TYPE=... NUM_WORKER=... ./scripts/evaluate.sh

MODEL_NAME=${MODEL_NAME:-"openrouter:openai/gpt-oss-120b"} # or "qwen3-14b-instruct"
SPLIT=${SPLIT:-"test"}

# Parse --model and --split flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL_NAME="$2"; shift 2 ;;
    --split) SPLIT="$2"; shift 2 ;;
    --num_worker) NUM_WORKER="$2"; shift 2 ;;
    *) shift ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_processing/data_mix_v4/test.clean.jsonl}"
OUTPUT_FILE="${OUTPUT_FILE:-${PROJECT_ROOT}/data/eval_results_${MODEL_NAME}.jsonl}"
BASE_MODEL=${MODEL_NAME}
AGENT_TYPE="${AGENT_TYPE:-text2sql}"
NUM_WORKER="${NUM_WORKER:-2}"

mkdir -p "$(dirname "${OUTPUT_FILE}")"

python "${PROJECT_ROOT}/scripts/run/run_evaluation.py" \
  --input_file "${INPUT_FILE}" \
  --output_file "${OUTPUT_FILE}" \
  --agent_type "${AGENT_TYPE}" \
  --base_model "${BASE_MODEL}" \
  --num_worker "${NUM_WORKER}"
