
OUTPUT_DIR=data_mix_v5

INPUT_REWRITE_FILE=${OUTPUT_DIR}/train.jsonl
OUTPUT_REWRITE_FILE=${OUTPUT_DIR}/train.clean.jsonl

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

deactivate 2>/dev/null || true

if [[ -f "${PROJECT_ROOT}/mcp-server/.venv/bin/activate" ]]; then
    source "${PROJECT_ROOT}/mcp-server/.venv/bin/activate"
else
    echo "Warning: ${PROJECT_ROOT}/mcp-server/.venv/bin/activate not found. Proceeding with system python."
fi

cd "${PROJECT_ROOT}/data_processing" || exit 1


# python generator_bigquery.py --val-target-size 200 --test-target-size 400 --output-dir $OUTPUT_DIR || exit 1

# rm -rf data_mix_v5/test.clean.jsonl || exit 1  # Removed - this was deleting the output file before creating it

python smoothen_query.py --input $INPUT_REWRITE_FILE --output $OUTPUT_REWRITE_FILE --workers 16