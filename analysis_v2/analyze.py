"""
Error Analysis v2 -- real data, with new dimensions:
  - reproduces the original status / family / answer_type / hops / subtype cuts
  - entropy / answer stability across the 3 iterations
  - hallucination (grounded vs ungrounded answers, schema errors, empty-evidence answering)
  - out-of-distribution (TF-IDF nearest-neighbour distance to the training set)

Outputs:
  analysis_v2/records.jsonl      -- one row per (model, iter, question)
  analysis_v2/agg_*.csv          -- aggregate tables used by the figures / report
"""
import json, re, os, sys, math
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "data_processing"))
from reward_func import extract_answer_from_sql_response, compare_json_dicts  # no tokenizer dep

DATA = os.path.join(ROOT, "data", "test_result (Copy)")
GT_FILE = os.path.join(ROOT, "data_processing", "data_mix_v5", "test.clean.jsonl")
TRAIN_FILE = os.path.join(ROOT, "data_processing", "data_mix_v5", "train.clean.jsonl")

MODELS = {
    "GPT-OSS-120B": "eval_test_results_openrouter_openai_gpt-oss-120b_iter{}.jsonl",
    "Qwen3-4B-LoRA": "eval_test_results_vllm_qwen-sql-v2_iter{}.jsonl",
}
ITERS = [1, 2, 3]
TOOL_BUDGET = 8


# ----------------------------------------------------------------------
# IO helpers
# ----------------------------------------------------------------------
def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def build_gt_map(rows):
    return {r["id"]: r for r in rows if "id" in r}


# ----------------------------------------------------------------------
# Scoring (re-implemented, no transformers/tokenizer dependency)
# ----------------------------------------------------------------------
def round_sig(x, sig=4):
    if x == 0:
        return 0
    return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)


def score_label(pred, ground_truth):
    """Mirror run_evaluation_score.recompute_score's label logic."""
    if pred is None:
        return -1.0
    pv = pred["value"]
    if ground_truth is None:
        return 1.0
    if type(pv) != type(ground_truth):
        # allow int/float cross-compare
        if isinstance(ground_truth, (int, float)) and isinstance(pv, (int, float)):
            pass
        else:
            return 0.0
    if isinstance(ground_truth, str):
        return 1.0 if pv == ground_truth else 0.0
    if isinstance(ground_truth, (int, float)) and not isinstance(ground_truth, bool):
        try:
            gt = round_sig(float(ground_truth), 4)
            pr = round_sig(float(pv), 4)
        except Exception:
            return 0.0
        eps = 0.01 if ground_truth <= 10 else 0.001 * ground_truth
        if abs(gt - pr) <= eps:
            return 1.0
        if abs(gt - pr * 100) <= eps:
            return 0.5
        return 0.0
    if isinstance(ground_truth, dict):
        return 1.0 if compare_json_dicts(pv, ground_truth) else 0.0
    return 0.0


def count_tool_calls(messages):
    return sum(1 for m in messages if m.get("role") == "assistant" and m.get("tool_calls"))


def has_tool_error(messages):
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str) and "Error executing tool" in c:
            return True
    return False


# ----------------------------------------------------------------------
# Grounding / hallucination signals
# ----------------------------------------------------------------------
# integers, decimals, comma-grouped thousands, and scientific notation (e.g. 2.33773e+07)
NUM_RE = re.compile(
    r"[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+)(?:[eE][+-]?\d+)?"
)
SQL_ERROR_RE = re.compile(
    r"does not exist|no such (?:column|table)|undefined(?:column|table|function)|"
    r"syntax error|invalid|relation .* does not exist|column .* does not exist",
    re.I,
)
EMPTY_RE = re.compile(r"\[FAILED\]|no data found|returned no rows|empty", re.I)


def parse_numbers(text):
    out = []
    for tok in NUM_RE.findall(text or ""):
        t = tok.replace(",", "")
        try:
            out.append(float(t))
        except Exception:
            pass
    return out


