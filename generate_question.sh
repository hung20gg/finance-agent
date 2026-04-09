
OUTPUT_DIR=data_mix_v5

INPUT_REWRITE_FILE=${OUTPUT_DIR}/test.jsonl
OUTPUT_REWRITE_FILE=${OUTPUT_DIR}/test.clean.jsonl

deactivate 2>/dev/null || true

cd mcp-server || exit 1

source .venv/bin/activate

cd ../data_processing || exit 1


# python generator_bigquery.py --val-target-size 200 --test-target-size 400 --output-dir $OUTPUT_DIR || exit 1

# rm -rf data_mix_v5/test.clean.jsonl || exit 1  # Removed - this was deleting the output file before creating it

python smoothen_query.py --input $INPUT_REWRITE_FILE --output $OUTPUT_REWRITE_FILE --workers 16