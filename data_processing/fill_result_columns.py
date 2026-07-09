"""Fill missing extra_info.result_columns in JSONL datasets.

Rules:
  - If answer_type == "entity", set result_columns to [].
  - Otherwise, if answer is a dict, set result_columns to list(answer.keys()).

The script updates files in place by default.

Usage:
    python data_processing/fill_result_columns.py data_processing/data_mix_v2/test_final.jsonl
    python data_processing/fill_result_columns.py --dry-run data_processing/data_mix_v2/test_final*.jsonl
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def infer_result_columns(row: Dict[str, Any]) -> List[str]:
    if row.get("answer_type") == "entity":
        return []

    answer = row.get("answer")
    if isinstance(answer, dict):
        return list(answer.keys())

    return []


def update_rows(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    changed_count = 0
    missing_count = 0

    for row in rows:
        extra_info = row.get("extra_info")
        if not isinstance(extra_info, dict):
            extra_info = {}
            row["extra_info"] = extra_info

        if "result_columns" in extra_info:
            continue

        missing_count += 1
        extra_info["result_columns"] = infer_result_columns(row)
        changed_count += 1

    return missing_count, changed_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill missing extra_info.result_columns in JSONL files.")
    parser.add_argument("paths", nargs="+", help="JSONL files to update.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    for raw_path in args.paths:
        path = Path(raw_path)
        rows = read_jsonl(path)
        missing_count, changed_count = update_rows(rows)

        if not args.dry_run and changed_count:
            write_jsonl(path, rows)

        action = "would_update" if args.dry_run else "updated"
        print(
            f"{path}: rows={len(rows)} missing_result_columns={missing_count} "
            f"{action}={changed_count}"
        )


if __name__ == "__main__":
    main()