def tool_observations(messages):
    return [m.get("content", "") or "" for m in messages if m.get("role") == "tool"]


def sql_queries(messages):
    qs = []
    for m in messages:
        for tc in (m.get("tool_calls") or []):
            fn = tc.get("function", {}) or {}
            if fn.get("name") == "execute_code":
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"query": args}
                if isinstance(args, dict) and args.get("query"):
                    qs.append(args["query"])
    return qs


# answer = data_value * scale ; scale==1 means grounded as-is, scale!=1 is a unit/format error
SCALES = [1.0, 100.0, 0.01, 1000.0, 0.001, 1e6, 1e-6, 1e9, 1e-9]


def value_match(value, obs_text, obs_numbers):
    """Return 'exact' (in data as-is), 'scaled' (in data up to a unit scale), or None."""
    if isinstance(value, str):
        v = value.strip().lower()
        if v and v in obs_text:
            return "exact"
        # a stringified number?
        nums = parse_numbers(v)
        if len(nums) == 1:
            value = nums[0]
        else:
            return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        for s in SCALES:
            target = value / s
            for n in obs_numbers:
                if abs(n - target) <= max(0.01, abs(target) * 0.01):
                    return "exact" if s == 1.0 else "scaled"
        return None
    return None


TICKER_RE = re.compile(r"\b[A-Z]{2,4}\d?\b")


def atomic_values(pred):
    """Decompose any answer (dict / json-string / scalar) into atomic payload values.

    Tuple answers are frequently emitted as a multi-line JSON *string* that does
    not round-trip through json.loads at extraction time; we recover the dict here
    so grounding is computed on the real cell values rather than the whole blob.
    """
    pv = pred["value"]
    if isinstance(pv, str):
        s = pv.strip()
        if s[:1] in "{[":
            try:
                pv = json.loads(s)
            except Exception:
                pass
    vals = []
    if isinstance(pv, dict):
        for _, lst in pv.items():
            vals.extend(lst if isinstance(lst, list) else [lst])
    elif isinstance(pv, list):
        vals = list(pv)
    elif isinstance(pv, str):
        toks = parse_numbers(pv) + TICKER_RE.findall(pv)
        vals = toks if toks else [pv]
    else:
        vals = [pv]
    return vals


def grounding_stats(pred, messages):
    """Return (grounding_frac, scaled_share) over the answer's atomic values.

    grounding_frac = fraction of values found in observations at ANY unit scale.
    scaled_share   = of the grounded values, fraction matched only after rescaling
                     (i.e., a unit/magnitude error rather than a fabrication).
    """
    if pred is None:
        return None, None
    obs_list = tool_observations(messages)
    obs_text = "\n".join(obs_list).lower()
    obs_numbers = parse_numbers("\n".join(obs_list))
    vals = atomic_values(pred)
    if not vals:
        return 0.0, 0.0
    n_exact = n_scaled = 0
    for v in vals:
        r = value_match(v, obs_text, obs_numbers)
        if r == "exact":
            n_exact += 1
        elif r == "scaled":
            n_scaled += 1
    grounded = n_exact + n_scaled
    gfrac = grounded / len(vals)
    scaled_share = (n_scaled / grounded) if grounded else 0.0
    return gfrac, scaled_share


