#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME=${MODEL_NAME:-"openrouter:openai/gpt-oss-120b"}
SPLIT=${SPLIT:-"test"}
ITERATION=${ITERATION:-1}
HINT=${HINT:-false}

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "PROJECT_ROOT=${PROJECT_ROOT}"
deactivate 2>/dev/null || true

if [[ -f "${PROJECT_ROOT}/agent/.venv/bin/activate" ]]; then
    source "${PROJECT_ROOT}/agent/.venv/bin/activate"
else
    echo "Warning: ${PROJECT_ROOT}/agent/.venv/bin/activate not found. Proceeding with system python."
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model|--base_model) MODEL_NAME="$2"; shift 2 ;;
    --split) SPLIT="$2"; shift 2 ;;
    --num_worker) NUM_WORKER="$2"; shift 2 ;;
    --iteration) ITERATION="$2"; shift 2 ;;
    --hint) HINT=true; shift ;;

    *) shift ;;
  esac
done


if [[ "$SPLIT" == "test" ]]; then
  INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_processing/data_mix_v5/test.clean.jsonl}"
elif [[ "$SPLIT" == "val" ]]; then
  INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_processing/data_mix_v5/val.clean.jsonl}"
elif [[ "$SPLIT" == "train" ]]; then
  INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_processing/data_mix_v5/train.clean.jsonl}"
else
  echo "Unsupported SPLIT: $SPLIT. Use 'test', 'train', or 'val'."
  exit 1
fi

safe_model_name="${MODEL_NAME//[:\/]/_}"
if [ "$HINT" = true ]; then
  OUTPUT_FILE="${OUTPUT_FILE:-${PROJECT_ROOT}/data/eval_${SPLIT}_hint_results_${safe_model_name}.jsonl}"
else
  OUTPUT_FILE="${OUTPUT_FILE:-${PROJECT_ROOT}/data/eval_${SPLIT}_results_${safe_model_name}.jsonl}"
fi
AGENT_TYPE="${AGENT_TYPE:-text2sql}"
NUM_WORKER="${NUM_WORKER:-2}"

# Watchdog settings
STALL_TIMEOUT_SECONDS="${STALL_TIMEOUT_SECONDS:-180}"   # no updates for 3 mins
HARD_TIMEOUT_SECONDS="${HARD_TIMEOUT_SECONDS:-3600}"   # total runtime 1 hour

mkdir -p "$(dirname "${OUTPUT_FILE}")"
mkdir -p "${PROJECT_ROOT}/logs"

echo "INPUT_FILE=${INPUT_FILE}"
echo "OUTPUT_FILE=${OUTPUT_FILE}"
echo "SAFE_MODEL_NAME=${safe_model_name}"
echo "AGENT_TYPE=${AGENT_TYPE}"
echo "MODEL_NAME=${MODEL_NAME}"
echo "NUM_WORKER=${NUM_WORKER}"
echo "STALL_TIMEOUT_SECONDS=${STALL_TIMEOUT_SECONDS}"
echo "HARD_TIMEOUT_SECONDS=${HARD_TIMEOUT_SECONDS}"
echo "HINT=${HINT}"

get_mtime() {
  local f="$1"
  if [[ -f "$f" ]]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      stat -f %m "$f" 2>/dev/null || echo 0
    else
      stat -c %Y "$f" 2>/dev/null || echo 0
    fi
  else
    echo 0
  fi
}

run_with_watchdog() {
  local output_file="$1"
  local log_file="$2"

  : > "$log_file"
  touch "$output_file" 2>/dev/null || true

  local hint_flag=""
  if [[ "$HINT" == "true" ]]; then
    hint_flag="--hint"
  fi

  python "${PROJECT_ROOT}/scripts/run/run_evaluation.py" \
    --input_file "${INPUT_FILE}" \
    --output_file "${output_file}" \
    --agent_type "${AGENT_TYPE}" \
    --base_model "${MODEL_NAME}" \
    --num_worker "${NUM_WORKER}" \
    ${hint_flag} \
    >>"$log_file" 2>&1 &

  local pid=$!
  local start_ts
  start_ts=$(date +%s)

  local last_activity_ts="$start_ts"

  while kill -0 "$pid" 2>/dev/null; do
    sleep 5

    local now
    now=$(date +%s)

    local log_mtime
    local out_mtime
    log_mtime=$(get_mtime "$log_file")
    out_mtime=$(get_mtime "$output_file")

    local latest_mtime="$log_mtime"
    if (( out_mtime > latest_mtime )); then
      latest_mtime="$out_mtime"
    fi

    if (( latest_mtime > last_activity_ts )); then
      last_activity_ts="$latest_mtime"
    fi

    if (( now - start_ts > HARD_TIMEOUT_SECONDS )); then
      echo "Process exceeded ${HARD_TIMEOUT_SECONDS}s. Killing PID ${pid} and continuing."
      kill -TERM "$pid" 2>/dev/null || true
      sleep 5
      kill -KILL "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 124
    fi

    if (( now - last_activity_ts > STALL_TIMEOUT_SECONDS )); then
      echo "No log/output update for ${STALL_TIMEOUT_SECONDS}s. Killing PID ${pid} and continuing."
      kill -TERM "$pid" 2>/dev/null || true
      sleep 5
      kill -KILL "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
      return 125
    fi
  done

  wait "$pid"
}

if [[ "$ITERATION" -eq 1 ]]; then
  echo "Running single iteration"

  single_log_file="${PROJECT_ROOT}/logs/eval_${SPLIT}_${safe_model_name}.log"

  if run_with_watchdog "${OUTPUT_FILE}" "${single_log_file}"; then
    echo "Single iteration finished successfully."
  else
    status=$?
    echo "Single iteration stopped with status ${status}."
  fi

else
  echo "Running ${ITERATION} iterations"

  for ((i=1; i<=ITERATION; i++)); do
    iter_output_file="${OUTPUT_FILE%.jsonl}_iter${i}.jsonl"
    iter_log_file="${PROJECT_ROOT}/logs/eval_${SPLIT}_${safe_model_name}_iter${i}.log"

    echo "Iteration $i → ${iter_output_file}"
    echo "Log file   $i → ${iter_log_file}"

    if run_with_watchdog "${iter_output_file}" "${iter_log_file}"; then
      echo "Iteration $i finished successfully."
    else
      status=$?
      echo "Iteration $i stopped with status ${status}. Continuing to next iteration."
      continue
    fi
  done
fi