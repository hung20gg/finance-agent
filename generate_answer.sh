
MODEL_NAME=${MODEL_NAME:-"openrouter:openai/gpt-oss-120b"} # or "qwen3-14b-instruct"
SPLIT=${SPLIT:-"test"}

echo "DEBUG: Initial MODEL_NAME=$MODEL_NAME"
echo "DEBUG: Arguments passed: $@"

# Parse --model and --split flags
while [[ $# -gt 0 ]]; do
  echo "DEBUG: Processing arg: $1"
  case "$1" in
    --model) MODEL_NAME="$2"; echo "DEBUG: Set MODEL_NAME to $2"; shift 2 ;;
    --split) SPLIT="$2"; shift 2 ;;
    --num_worker) NUM_WORKER="$2"; shift 2 ;;
    *) shift ;;
  esac
done

echo "DEBUG: Final MODEL_NAME=$MODEL_NAME"
echo "DEBUG: Final SPLIT=$SPLIT"

deactivate 2>/dev/null || true

cd agent || exit 1

source .venv/bin/activate

cd ../scripts || exit 1

echo "DEBUG: Calling evaluate.sh with --model '$MODEL_NAME' and --num_worker '${NUM_WORKER:-2}'"

./evaluate.sh --model "${MODEL_NAME}" --num_worker "${NUM_WORKER:-2}" --input_file


# ./generate_answer.sh --model openrouter:openai/gpt-oss-120b --num_worker 4