def is_gold_scale_error(pred, ground_truth):
    """True if the answer equals the gold value(s) up to a 10^k unit factor (k!=0)."""
    def scale_rel(a, b):
        if b == 0 or a == 0:
            return None
        for s in SCALES:
            if s != 1.0 and abs(a - b * s) <= max(1e-6, abs(b * s) * 0.01):
                return s
        return None
    if pred is None or ground_truth is None:
        return False
    pv = pred["value"]
    if isinstance(pv, str):
        nums = parse_numbers(pv)
        pv = nums[0] if len(nums) == 1 else pv
    if isinstance(ground_truth, (int, float)) and isinstance(pv, (int, float)) \
            and not isinstance(ground_truth, bool):
        return scale_rel(float(pv), float(ground_truth)) is not None
    if isinstance(ground_truth, dict) and isinstance(pred["value"], (dict, str)):
        gv = []
        for lst in ground_truth.values():
            gv.extend(lst if isinstance(lst, list) else [lst])
        gv = [x for x in gv if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if not gv:
            return False
        pvs = [x for x in atomic_values(pred) if isinstance(x, (int, float))]
        if len(pvs) < len(gv):
            return False
        hits = sum(1 for g in gv for p in pvs if scale_rel(p, g))
        return hits >= max(2, len(gv) // 2)
    return False


def schema_error_count(messages):
    return sum(1 for o in tool_observations(messages) if SQL_ERROR_RE.search(o))


def empty_result_count(messages):
    return sum(1 for o in tool_observations(messages) if EMPTY_RE.search(o))


def last_query_empty(messages):
    """Did the last execute_code observation fail / return empty?"""
    last = None
    for m in messages:
        if m.get("role") == "tool":
            last = m.get("content", "") or ""
    if last is None:
        return False
    return bool(EMPTY_RE.search(last) or SQL_ERROR_RE.search(last))


# ----------------------------------------------------------------------
# Answer normalisation (for entropy / stability across iterations)
# ----------------------------------------------------------------------
def normalize_answer(pred):
    if pred is None:
        return "<none>"
    pv = pred["value"]
    if isinstance(pv, str):
        s = pv.strip()
        if s[:1] in "{[":
            try:
                pv = json.loads(s)
            except Exception:
                return "s:" + s.lower()
        else:
            return "s:" + s.lower()
    if isinstance(pv, (int, float)) and not isinstance(pv, bool):
        try:
            return "n:" + repr(round_sig(float(pv), 4))
        except Exception:
            return "n:" + str(pv)
    if isinstance(pv, dict):
        try:
            cols = sorted(pv.keys())
            rows = []
            n = max((len(pv[c]) for c in cols if isinstance(pv[c], list)), default=0)
            for i in range(n):
                rows.append(tuple(str(pv[c][i]) if isinstance(pv[c], list) and i < len(pv[c]) else "" for c in cols))
            return "d:" + json.dumps(sorted(rows), ensure_ascii=False)
        except Exception:
            return "d:" + json.dumps(pv, ensure_ascii=False, sort_keys=True)
    return "o:" + str(pv)


def shannon_entropy(counts):
    total = sum(counts)
    if total <= 1:
        return 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h


# ----------------------------------------------------------------------
# Per-record analysis
# ----------------------------------------------------------------------
def analyze_record(item, gt):
    messages = item.get("messages", [])
    ground_truth = gt.get("answer")
    last = messages[-1] if messages else None
    content = (last.get("content", "") or "").split("</think>")[-1] if last else ""
    pred = extract_answer_from_sql_response(content)

    total_score = max(score_label(pred, ground_truth), 0.0)
    raw_score = score_label(pred, ground_truth)
    ntc = count_tool_calls(messages)
    terr = has_tool_error(messages)

    is_standard = total_score == 1.0
    is_advanced = is_standard and ntc <= TOOL_BUDGET and not terr
    if is_advanced:
        status = "advanced"
    elif is_standard:
        status = "standard_only"
    else:
        status = "failed"

    reason = "N/A"
    if status == "standard_only":
        if terr and ntc > TOOL_BUDGET:
            reason = "both"
        elif terr:
            reason = "tool_error"
        else:
            reason = "too_many_tools"

    gfrac, scaled_share = grounding_stats(pred, messages)
    schema_err = schema_error_count(messages)
    empties = empty_result_count(messages)

    # a parseable-but-degenerate answer (e.g. the literal "JSON", a raw unparsed
    # brace blob, or an empty string) carries no usable value -> treat as no answer
    degenerate = False
    if pred is not None and isinstance(pred["value"], str):
        s = pred["value"].strip()
        if (s in {"", "JSON", "json", "N/A", "None", "null"}
                or (("{" in s or "[" in s) and not parse_numbers(s) and not TICKER_RE.search(s))):
            degenerate = True

    # failure-mechanism label, only meaningful for wrong answers
    hall = "correct"
    if status == "failed":
        if pred is None or degenerate:
            hall = "no_answer"           # abstained / unparseable -> not a hallucination
        elif gfrac is not None and gfrac < 0.5:
            hall = "ungrounded"          # values absent from data at any scale -> fabrication
        elif is_gold_scale_error(pred, ground_truth):
            hall = "unit_scale_error"    # right value vs gold, wrong magnitude (e.g. x1000 VND)
        else:
            hall = "grounded_error"      # supported values but wrong selection/aggregation

    empty_evidence_answer = (
        status == "failed" and pred is not None and last_query_empty(messages)
    )

    return {
        "id": item.get("id"),
        "status": status,
        "reason": reason,
        "raw_score": raw_score,
        "num_tool_calls": ntc,
        "has_tool_error": terr,
        "family": gt.get("question_family", "unknown"),
        "answer_type": gt.get("answer_type", "unknown"),
        "subtype": gt.get("question_subtype", "unknown"),
        "hops": gt.get("reasoning_hops", 0),
        "pred_norm": normalize_answer(pred),
        "pred_is_none": pred is None,
        "grounding_frac": gfrac,
        "scaled_share": scaled_share,
        "schema_errors": schema_err,
        "empty_results": empties,
        "hallucination": hall,
        "empty_evidence_answer": bool(empty_evidence_answer),
        "n_sql": len(sql_queries(messages)),
    }


# ----------------------------------------------------------------------
# OOD: TF-IDF nearest-neighbour distance to the training set
# ----------------------------------------------------------------------
def compute_ood(gt_rows):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    import numpy as np

    def qtext(r):
        return (r.get("question_raw") or r.get("question") or "").strip()

    train_rows = load_jsonl(TRAIN_FILE)
    train_q = [qtext(r) for r in train_rows]
    test_q = [qtext(r) for r in gt_rows]

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)
    vec.fit(train_q + test_q)
    Xtr = vec.transform(train_q)
    Xte = vec.transform(test_q)

    # nearest-neighbour cosine similarity (tf-idf rows are L2-normalised by default)
    nn_sim = np.zeros(len(test_q))
    block = 64
    for i in range(0, Xte.shape[0], block):
        sims = linear_kernel(Xte[i:i + block], Xtr)  # cosine since normalised
        nn_sim[i:i + block] = sims.max(axis=1)
    nn_dist = 1.0 - nn_sim

    thr = float(np.quantile(nn_dist, 0.80))  # top-20% most novel = OOD
    out = {}
    for r, d in zip(gt_rows, nn_dist):
        out[r["id"]] = {"nn_dist": float(d), "ood": bool(d >= thr)}
    return out, thr


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    gt_rows = load_jsonl(GT_FILE)
    gt_map = build_gt_map(gt_rows)
    print(f"GT: {len(gt_map)} questions")

    ood_map, ood_thr = compute_ood(gt_rows)
    print(f"OOD threshold (80th pct NN-distance): {ood_thr:.4f}; "
          f"{sum(v['ood'] for v in ood_map.values())} flagged OOD")

    records = []
    for model, pat in MODELS.items():
        for it in ITERS:
            path = os.path.join(DATA, "sql", pat.format(it))
            if not os.path.exists(path):
                print("MISSING", path); continue
            data = load_jsonl(path)
            n = 0
            for item in data:
                qid = item.get("id")
                if qid not in gt_map:
                    continue
                rec = analyze_record(item, gt_map[qid])
                rec["model"] = model
                rec["iteration"] = it
                rec["ood"] = ood_map.get(qid, {}).get("ood", False)
                rec["nn_dist"] = ood_map.get(qid, {}).get("nn_dist", None)
                records.append(rec)
                n += 1
            print(f"{model} iter{it}: {n} scored")

    with open(os.path.join(HERE, "records.jsonl"), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} records")
    return records


if __name__ == "__main__":
    main()
