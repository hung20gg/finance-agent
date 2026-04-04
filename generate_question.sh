

INPUT_FILE=data_mix_v4/test.jsonl
OUTPUT_FILE=data_mix_v4/test.clean.jsonl

deactivate 2>/dev/null || true

cd data_collection || exit 1

source .venv/bin/activate

cd ../data_processing || exit 1


python generator_bigquery.py || exit 1

rm -rf data_mix_v4/test.clean.jsonl

python smoothen_query.py --input $INPUT_FILE --output $OUTPUT_FILE --workers 8