"""Merge test_bo_sung.jsonl + a balanced sample of test.jsonl into test_final.jsonl (~700 rows).

test_bo_sung.jsonl has no question_type metadata, so it is kept in full as its own
bucket ("bo_sung"). The remaining budget is filled from test.jsonl using an
even-as-possible allocation across question_type, capped by availability per type.
"""
import json
import math
import random
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data_mix_v2"
TARGET_TOTAL = 700
SEED = 42


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def balanced_allocation(counts_by_type, budget):
    """Allocate `budget` items across types as evenly as possible, capped by availability."""
    remaining_types = dict(counts_by_type)
    allocation = defaultdict(int)
    remaining_budget = budget

    while remaining_budget > 0 and remaining_types:
        share = max(1, remaining_budget // len(remaining_types))
        progressed = False
        for qtype in list(remaining_types.keys()):
            if remaining_budget <= 0:
                break
            take = min(share, remaining_types[qtype], remaining_budget)
            if take <= 0:
                continue
            allocation[qtype] += take
            remaining_types[qtype] -= take
            remaining_budget -= take
            progressed = True
            if remaining_types[qtype] == 0:
                del remaining_types[qtype]
        if not progressed:
            break

    return allocation


def main():
    random.seed(SEED)

    bo_sung_raw = load_jsonl(DATA_DIR / "test_bo_sung.jsonl")
    bo_sung = [r for r in bo_sung_raw if r.get("question_raw") != "nan"]
    n_dropped = len(bo_sung_raw) - len(bo_sung)
    if n_dropped:
        print(f"Dropped {n_dropped} test_bo_sung rows with broken question_raw == 'nan'")
    test_rows = load_jsonl(DATA_DIR / "test.jsonl")

    by_type = defaultdict(list)
    for row in test_rows:
        by_type[row.get("question_type", "unknown")].append(row)
    for rows in by_type.values():
        random.shuffle(rows)

    counts_by_type = {qtype: len(rows) for qtype, rows in by_type.items()}
    budget = TARGET_TOTAL - len(bo_sung)
    allocation = balanced_allocation(counts_by_type, budget)

    selected_from_test = []
    for qtype, n in allocation.items():
        selected_from_test.extend(by_type[qtype][:n])

    final_rows = []
    for i, row in enumerate(bo_sung):
        row = dict(row)
        row["id"] = f"test_final-bo_sung-{i:05d}"
        row["question_type"] = row.get("question_type", "bo_sung")
        final_rows.append(row)

    for i, row in enumerate(selected_from_test):
        row = dict(row)
        row["id"] = f"test_final-test-{i:05d}"
        final_rows.append(row)

    random.shuffle(final_rows)

    out_path = DATA_DIR / "test_final.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in final_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    dist = defaultdict(int)
    for row in final_rows:
        dist[row.get("question_type", "unknown")] += 1

    print(f"test_bo_sung: {len(bo_sung)} rows (kept in full, bucket='bo_sung')")
    print(f"sampled from test.jsonl: {len(selected_from_test)} rows across {len(allocation)} question_types")
    print(f"total test_final: {len(final_rows)} rows -> {out_path}")
    print("\nDistribution by question_type in test_final:")
    for qtype, c in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {qtype}: {c}")


if __name__ == "__main__":
    main()
