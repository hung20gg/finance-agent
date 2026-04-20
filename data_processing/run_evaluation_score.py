import json
import sys
import os
import numpy as np
from collections import defaultdict

# Import reward helpers from the same package
sys.path.insert(0, os.path.dirname(__file__))
from reward_func import extract_answer_from_sql_response, compare_json_dicts
import math

# -----------------------
# Utils
# -----------------------

def load_jsonl(path):
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def has_tool_error(messages):
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str) and "Error executing tool" in content:
            return True
    return False


def extract_tokens(item):
    """
    Approximate tokens using total character count / 4.
    Includes all message content.
    """
    total_chars = 0

    for m in item.get("messages", []):
        content = m.get("content", "")

        if isinstance(content, str):
            total_chars += len(content)

        if "tool_calls" in m:
            total_chars += len(str(m["tool_calls"]))

        # if content is structured (rare but safe)
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict):
                    total_chars += len(str(c.get("text", "")))

    if total_chars == 0:
        return None

    return total_chars / 3.0


def get_token_bucket(tokens):
    if tokens is None:
        return "unknown"
    if tokens < 2000:
        return "<2k"
    elif tokens < 4000:
        return "2k-4k"
    else:
        return ">4k"


# -----------------------
# Core logic
# -----------------------

def build_gt_map(gt_data):
    return {item["id"]: item for item in gt_data if "id" in item}


def recompute_score(messages: list, ground_truth) -> dict:
    """Recalculate the reward from the last assistant message."""
    # Count tool calls from messages
    num_tool_calls = sum(
        1 for m in messages
        if m.get("role") == "assistant" and m.get("tool_calls")
    )

    # Answer is always in the last message
    last_msg = messages[-1] if messages else None
    if last_msg is None:
        return {"total_score": 0.0, "num_tool_calls": num_tool_calls, "error": "No messages"}

    content = (last_msg.get("content", "") or "").split('</think>')[-1]
    pred = extract_answer_from_sql_response(content)

    if pred is None:
        return {
            "total_score": -1.0,
            "num_tool_calls": num_tool_calls,
            "error": "Could not extract answer from response",
        }

    def round_sig(x, sig=4):
        if x == 0:
            return 0
        return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)

    label = 0.0
    if ground_truth is None:
        label = 1.0
    elif type(pred["value"]) != type(ground_truth):
        label = 0.0
    elif isinstance(ground_truth, str):
        label = 1.0 if pred["value"] == ground_truth else 0.0
    elif isinstance(ground_truth, float):
        eps = 0.01
        if ground_truth > 10:
            eps = 0.001 * ground_truth
        gt = round_sig(ground_truth, 4)
        pr = round_sig(pred["value"], 4)
        if abs(gt - pr) <= eps:
            label = 1.0
        elif abs(gt - pr * 100) <= eps:
            label = 0.5  # soft score: correct value but missing percentage conversion
        else:
            label = 0.0
    elif isinstance(ground_truth, int):
        label = 1.0 if pred["value"] == ground_truth else 0.0
    elif isinstance(ground_truth, dict):
        label = compare_json_dicts(pred["value"], ground_truth)

    return {
        "total_score": float(label),
        "num_tool_calls": num_tool_calls,
        "pred": pred,
        "ground_truth": ground_truth,
    }


def evaluate(pred_data, gt_map):
    stats = {
        "total": 0,
        "standard_correct": 0,
        "soft_correct": 0,  # standard + soft (score >= 0.5)
        "advanced_correct": 0,
        "tokens": []
    }

    by_answer_type = defaultdict(lambda: {"total": 0, "std": 0, "soft": 0, "adv": 0, "tokens": []})
    by_family = defaultdict(lambda: {"total": 0, "std": 0, "soft": 0, "adv": 0, "tokens": []})
    by_token_bucket = defaultdict(lambda: {"total": 0, "std": 0, "soft": 0, "adv": 0})
    missing_ids = 0

    for item in pred_data:
        qid = item.get("id")
        if qid not in gt_map:
            continue

        gt = gt_map[qid]
        messages = item.get("messages", [])

        if not messages:
            missing_ids += 1
            continue

        # Recalculate reward from last message (ignore pre-computed score)
        ground_truth = gt.get("answer")
        original_score = item.get("score",{}).get("total_score")
        
        score = recompute_score(messages, ground_truth)
        if score["total_score"] != original_score:
            print(qid, original_score, score)

        total_score = max(score.get("total_score", 0.0), 0.0)  # ensure non-negative
        num_tool_calls = score.get("num_tool_calls", float("inf"))

        answer_type = gt.get("answer_type", "unknown")
        family = gt.get("question_family", "unknown")

        stats["total"] += 1
        by_answer_type[answer_type]["total"] += 1
        by_family[family]["total"] += 1

        # ---- tokens ----
        tokens = extract_tokens(item)
        bucket = get_token_bucket(tokens)
        if tokens is not None:
            stats["tokens"].append(tokens)
            by_answer_type[answer_type]["tokens"].append(tokens)
            by_family[family]["tokens"].append(tokens)

        by_token_bucket[bucket]["total"] += 1

        # ---- standard (exact match: score == 1) ----
        if total_score == 1.0:
            stats["standard_correct"] += 1
            by_answer_type[answer_type]["std"] += 1
            by_family[family]["std"] += 1
            by_token_bucket[bucket]["std"] += 1

        # ---- soft benchmark (score >= 0.5: standard + soft-match) ----
        # soft-match = correct value but missing the ÷100 percentage conversion
        if total_score >= 0.5:
            stats["soft_correct"] += 1
            by_answer_type[answer_type]["soft"] += 1
            by_family[family]["soft"] += 1
            by_token_bucket[bucket]["soft"] += 1

        # ---- advanced (exact match, <=8 tool calls, no errors) ----
        if (
            total_score == 1.0
            and num_tool_calls <= 8
            and not has_tool_error(messages)
        ):
            stats["advanced_correct"] += 1
            by_answer_type[answer_type]["adv"] += 1
            by_family[family]["adv"] += 1
            by_token_bucket[bucket]["adv"] += 1

    return stats, by_answer_type, by_family, by_token_bucket, missing_ids


