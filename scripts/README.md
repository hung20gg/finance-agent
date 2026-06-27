# Utility Scripts

This directory contains shell and PowerShell scripts for evaluation, data generation, and server management.

## Key Scripts

### Evaluation
- `evaluate.sh`: Main evaluation script for testing agent performance on specific datasets. Supports parameters like `--model`, `--split`, and `--num_worker`.
- `evaluate_baseline.sh`: Baseline runner for method-based evaluations such as `vanilla`. Supports `--method`, `--model`, `--split`, and `--num_worker`.
- `evaluate_chart.sh`: Specialized evaluation script for Text2Chart performance.
- `evaluate.ps1`: Windows PowerShell version of the evaluation script.

### Data Generation
- `generate_answer.sh`: Orchestrates the generation of answers from a model for a given set of questions.
- `generate_question.sh`: Used for generating synthetic or sampled questions for testing.

### Server Management
- `run_mcp.sh` / `start_mcp_server.sh`: Helpers to start the MCP server.

### Testing
- `test_agent.sh`: Runs the agent testing suite.

## Usage

Most scripts are designed to be run from the project root. For example:
```bash
./scripts/evaluate.sh --model vllm:qwen-sql-v1-full --split val
```

To run the vanilla baseline:
```bash
./scripts/evaluate_baseline.sh --method vanilla --model deepinfra:openai/gpt-oss-120b --split val
```

Baseline runs use the answer-only scorer. Any `tool_calls` in the baseline transcript are synthetic and are kept only for evaluator compatibility.

## Subdirectories
- `build/`: Scripts for building Docker images or other artifacts.
- `download/`: Scripts for downloading model weights or datasets.
- `run/`: Operational scripts for running specific agent configurations.
- `training/`: Scripts and configurations for fine-tuning models.
