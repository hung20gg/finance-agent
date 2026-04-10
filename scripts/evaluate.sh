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
    --model|--base_model) MODEL_NAME="$2"; shift 2 ;;
    --split) SPLIT="$2"; shift 2 ;;
    --num_worker) NUM_WORKER="$2"; shift 2 ;;
    *) shift ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$SPLIT" == "test" ]]; then
  INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_processing/data_mix_v5/test.clean.jsonl}"
elif [[ "$SPLIT" == "val" ]]; then
  INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_processing/data_mix_v5/val.clean.jsonl}"
elif [[ "$SPLIT" == "train" ]]; then
  INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_processing/data_mix_v5/train.clean.jsonl}"

else
  echo "Unsupported SPLIT: $SPLIT. Use 'test' 'train 'val'."
  exit 1
fi

safe_model_name="${MODEL_NAME//[:\/]/_}"
OUTPUT_FILE="${OUTPUT_FILE:-${PROJECT_ROOT}/data/eval_${SPLIT}_results_${safe_model_name}.jsonl}"
AGENT_TYPE="${AGENT_TYPE:-text2sql}"
NUM_WORKER="${NUM_WORKER:-2}"

mkdir -p "$(dirname "${OUTPUT_FILE}")"

echo "INPUT_FILE=${INPUT_FILE}"
echo "OUTPUT_FILE=${OUTPUT_FILE}"
echo "SAFE_MODEL_NAME=${safe_model_name}"
echo "AGENT_TYPE=${AGENT_TYPE}"
echo "MODEL_NAME=${MODEL_NAME}"
echo "NUM_WORKER=${NUM_WORKER}"

python "${PROJECT_ROOT}/scripts/run/run_evaluation.py" \
  --input_file "${INPUT_FILE}" \
  --output_file "${OUTPUT_FILE}" \
  --agent_type "${AGENT_TYPE}" \
  --base_model "${MODEL_NAME}" \
  --num_worker "${NUM_WORKER}"