# -----------------------
# Token stats
# -----------------------

def compute_token_stats(tokens):
    if not tokens:
        return (0, 0, 0)

    arr = np.array(tokens)
    avg = arr.mean()
    p95 = np.percentile(arr, 95)
    count = len(arr)

    return avg, p95, count

def print_token_bucket(data):
    print("\n=== Accuracy by Token Usage ===")
    print(f"{'Bucket':10s} | Total | Std Acc | Soft Acc | Adv Acc")
    print("-" * 60)

    for k in ["<2k", "2k-4k", ">4k", "unknown"]:
        if k not in data:
            continue

        v = data[k]
        total = v["total"]

        std  = v.get("std", 0) / total if total else 0
        soft = v.get("soft", 0) / total if total else 0
        adv  = v.get("adv", 0) / total if total else 0

        print(f"{k:10s} | {total:5d} | {std:.4f}  | {soft:.4f}   | {adv:.4f}")


# -----------------------
# Pretty print
# -----------------------

def print_summary(stats):
    total = stats["total"]

    avg, p95, count = compute_token_stats(stats["tokens"])
    soft = stats.get("soft_correct", 0)

    print("\n=== OVERALL ===")
    print(f"Total evaluated: {total}")
    print(f"Standard Acc:  {stats['standard_correct']}/{total} = {stats['standard_correct']/total:.4f}")
    print(f"Soft Score Acc: {soft}/{total} = {soft/total:.4f}  (correct value, missing %x100 conversion)")
    print(f"Advanced Acc:  {stats['advanced_correct']}/{total} = {stats['advanced_correct']/total:.4f}")
    print(f"Token count: {count}, Avg: {avg:.2f}, P95: {p95:.2f}")


def print_breakdown(title, data):
    print(f"\n=== {title} ===")
    print(f"{'Type':30s} | Total | Std  | Soft | Adv  | AvgTok | P95Tok")
    print("-" * 90)

    for k, v in sorted(data.items()):
        total = v["total"]

        std  = v.get("std", 0) / total if total else 0
        soft = v.get("soft", 0) / total if total else 0
        adv  = v.get("adv", 0) / total if total else 0

        avg, p95, count = compute_token_stats(v["tokens"])

        print(f"{k:30s} | {total:5d} | {std:.4f} | {soft:.4f} | {adv:.4f} | {avg:7.1f} | {p95:7.1f}")


# -----------------------
# Main
# -----------------------
import os
def run_eval(gt_file, pred_file):
    if not os.path.exists(pred_file):
        return
    print(f"\nEvaluating predictions in {pred_file} against ground truth {gt_file}...")
    gt_data = load_jsonl(gt_file)
    pred_data = load_jsonl(pred_file)

    gt_map = build_gt_map(gt_data)

    stats, by_answer_type, by_family, by_token_bucket, missing = evaluate(pred_data, gt_map)

    print_summary(stats)
    print(f"\nMissing / skipped (no score): {missing}")

    print_breakdown("By Answer Type", by_answer_type)
    print_breakdown("By Question Family", by_family)
    print_token_bucket(by_token_bucket)


if __name__ == "__main__":
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-run2.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1_iter1.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1_iter2.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1_iter3.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-run1.jsonl")

    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-acc.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-acc_iter1.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-acc_iter2.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-acc_iter3.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-acc-run1.jsonl")

    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-4e.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-4e_iter1.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-4e_iter2.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-4e_iter3.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/broken_pipeline/eval_val_results_vllm_qwen-sql-v1-4e_iter4.jsonl")
    
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-full_iter1.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-full_iter2.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-full_iter3.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1_iter1.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1_iter2.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1_iter3.jsonl")
    
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-4e_iter1.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-4e_iter2.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-4e_iter3.jsonl")
    
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-acc_iter1.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-acc_iter2.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-acc_iter3.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_openrouter_openai_gpt-oss-120b_iter1.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_openrouter_openai_gpt-oss-120b_iter2.jsonl")
    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_openrouter_openai_gpt-oss-120b_iter3.jsonl")


    # run_eval("data_mix_v5/val.clean.jsonl", "../data/eval_val_results_openrouter_qwen_qwen3.5-397b-a17b.jsonl")


    run_eval("data_mix_v5/test.clean.jsonl", "../data/eval_test_results_openrouter_openai_gpt-oss-120b_iter1.jsonl")
    run_eval("data_mix_v5/test.clean.jsonl", "../data/eval_test_results_openrouter_openai_gpt-oss-120b_iter2.jsonl")
    run_eval("data_mix_v5/test.clean.jsonl", "../data/eval_test_results_openrouter_openai_gpt-oss-120b_iter3.jsonl")

