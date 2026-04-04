deactivate 2>/dev/null || true

cd agent || exit 1

source .venv/bin/activate

cd ../scripts || exit 1

./evaluate.sh
