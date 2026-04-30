# upload_dataset.py
# Usage:
#   python upload_dataset.py
# or:
#   python upload_dataset.py <HF_TOKEN>
#
# Expects:
#   data_mix_v5/train.jsonl
#   data_mix_v5/val.jsonl
#   data_mix_v5/test.jsonl
#
# This script:
# 1) Cleans JSONL to ensure a stable schema for Hugging Face
# 2) Uploads cleaned JSONL files to the dataset repo
# 3) Uploads a README.md with the updated schema

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from huggingface_hub import HfApi, login


# ----------------------------
# CONFIG
# ----------------------------
REPO_ID = "hung20gg/financial-forecast"
REPO_TYPE = "dataset"

DATA_DIR = Path("data_mix_v5")
TRAIN_IN = DATA_DIR / "train.clean.jsonl"
VAL_IN = DATA_DIR / "val.clean.jsonl"
TEST_IN = DATA_DIR / "test.clean.jsonl"

TRAIN_OUT = DATA_DIR / "train.cleaned.jsonl"
VAL_OUT = DATA_DIR / "val.cleaned.jsonl"
TEST_OUT = DATA_DIR / "test.cleaned.jsonl"

SHAREGPT_PATH = Path("../../LlamaFactory/data/output_sharegpt_clean.jsonl")

ENV_PATH = Path("../.env")  # change if needed


# ----------------------------
# HELPERS
# ----------------------------
def to_int(x: Any) -> int | None:
    if x is None:
        return None
    try:
        return int(x)
    except Exception:
        return None


def to_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def ensure_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def normalize_example(obj: Dict[str, Any]) -> Dict[str, Any]:
    # Basic root fields
    answer_type = ensure_str(obj.get("answer_type"))
    question = ensure_str(obj.get("question"))
    
    extra_src = obj.get("extra_info", {})
    if not isinstance(extra_src, dict):
        extra_src = {}

    # Apply prompt formatting rules similar to run_evaluation.py
    if answer_type:
        question += f" [{answer_type}]"
    
    result_columns = extra_src.get("result_columns", [])
    if answer_type == "tuple" and result_columns:
        question += f" (Expected columns: {', '.join(result_columns)})"

    res = {
        "id": ensure_str(obj.get("id")),
        "question": question,
        # "question_raw": ensure_str(obj.get("question_raw")),
        "answer_type": answer_type,
        # "answer": to_float(obj.get("answer")),
        "time_asked": ensure_str(obj.get("time_asked")),
        "sources": [ensure_str(s) for s in obj.get("sources", [])] if isinstance(obj.get("sources"), list) else [],
    }
    
    res["data_source"] = "finance-sql"
    _gt = obj.get("answer")
    if isinstance(_gt, (dict, list)):
        _gt_str = json.dumps(_gt, ensure_ascii=False)
    elif _gt is not None:
        _gt_str = str(_gt)
    else:
        _gt_str = ""
    res["reward_model"] = {"style": "rule", "ground_truth": _gt_str}
    res["answer"] = _gt_str

    
    res["extra_info"] = {
        # Fields moved from root
        "gap": to_int(obj.get("gap")),
        "data_cutoff": ensure_str(obj.get("data_cutoff")),
        "reasoning_hops": to_int(obj.get("reasoning_hops")),
        "entities": [ensure_str(e) for e in obj.get("entities", [])] if isinstance(obj.get("entities"), list) else [],
        "metrics": [ensure_str(m) for m in obj.get("metrics", [])] if isinstance(obj.get("metrics"), list) else [],
        "periods": [ensure_str(p) for p in obj.get("periods", [])] if isinstance(obj.get("periods"), list) else [],
        "question_family": ensure_str(obj.get("question_family")),
        "question_subtype": ensure_str(obj.get("question_subtype")),
        "ambiguity": ensure_str(obj.get("ambiguity")),
        "result_columns": result_columns,

        
        # Original extra_info fields
        "value_a": to_float(extra_src.get("value_a")),
        "value_b": to_float(extra_src.get("value_b")),
        "current": to_float(extra_src.get("current")),
        "previous": to_float(extra_src.get("previous")),
    }
    
    return res


