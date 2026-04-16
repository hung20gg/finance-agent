import json
import numpy as np
from collections import defaultdict

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


def evaluate(pred_data):
    stats = {
        "total": 0,
        "standard_correct": 0,
        "tokens": []
    }

    by_token_bucket = defaultdict(lambda: {"total": 0, "std": 0, "adv": 0})
    missing_ids = 0

    for item in pred_data:
        qid = item.get("id")


        if "score" not in item:
            missing_ids += 1
            continue

        score = item["score"]
        if isinstance(score, dict):
            total_score = score.get("total_score", 0)
            num_tool_calls = score.get("num_tool_calls", float("inf"))
        else:
            total_score = score
            num_tool_calls = float("inf")

        messages = item.get("messages", [])

        stats["total"] += 1

        # ---- tokens ----
        tokens = extract_tokens(item)
        bucket = get_token_bucket(tokens)
        if tokens is not None:
            stats["tokens"].append(tokens)

        by_token_bucket[bucket]["total"] += 1

        # ---- standard ----
        stats["standard_correct"] += total_score
        by_token_bucket[bucket]["std"] += total_score

    return stats, by_token_bucket, missing_ids


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
    print(f"{'Bucket':10s} | Total | Std Acc | Adv Acc")
    print("-" * 50)

    for k in ["<2k", "2k-4k", ">4k", "unknown"]:
        if k not in data:
            continue

        v = data[k]
        total = v["total"]

        std = v["std"] / total if total else 0
        adv = v["adv"] / total if total else 0

        print(f"{k:10s} | {total:5d} | {std:.4f} | {adv:.4f}")

# -----------------------
# Pretty print
# -----------------------

def print_summary(stats):
    total = stats["total"]

    avg, p95, count = compute_token_stats(stats["tokens"])

    print("\n=== OVERALL ===")
    print(f"Total evaluated: {total}")
    print(f"Standard Acc: {stats['standard_correct']}/{total} = {stats['standard_correct']/total:.4f}")
    print(f"Token count: {count}, Avg: {avg:.2f}, P95: {p95:.2f}")


def print_breakdown(title, data):
    print(f"\n=== {title} ===")
    print(f"{'Type':30s} | Total | Std | Adv | AvgTok | P95Tok")
    print("-" * 80)

    for k, v in sorted(data.items()):
        total = v["total"]

        std = v["std"] / total if total else 0
        adv = v["adv"] / total if total else 0

        avg, p95, count = compute_token_stats(v["tokens"])

        print(f"{k:30s} | {total:5d} | {std:.4f} | {adv:.4f} | {avg:7.1f} | {p95:7.1f}")


# -----------------------
# Main
# -----------------------

def run_eval( pred_file):
    pred_data = load_jsonl(pred_file)


    stats,  by_token_bucket, missing = evaluate(pred_data)

    print_summary(stats)
    print(f"\nMissing / skipped (no score): {missing}")

    print_token_bucket(by_token_bucket)


if __name__ == "__main__":

    run_eval("../data/eval_text2chart_matplotlib_val_results_openrouter_openai_gpt-oss-120b_iter1.jsonl")
    run_eval("../data/eval_text2chart_matplotlib_val_results_openrouter_openai_gpt-oss-120b_iter3.jsonl")
    run_eval("../data/eval_text2chart_highchart_val_results_openrouter_openai_gpt-oss-120b.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-4e_iter3.jsonl")
    # run_eval("data_mix_v5/val.jsonl", "../data/eval_val_results_vllm_qwen-sql-v1-4e_iter4.jsonl")