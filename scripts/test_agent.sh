deactivate 2>/dev/null || true

cd agent && source .venv/bin/activate || exit 1

cd ..

python -m agent.test_agent