def clean_jsonl(src: Path, dst: Path, skip_ids: set[str] | None = None, take_half: bool = False) -> None:
    if not src.exists():
        print(f"[skip] {src} does not exist.")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    examples = []
    skipped = 0
    with src.open("r", encoding="utf-8") as f_in:
        for i, line in enumerate(f_in, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    skipped += 1
                    continue
                
                # Check skip list
                if skip_ids and ensure_str(obj.get("id")) in skip_ids:
                    skipped += 1
                    continue

                obj = normalize_example(obj)
                examples.append(obj)
            except Exception as e:
                # print(f"Error at line {i}: {e}")
                skipped += 1

    if take_half:
        examples = examples[:len(examples) // 2]

    with dst.open("w", encoding="utf-8") as f_out:
        for obj in examples:
            f_out.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"[clean] {src} -> {dst} | kept={len(examples)}, skipped={skipped}")


def build_readme() -> str:
    return """---
language:
- vi
task_categories:
- question-answering
dataset_info:
  features:
  - name: id
    dtype: string
  - name: question
    dtype: string
  - name: answer_type
    dtype: string
  - name: answer
    dtype: string
  - name: time_asked
    dtype: string
  - name: sources
    sequence: string
  - name: data_source
    dtype: string
  - name: reward_model
    struct:
    - name: style
      dtype: string
    - name: ground_truth
      dtype: string
  - name: extra_info
    struct:
    - name: gap
      dtype: int64
    - name: data_cutoff
      dtype: string
    - name: reasoning_hops
      dtype: int64
    - name: entities
      sequence: string
    - name: metrics
      sequence: string
    - name: periods
      sequence: string
    - name: question_family
      dtype: string
    - name: question_subtype
      dtype: string
    - name: ambiguity
      dtype: string
    - name: result_columns
      sequence: string
    - name: value_a
      dtype: float64
    - name: value_b
      dtype: float64
    - name: current
      dtype: float64
    - name: previous
      dtype: float64
configs:
- config_name: default
  data_files:
  - split: train
    path: train.jsonl
  - split: val
    path: val.jsonl
  - split: test
    path: test.jsonl
---

# Financial Forecast Dataset

Vietnamese finance QA dataset focused on company metrics and comparisons.

## Columns
- `id`: Unique identifier
- `question`: Formatted question
- `question_raw`: Raw question text
- `answer_type`: Type of answer (e.g., `entity`)
- `answer`: The numerical answer
- `time_asked`: Date the question was asked
- `sources`: Data sources (e.g., `company_quarter`)
- `data_source`: Identifier for the data source pipeline (e.g., `finance-sql`)
- `reward_model`: Reward model config containing:
    - `style`: Reward style (e.g., `rule`)
    - `ground_truth`: The ground truth value used for reward computation
- `extra_info`: Metadata containing:
    - `gap`: Time gap in periods
    - `data_cutoff`: Data cutoff date
    - `reasoning_hops`: Number of reasoning steps
    - `entities`: List of companies/entities involved
    - `metrics`: List of financial metrics involved
    - `periods`: List of time periods involved
    - `question_family`: Category of the question
    - `question_subtype`: Detailed subcategory
    - `ambiguity`: Ambiguity status
    - `value_a`, `value_b`, `current`, `previous`: Intermediate numerical values
"""


def upload_all(api: HfApi, file_map: dict[Path, str]) -> None:
    """
    Upload multiple files in a single commit to avoid per-file connection stalls.
    file_map: {local_path -> path_in_repo}
    """
    from huggingface_hub import CommitOperationAdd

    operations = []
    for local_path, path_in_repo in file_map.items():
        if not local_path.exists():
            print(f"[upload] skip {local_path} (not found)")
            continue
        print(f"[upload] queuing {local_path} -> {path_in_repo}")
        operations.append(
            CommitOperationAdd(
                path_in_repo=path_in_repo,
                path_or_fileobj=str(local_path),
            )
        )

    if not operations:
        print("[upload] no files to upload.")
        return

    api.create_commit(
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
        operations=operations,
        commit_message="Update dataset files",
    )
    print(f"[upload] committed {len(operations)} file(s) successfully.")


def main() -> None:
    load_dotenv(dotenv_path=str(ENV_PATH))

    print("Log in to Hugging Face...")
    hf_key = os.environ.get("HF_TOKEN")
    if not hf_key and len(sys.argv) > 1:
        hf_key = sys.argv[1].strip()
    
    if hf_key:
        login(token=hf_key, add_to_git_credential=True)
    else:
        print("WARNING: HF_TOKEN not found. Using existing login if available.")

    api = HfApi()

    print("Creating repo if not exists...")
    try:
        api.create_repo(repo_id=REPO_ID, repo_type=REPO_TYPE, exist_ok=True)
        print(f"[repo] ok: {REPO_ID}")
    except Exception as e:
        print(f"[repo] could not create/verify repo: {e}")

    # 0) Load ShareGPT IDs if available
    sharegpt_ids = set()
    if SHAREGPT_PATH.exists():
        try:
            with SHAREGPT_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        if "id" in d:
                            sharegpt_ids.add(str(d["id"]))
            print(f"Loaded {len(sharegpt_ids)} IDs from ShareGPT file.")
        except Exception as e:
            print(f"Warning: Could not read ShareGPT IDs: {e}")
    else:
        print(f"Warning: ShareGPT file not found at {SHAREGPT_PATH}")

    # 1) Clean JSONL files
    print("Cleaning JSONL files...")
    clean_jsonl(TRAIN_IN, TRAIN_OUT, skip_ids=sharegpt_ids)
    clean_jsonl(VAL_IN, VAL_OUT, take_half=True)
    clean_jsonl(TEST_IN, TEST_OUT)

    # 2) Upload cleaned files as train/test in repo root
    print("Uploading cleaned JSONL files...")
    upload_all(api, {
        TRAIN_OUT: "train.jsonl",
        VAL_OUT: "val.jsonl",
        TEST_OUT: "test.jsonl",
    })

    # 3) Write + upload README.md
    print("Writing README_hf.md locally...")
    readme_path = Path("README_hf.md")
    readme_path.write_text(build_readme(), encoding="utf-8")

    print("Uploading README.md to repo...")
    upload_all(api, {readme_path: "README.md"})

    print(f"✅ Done. Dataset: https://huggingface.co/datasets/{REPO_ID}")


if __name__ == "__main__":
    main()