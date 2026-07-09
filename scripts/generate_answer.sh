
MODEL_NAME=${MODEL_NAME:-"openrouter:openai/gpt-oss-120b"} # or "qwen3-14b-instruct"
SPLIT=${SPLIT:-"test"}
ITERATION=${ITERATION:-1}
HINT=${HINT:-false}


echo "DEBUG: Initial MODEL_NAME=$MODEL_NAME"
echo "DEBUG: Arguments passed: $@"

# Parse --model and --split flags
while [[ $# -gt 0 ]]; do
  echo "DEBUG: Processing arg: $1"
  case "$1" in
    --model) MODEL_NAME="$2"; echo "DEBUG: Set MODEL_NAME to $2"; shift 2 ;;
    --split) SPLIT="$2"; shift 2 ;;
    --num_worker) NUM_WORKER="$2"; shift 2 ;;
    --iteration) ITERATION="$2"; shift 2 ;;
    --hint)
      if [[ $# -gt 1 && "$2" != --* ]]; then
        case "$2" in
          true|True|TRUE|1|yes|Yes|YES) HINT=true ;;
          false|False|FALSE|0|no|No|NO) HINT=false ;;
          *) echo "Unsupported --hint value: $2. Use true or false."; exit 1 ;;
        esac
        shift 2
      else
        HINT=true
        shift
      fi
      ;;
    --no-hint) HINT=false; shift ;;
    *) shift ;;
  esac
done

echo "DEBUG: Final MODEL_NAME=$MODEL_NAME"
echo "DEBUG: Final SPLIT=$SPLIT"
echo "DEBUG: Final HINT=$HINT"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

deactivate 2>/dev/null || true

if [[ -f "${PROJECT_ROOT}/agent/.venv/bin/activate" ]]; then
    source "${PROJECT_ROOT}/agent/.venv/bin/activate"
else
    echo "Warning: ${PROJECT_ROOT}/agent/.venv/bin/activate not found. Proceeding with system python."
fi

echo "DEBUG: Calling evaluate.sh with --model '$MODEL_NAME' and --num_worker '${NUM_WORKER:-2}'"

hint_flag=()
if [[ "$HINT" == "true" ]]; then
  hint_flag=(--hint)
fi

"${PROJECT_ROOT}/scripts/evaluate.sh" --model "${MODEL_NAME}" --num_worker "${NUM_WORKER:-2}" --split "${SPLIT}" --iteration "${ITERATION}" "${hint_flag[@]}"

# ./generate_answer.sh --model openrouter:openai/gpt-oss-120b --num_worker 4 --hint
