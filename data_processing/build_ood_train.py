"""Filter train.norm.jsonl into an OOD-ready training set.

Removes question_type values that are rare/absent in train but well
represented in test, so a model trained on train.ood.jsonl and evaluated on
those question_types in test.jsonl is being tested on genuine out-of-
distribution generalization rather than pattern memorization. See
ood_analysis.md for the rationale behind each excluded type.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data_mix_v2"
SOURCE = DATA_DIR / "train.norm.jsonl"
OOD_TYPES = {
    "macro_highest_year",
    "macro_lowest_year",
    "commodity_top",
    "universe_top",
    "stock_vs_commodity_diff",
    "company_vs_company_yearly_diff",
    "index_direct",
}


def main():
    kept, removed = [], []
    with open(SOURCE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            (removed if row.get("question_type") in OOD_TYPES else kept).append(row)

    out_path = DATA_DIR / "train.ood.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    holdout_path = DATA_DIR / "train_ood_removed.jsonl"
    with open(holdout_path, "w", encoding="utf-8") as f:
        for row in removed:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"kept: {len(kept)} -> {out_path}")
    print(f"removed: {len(removed)} -> {holdout_path}")
    from collections import Counter
    print("Removed breakdown:", dict(Counter(r.get("question_type") for r in removed)))


if __name__ == "__main__":
    main()
