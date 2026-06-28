import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run.reward_function import compute_score, extract_answer_from_sql_response


SQL_ARGUMENT_KEYS = ("sql", "query", "sql_query", "statement", "generated_sql")


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def maybe_parse_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except Exception:
        return value


def load_dataset(path: str) -> List[Dict[str, Any]]:
    if path.endswith(".jsonl"):
        return load_jsonl(path)

    if path.endswith(".xlsx"):
        import pandas as pd

        dataframes = pd.read_excel(path, sheet_name=None)
        rows: List[Dict[str, Any]] = []
        for _, dataframe in dataframes.items():
            frame = dataframe.where(dataframe.notna(), None)
            rows.extend(frame.to_dict(orient="records"))
        parsed_rows = []
        for row in rows:
            parsed = {key: maybe_parse_json_string(value) for key, value in row.items()}
            parsed_rows.append(parsed)
        return parsed_rows

    raise ValueError(f"Unsupported dataset format: {path}")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def flatten_message_text(messages: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return "\n".join(parts)


def iterate_tool_calls(messages: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for message in messages:
        for tool_call in message.get("tool_calls", []) or []:
            if isinstance(tool_call, dict):
                yield tool_call


def parse_tool_arguments(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    arguments = tool_call.get("function", {}).get("arguments", {})
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        return {}
    try:
        return json.loads(arguments)
    except Exception:
        return {"_raw": arguments}


def find_sql_strings(value: Any) -> List[str]:
    candidates: List[str] = []
    if isinstance(value, str):
        test = value.strip()
        lowered = test.lower()
        if lowered.startswith("select") or lowered.startswith("with"):
            candidates.append(test)
        return candidates
    if isinstance(value, dict):
        for key, item in value.items():
            if key in SQL_ARGUMENT_KEYS:
                candidates.extend(find_sql_strings(item))
            else:
                candidates.extend(find_sql_strings(item))
        return candidates
    if isinstance(value, list):
        for item in value:
            candidates.extend(find_sql_strings(item))
    return candidates


def extract_sql_candidates(messages: List[Dict[str, Any]]) -> List[str]:
    sql_candidates: List[str] = []
    for tool_call in iterate_tool_calls(messages):
        function_name = tool_call.get("function", {}).get("name", "")
        arguments = parse_tool_arguments(tool_call)
        candidates = find_sql_strings(arguments)
        if candidates:
            sql_candidates.extend(candidates)
        elif "sql" in function_name.lower() and isinstance(arguments.get("_raw"), str):
            sql_candidates.extend(find_sql_strings(arguments["_raw"]))
    seen = set()
    deduped = []
    for candidate in sql_candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def enrich_prediction(row: Dict[str, Any], dataset_row: Dict[str, Any]) -> Dict[str, Any]:
    messages = row.get("messages", []) or []
    tool_calls = list(iterate_tool_calls(messages))
    tool_names = [tc.get("function", {}).get("name", "") for tc in tool_calls]
    sql_candidates = extract_sql_candidates(messages)
    answer_text = flatten_message_text(messages).split("</tool_call>")[-1].split("</think>")[-1]
    parsed_answer = extract_answer_from_sql_response(answer_text)

    stored_score = row.get("score", {})
    if stored_score and isinstance(stored_score, dict):
        total_score = safe_float(stored_score.get("total_score"), 0.0)
    else:
        recomputed = compute_score(flatten_message_text(messages), dataset_row.get("answer"))
        stored_score = recomputed
        total_score = safe_float(recomputed.get("total_score"), 0.0)

    return {
        "id": row.get("id"),
        "question": dataset_row.get("question"),
        "question_raw": dataset_row.get("question_raw"),
        "answer_type": dataset_row.get("answer_type"),
        "question_family": dataset_row.get("question_family"),
        "question_subtype": dataset_row.get("question_subtype"),
        "ambiguity": dataset_row.get("ambiguity"),
        "reasoning_hops": dataset_row.get("reasoning_hops"),
        "time_asked": dataset_row.get("time_asked"),
        "entities": dataset_row.get("entities"),
        "metrics": dataset_row.get("metrics"),
        "periods": dataset_row.get("periods"),
        "sources": dataset_row.get("sources"),
        "ground_truth": dataset_row.get("answer"),
        "score": stored_score,
        "total_score": total_score,
        "is_correct": 1 if total_score >= 0.999 else 0,
        "has_partial_credit": 1 if 0 < total_score < 0.999 else 0,
        "num_tool_calls": len(tool_calls),
        "num_sql_tool_calls": sum(1 for name in tool_names if "sql" in name.lower()),
        "tool_names": tool_names,
        "sql_candidates": sql_candidates,
        "last_sql": sql_candidates[-1] if sql_candidates else None,
        "parsed_answer": parsed_answer,
    }


def summarize_group(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    count = len(rows)
    total_score = sum(safe_float(row.get("total_score"), 0.0) for row in rows)
    exact = sum(int(row.get("is_correct", 0)) for row in rows)
    partial = sum(int(row.get("has_partial_credit", 0)) for row in rows)
    any_tool = sum(1 for row in rows if row.get("num_tool_calls", 0) > 0)
    any_sql = sum(1 for row in rows if row.get("num_sql_tool_calls", 0) > 0)
    return {
        "count": count,
        "avg_score": total_score / count if count else 0.0,
        "exact_accuracy": exact / count if count else 0.0,
        "partial_credit_rate": partial / count if count else 0.0,
        "tool_call_rate": any_tool / count if count else 0.0,
        "sql_call_rate": any_sql / count if count else 0.0,
        "avg_tool_calls": sum(row.get("num_tool_calls", 0) for row in rows) / count if count else 0.0,
        "avg_sql_tool_calls": sum(row.get("num_sql_tool_calls", 0) for row in rows) / count if count else 0.0,
    }


def print_summary_table(title: str, grouped: Dict[str, Dict[str, Any]]) -> None:
    print(f"\n{title}")
    print(
        "{:32} {:>8} {:>10} {:>10} {:>10} {:>10}".format(
            "group",
            "count",
            "avg_score",
            "exact_acc",
            "tool_rate",
            "sql_rate",
        )
    )
    for key, summary in sorted(grouped.items(), key=lambda item: item[0]):
        print(
            "{:32} {:>8} {:>10.3f} {:>10.3f} {:>10.3f} {:>10.3f}".format(
                str(key)[:32],
                summary["count"],
                summary["avg_score"],
                summary["exact_accuracy"],
                summary["tool_call_rate"],
                summary["sql_call_rate"],
            )
        )


def build_group_summaries(rows: List[Dict[str, Any]], field: str) -> Dict[str, Dict[str, Any]]:
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = row.get(field)
        if isinstance(key, list):
            key = ",".join(map(str, key))
        buckets[str(key)].append(row)
    return {key: summarize_group(items) for key, items in buckets.items()}


def main():
    parser = argparse.ArgumentParser(description="Evaluate finance-agent SQL traces using the test dataset schema.")
    parser.add_argument("--dataset", required=True, help="Path to dataset JSONL or XLSX.")
    parser.add_argument("--predictions", required=True, help="Path to scripts/evaluate.sh output JSONL.")
    parser.add_argument("--output-json", default="", help="Optional enriched per-example output JSON path.")
    parser.add_argument(
        "--group-by",
        default="answer_type,question_family,ambiguity,reasoning_hops",
        help="Comma-separated fields to summarize.",
    )
    args = parser.parse_args()

    dataset_rows = load_dataset(args.dataset)
    dataset_by_id = {row.get("id"): row for row in dataset_rows if row.get("id")}
    prediction_rows = load_jsonl(args.predictions)

    enriched_rows: List[Dict[str, Any]] = []
    missing_ids: List[str] = []
    for prediction in prediction_rows:
        question_id = prediction.get("id")
        dataset_row = dataset_by_id.get(question_id)
        if dataset_row is None:
            missing_ids.append(str(question_id))
            continue
        enriched_rows.append(enrich_prediction(prediction, dataset_row))

    overall = summarize_group(enriched_rows)
    print_summary_table("Overall", {"all": overall})

    for field in [item.strip() for item in args.group_by.split(",") if item.strip()]:
        print_summary_table(f"By {field}", build_group_summaries(enriched_rows, field))

    if missing_ids:
        print(f"\nMissing dataset ids for {len(missing_ids)} prediction rows.")

    if args.output_json:
        payload = {
            "overall": overall,
            "group_by": {
                field: build_group_summaries(enriched_rows, field)
                for field in [item.strip() for item in args.group_by.split(",") if item.strip()]
            },
            "rows": enriched_rows,
            "missing_ids": missing_ids,
        }
        with open(args.output_json, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        print(f"\nSaved enriched evaluation to {args.output_json}")


if __name__ == "__main__":
    main()
