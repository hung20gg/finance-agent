# Data Processing & Dataset Generation

This module is responsible for preparing training and evaluation datasets for the LLMs used in the Finance Agent.

## Overview

We generate high-quality datasets to fine-tune models (specifically Qwen variants) for specialized tasks like Text2SQL and Text2Chart. The data is formatted to be compatible with **GRPO (Group Relative Policy Optimization)** and standard Hugging Face formats.

## Dataset Structure

Each entry typically includes:
- **Question (Prompt)**: The natural language query.
- **Ground Truth (Label)**: The correct SQL query or Highcharts configuration.

## Sampling Strategy

Data is sampled from the datasource based on specific financial events and metrics. For example:
- Stock/Index returns within a specific quarter.
- Commodity price changes (e.g., Gold).
- Corporate financial metrics (Revenue, EBITDA, Net Income).
- Banking-specific ratios (NIM, Bad debt ratio).
- Macro indicators (Inflation, Unemployment).

## Temporal Split

- **Training Data**: Q3 2023 -> Q2 2025
- **Testing Data**: Q3 2025

## Usage

To generate a new dataset, run the processing scripts:
```bash
python -m src.generate_dataset --type sql --split train
```

Check the `data/` directory in the root for generated output files (`.jsonl`).