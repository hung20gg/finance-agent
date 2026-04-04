# upload_dataset.py
# Usage:
#   python upload_dataset.py
# or:
#   python upload_dataset.py <HF_TOKEN>
#
# Expects:
#   data/train.jsonl
#   data/val.jsonl
#   data/test.jsonl
#
# This script:
# 1) Cleans JSONL to avoid schema/type flip issues (extra_info.answer always string, reward_model.ground_truth mean/std floats, etc.)
# 2) Uploads cleaned JSONL files to the dataset repo
# 3) Uploads a README.md with a schema that matches the nested struct ground_truth

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

DATA_DIR = Path("data")
TRAIN_IN = DATA_DIR / "train.jsonl"
VAL_IN = DATA_DIR / "val.jsonl"
TEST_IN = DATA_DIR / "test.jsonl"

TRAIN_OUT = DATA_DIR / "train.cleaned.jsonl"
VAL_OUT = DATA_DIR / "val.cleaned.jsonl"
TEST_OUT = DATA_DIR / "test.cleaned.jsonl"

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


def normalize_prompt(obj: Dict[str, Any]) -> None:
    prompt = obj.get("prompt")
    if not isinstance(prompt, list):
        obj["prompt"] = []
        return

    new_prompt = []
    for msg in prompt:
        if not isinstance(msg, dict):
            continue
        new_prompt.append(
            {
                "role": ensure_str(msg.get("role")),
                "content": ensure_str(msg.get("content")),
            }
        )
    obj["prompt"] = new_prompt


def normalize_reward_model(obj: Dict[str, Any]) -> None:
    rm = obj.get("reward_model", {})
    if not isinstance(rm, dict):
        rm = {}

    gt = rm.get("ground_truth", {})
    if not isinstance(gt, dict):
        # If ground_truth is sometimes a string, try to parse it, else set empty struct
        # (keeps schema stable as struct in the cleaned file)
        if isinstance(gt, str):
            try:
                parsed = json.loads(gt)
                if isinstance(parsed, dict):
                    gt = parsed
                else:
                    gt = {}
            except Exception:
                gt = {}
        else:
            gt = {}

    obj["reward_model"] = {
        "style": ensure_str(rm.get("style")),
        "ground_truth": {
            "mean": to_float(gt.get("mean")),
            "std": to_float(gt.get("std")),
        },
    }


def normalize_extra_info(obj: Dict[str, Any]) -> None:
    extra = obj.get("extra_info", {})
    if not isinstance(extra, dict):
        extra = {}

    normalized_extra = {
        "split": ensure_str(extra.get("split")),
        "index": to_int(extra.get("index")),
        "time_asked": ensure_str(extra.get("time_asked")),
        "gap": to_int(extra.get("gap")),
        "question_type": ensure_str(extra.get("question_type")),
        "std": to_float(extra.get("std")),
        "id": ensure_str(extra.get("id")),
    }

    # Keep answer only if it already exists in source data.
    # This prevents introducing a new field that can break feature casting.
    if "answer" in extra:
        normalized_extra["answer"] = ensure_str(extra.get("answer"))

    obj["extra_info"] = normalized_extra


def normalize_example(obj: Dict[str, Any]) -> Dict[str, Any]:
    obj["data_source"] = ensure_str(obj.get("data_source"))
    obj["ability"] = ensure_str(obj.get("ability"))

    normalize_prompt(obj)
    normalize_reward_model(obj)
    normalize_extra_info(obj)

    return obj


def clean_jsonl(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Missing file: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    kept = 0
    skipped = 0
    with src.open("r", encoding="utf-8") as f_in, dst.open("w", encoding="utf-8") as f_out:
        for i, line in enumerate(f_in, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    skipped += 1
                    continue
                obj = normalize_example(obj)
                f_out.write(json.dumps(obj, ensure_ascii=False) + "\n")
                kept += 1
            except Exception:
                skipped += 1

    print(f"[clean] {src} -> {dst} | kept={kept}, skipped={skipped}")


def build_readme() -> str:
    # Schema here matches the CLEANED jsonl (ground_truth is a struct)
    return """---
language:
- vi
task_categories:
- question-answering
dataset_info:
  features:
  - name: data_source
    dtype: string
  - name: prompt
    list:
    - name: role
      dtype: string
    - name: content
      dtype: string
  - name: ability
    dtype: string
  - name: reward_model
    struct:
    - name: style
      dtype: string
    - name: ground_truth
      struct:
      - name: mean
        dtype: float64
      - name: std
        dtype: float64
  - name: extra_info
    struct:
    - name: split
      dtype: string
    - name: index
      dtype: int64
    - name: time_asked
      dtype: string
    - name: gap
      dtype: int64
    - name: question_type
      dtype: string
    - name: std
      dtype: float64
    - name: id
      dtype: string
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

# Financial Forecast Dataset (ktln)

Vietnamese finance QA dataset in chat format.

## Columns
- `data_source`: source tag (e.g. `ktln`)
- `prompt`: list of chat messages with `role` and `content`
- `ability`: e.g. `math`
- `reward_model.ground_truth`: numeric targets (`mean`, `std`)
- `extra_info`: metadata (split/index/time_asked/gap/question_type/std/id)
"""


def upload(api: HfApi, local_path: Path, path_in_repo: str) -> None:
    api.upload_file(
        path_or_fileobj=str(local_path),
        path_in_repo=path_in_repo,
        repo_id=REPO_ID,
        repo_type=REPO_TYPE,
    )
    print(f"[upload] {local_path} -> {path_in_repo}")


def main() -> None:
    load_dotenv(dotenv_path=str(ENV_PATH))

    print("Log in to Hugging Face...")
    if "HF_TOKEN" in os.environ and os.environ["HF_TOKEN"].strip():
        hf_key = os.environ["HF_TOKEN"].strip()
        login(token=hf_key, add_to_git_credential=True)
    elif len(sys.argv) > 1 and sys.argv[1].strip():
        hf_key = sys.argv[1].strip()
        login(token=hf_key, add_to_git_credential=True)
    else:
        print("ERROR: HF_TOKEN not provided as argument or in .env!")
        sys.exit(1)

    api = HfApi()

    print("Creating repo if not exists...")
    api.create_repo(repo_id=REPO_ID, repo_type=REPO_TYPE, exist_ok=True)
    print(f"[repo] ok: {REPO_ID}")

    # 1) Clean JSONL files
    print("Cleaning JSONL files...")
    clean_jsonl(TRAIN_IN, TRAIN_OUT)
    clean_jsonl(VAL_IN, VAL_OUT)
    clean_jsonl(TEST_IN, TEST_OUT)

    # 2) Upload cleaned files as train/test in repo root
    print("Uploading cleaned JSONL files...")
    upload(api, TRAIN_OUT, "train.jsonl")
    upload(api, VAL_OUT, "val.jsonl")
    upload(api, TEST_OUT, "test.jsonl")

    # 3) Write + upload README.md
    print("Writing README_hf.md...")
    readme_path = Path("README_hf.md")
    readme_path.write_text(build_readme(), encoding="utf-8")

    print("Uploading README.md...")
    upload(api, readme_path, "README.md")

    print(f"✅ Done. Dataset: https://huggingface.co/datasets/{REPO_ID}")


if __name__ == "__main__":
    main()