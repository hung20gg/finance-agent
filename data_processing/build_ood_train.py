"""Filter train.norm.jsonl into an OOD-ready training set.

Two reduction stages, both reproducible from train.norm.jsonl:

1. Type holdout    -- drop question_type values that are rare/absent in train
                      but well represented in test, so a model trained here and
                      evaluated on those types in test.jsonl is tested on
                      genuine out-of-distribution generalization rather than
                      pattern memorization.
2. Stratified down -- randomly thin the remaining rows, stratified by
                      question_type with a fixed seed, until the kept set is 60%
                      of the post-type-holdout size (i.e. a further 40% cut).
                      Distribution shape is preserved: every period (2025
                      included) and all question_types stay represented in
                      proportion.

See ood_analysis.md for the rationale behind each stage.
"""
import json
import random
from collections import Counter
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

# Stage 2: keep this fraction of the rows that survive the type holdout.
KEEP_FRACTION = 0.60
SEED = 42


def stratified_downsample(rows, keep_total, seed):
    """Keep exactly `keep_total` rows, allocated per question_type in proportion
    to each type's size (largest-remainder rounding), sampling within each type
    with a fixed seed so all question_types stay represented and the period mix
    (2025 included) is preserved in proportion."""
    by_type = {}
    for r in rows:
        by_type.setdefault(r.get("question_type"), []).append(r)

    total = len(rows)
    # Proportional quota per type with largest-remainder rounding to hit keep_total exactly.
    quotas, remainders = {}, {}
    for qt, items in by_type.items():
        exact = len(items) * keep_total / total
        quotas[qt] = int(exact)  # floor
        remainders[qt] = exact - int(exact)

    deficit = keep_total - sum(quotas.values())
    for qt in sorted(remainders, key=lambda k: remainders[k], reverse=True)[:deficit]:
        quotas[qt] += 1

    rng = random.Random(seed)
    kept, dropped = [], []
    for qt, items in by_type.items():
        order = items[:]
        rng.shuffle(order)
        k = min(quotas[qt], len(items))
        kept.extend(order[:k])
        dropped.extend(order[k:])
    return kept, dropped


def main():
    with open(SOURCE, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    # Stage 1: question_type holdout.
    type_removed = [r for r in rows if r.get("question_type") in OOD_TYPES]
    after_type = [r for r in rows if r.get("question_type") not in OOD_TYPES]

    # Stage 2: stratified downsample to KEEP_FRACTION of the post-type-holdout size.
    keep_total = round(len(after_type) * KEEP_FRACTION)
    kept, downsampled_out = stratified_downsample(after_type, keep_total, SEED)

    out_path = DATA_DIR / "train.ood.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Type-removed rows are the evaluable OOD holdout (these types recur in test.jsonl).
    holdout_path = DATA_DIR / "train_ood_removed.jsonl"
    with open(holdout_path, "w", encoding="utf-8") as f:
        for row in type_removed:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"stage1 type-removed:    {len(type_removed)}")
    print(f"stage2 downsampled-out: {len(downsampled_out)}")
    print(f"kept:                   {len(kept)} -> {out_path}")
    print(f"  ({100 * len(kept) / len(after_type):.1f}% of {len(after_type)} post-type-holdout rows)")
    print(f"type-holdout:           {len(type_removed)} -> {holdout_path}")
    print("Removed type breakdown:", dict(Counter(r.get("question_type") for r in type_removed)))
    print("Kept question_types:   ", len(Counter(r.get("question_type") for r in kept)))


if __name__ == "__main__":
    main()
