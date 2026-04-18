#!/usr/bin/env bash
set -euo pipefail

# Default values
AGENT="bi_agent"
SELF_EVALUATE=""
SAVE_CHARTS=""
CHART_TYPE=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      AGENT="$2"
      shift 2
      ;;
    --self-evaluate)
      SELF_EVALUATE="--self-evaluate"
      shift
      ;;
    --save-charts)
      SAVE_CHARTS="--save_charts"
      shift
      ;;
    --chart-type)
      CHART_TYPE="--chart_type $2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      shift
      ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Activate env
deactivate 2>/dev/null || true

if [[ -f "${PROJECT_ROOT}/agent/.venv/bin/activate" ]]; then
    source "${PROJECT_ROOT}/agent/.venv/bin/activate"
else
    echo "Warning: ${PROJECT_ROOT}/agent/.venv/bin/activate not found. Proceeding with system python."
fi

cd "${PROJECT_ROOT}"

# Debug (optional)
echo "AGENT=${AGENT}"
echo "SELF_EVALUATE=${SELF_EVALUATE}"
echo "SAVE_CHARTS=${SAVE_CHARTS}"
echo "CHART_TYPE=${CHART_TYPE}"

# Run python with args
python -m agent.test_agent \
  --agent "${AGENT}" \
  ${SELF_EVALUATE} \
  ${SAVE_CHARTS} \
  ${CHART_TYPE}