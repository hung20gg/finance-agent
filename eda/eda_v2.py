"""
EDA v2 on the data_mix_v2 (final) datasets, with neural embeddings.

Part A -- data EDA on train_final / test_final / RAG pool:
  composition (answer_type, question_type, lang), type-based OOD (test/train
  count ratio, repo-style holdout), embedding OOD (NN distance), semantic map.
Part B -- accuracy + RAG study on the 347-question test set (the only split with
  model predictions, incl. the with-RAG `w_rag` and no-RAG `sql` conditions):
  accuracy by attribute, accuracy vs novelty, and RAG-similarity -> accuracy-uplift.

Embedding model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (fastembed).
"""
import os, sys, json, re, math
from collections import Counter, defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(HERE, "figures_v2"); os.makedirs(FIG, exist_ok=True)
CACHE = os.path.join(HERE, "emb_cache"); os.makedirs(CACHE, exist_ok=True)
DM2 = os.path.join(ROOT, "data_processing", "data_mix_v2")
DM5 = os.path.join(ROOT, "data_processing", "data_mix_v5")
PRED = os.path.join(ROOT, "data", "test_result (Copy)")
sys.path.insert(0, os.path.join(ROOT, "analysis_v2"))
import analyze  # scoring logic (reward_func based)

EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
C = {"train": "#4C72B0", "RAG": "#55A868", "test": "#DD8452"}
summary = {}


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def qtext(r):
    return (r.get("question") or r.get("question_raw") or "").strip()


def load_rag():
    c = open(os.path.join(ROOT, "mcp-server", "src", "tools", "example.md"), encoding="utf-8").read()
    out = []
    for b in c.split("## "):
        b = b.strip()
        if b:
            q = b.split("\n", 1)[0].strip()
            if q:
                out.append(q)
    return out


def savefig(name):
    plt.tight_layout(); plt.savefig(os.path.join(FIG, name), dpi=150, bbox_inches="tight"); plt.close()
    print("wrote", name)


# ---------------------------------------------------------------- embeddings (cached)
_model = None
def embed(texts, tag):
    fp = os.path.join(CACHE, tag + ".npy")
    if os.path.exists(fp):
        return np.load(fp)
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(EMB_MODEL)
    arr = np.array(list(_model.embed(list(texts))), dtype=np.float32)
    arr = arr / (np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9)
    np.save(fp, arr)
    print(f"  embedded {tag}: {arr.shape}")
    return arr


def nn_max_sim(Q, R, exclude_self=False):
    out = np.zeros(Q.shape[0]); blk = 256
    for i in range(0, Q.shape[0], blk):
        s = Q[i:i+blk] @ R.T
        if exclude_self:
            for j in range(s.shape[0]):
                s[j, i + j] = -1
        out[i:i+blk] = s.max(axis=1)
    return out


# ================================================================ PART A
train = load_jsonl(os.path.join(DM2, "train_final.jsonl"))
test = load_jsonl(os.path.join(DM2, "test_final.jsonl"))
rag = load_rag()
summary["sizes"] = {"train_final": len(train), "test_final": len(test), "RAG": len(rag)}
print("sizes", summary["sizes"])

# --- composition (no reasoning_hops, per request) ---
def share(rows, field):
    c = Counter(r.get(field) for r in rows if r.get(field) is not None)
    t = sum(c.values()) or 1
    return {k: v / t for k, v in c.items()}, c

fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
# answer_type train vs test
for ax, field, order in [(axes[0], "answer_type", ["entity", "tuple"])]:
    str_, _ = share(train, field); ste_, _ = share(test, field)
    cats = order
    x = np.arange(len(cats)); w = .38
    ax.bar(x - w/2, [str_.get(c, 0) for c in cats], w, label="train", color=C["train"])
    ax.bar(x + w/2, [ste_.get(c, 0) for c in cats], w, label="test", color=C["test"])
    ax.set_xticks(x); ax.set_xticklabels(cats); ax.set_title("answer_type"); ax.set_ylabel("share"); ax.legend()
# lang (test only -- train_final has no lang)
slang, clang = share(test, "lang")
axes[1].bar(list(slang.keys()), list(slang.values()), color=C["test"])
axes[1].set_title("test_final language"); axes[1].set_ylabel("share")
# question_type count: top-12 in test
tec = Counter(r.get("question_type") for r in test)
trc = Counter(r.get("question_type") for r in train)
top = [t for t, _ in tec.most_common(12)]
x = np.arange(len(top)); w = .4
axes[2].barh(x - w/2, [trc.get(t, 0) for t in top], w, label="train", color=C["train"])
axes[2].barh(x + w/2, [tec.get(t, 0) for t in top], w, label="test", color=C["test"])
axes[2].set_yticks(x); axes[2].set_yticklabels([t[:24] for t in top], fontsize=7); axes[2].invert_yaxis()
axes[2].set_title("top question_type (count)"); axes[2].legend(fontsize=8); axes[2].set_xscale("log")
savefig("v2_1_composition.png")
summary["answer_type"] = {"train": str_, "test": ste_}
summary["lang"] = slang

# --- type-based OOD (repo-style: test types nearly absent in train) ---
te_types = set(tec); held = sorted(t for t in te_types if trc.get(t, 0) <= 3)
ratios = sorted(((t, tec[t], trc.get(t, 0), tec[t] / (trc.get(t, 0) + 0.5)) for t in te_types),
                key=lambda z: -z[3])
summary["type_ood"] = {"n_train_types": len(trc), "n_test_types": len(te_types),
                       "held_out_types": held,
                       "top_ratio": [(t, nt, ntr, round(r, 1)) for t, nt, ntr, r in ratios[:10]]}
print("held-out (OOD) test types:", held)

# ================================================================ embeddings
te_q = [qtext(r) for r in test]
tr_q = [qtext(r) for r in train]
Ete = embed(te_q, "v2_test_final")
Erag = embed(rag, "v2_rag")
# embed a sample of train for speed (full 12k ok but cache); use full
Etr = embed(tr_q, "v2_train_final")

# --- embedding OOD: test->train, test->RAG, size-matched control ---
d_te_tr = 1 - nn_max_sim(Ete, Etr)
d_te_rag = 1 - nn_max_sim(Ete, Erag)
rng = np.random.default_rng(0)
sub = rng.choice(len(Etr), size=len(Erag), replace=False)
d_te_tr_ctl = 1 - nn_max_sim(Ete, Etr[sub])

fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
axes[0].hist(d_te_tr, bins=30, density=True, histtype="step", lw=2, label=f"test→train (full {len(tr_q)})", color=C["train"])
axes[0].hist(d_te_tr_ctl, bins=30, density=True, histtype="step", lw=2, ls="--", label=f"test→train ({len(rag)}, control)", color="#777")
axes[0].hist(d_te_rag, bins=30, density=True, histtype="step", lw=2, label=f"test→RAG ({len(rag)})", color=C["RAG"])
axes[0].set_xlabel("embedding NN distance (1−cos)"); axes[0].set_ylabel("density")
axes[0].set_title("Novelty of test_final vs train / RAG"); axes[0].legend(fontsize=8)
# type-based OOD scatter
nt = [tec[t] for t, _, _, _ in ratios]; ntr = [r[2] for r in ratios]
axes[1].scatter([r[2] for r in ratios], [r[1] for r in ratios], s=20, color="#888")
for t, n_t, n_tr, rr in ratios:
    if rr > 5 and n_t >= 10:
        axes[1].annotate(t[:18], (n_tr, n_t), fontsize=6)
axes[1].set_xlabel("train count (log)"); axes[1].set_ylabel("test count (log)")
axes[1].set_xscale("symlog"); axes[1].set_yscale("log")
axes[1].set_title("question_type: test vs train count (top-left = OOD)")
savefig("v2_2_ood.png")
summary["emb_ood"] = {
    "test_to_train_median": float(np.median(d_te_tr)),
    "test_to_train_ctl_median": float(np.median(d_te_tr_ctl)),
    "test_to_rag_median": float(np.median(d_te_rag)),
    "test_covered_by_rag_<0.4": float((d_te_rag < 0.4).mean()),
    "test_covered_by_train_<0.4": float((d_te_tr < 0.4).mean()),
}
print("emb_ood", json.dumps(summary["emb_ood"], indent=2))

# --- semantic map ---
from sklearn.decomposition import TruncatedSVD
idx = rng.choice(len(Etr), size=min(1500, len(Etr)), replace=False)
allX = np.vstack([Etr[idx], Erag, Ete])
P = TruncatedSVD(n_components=2, random_state=0).fit_transform(allX)
ntr_, nrag_ = len(idx), len(rag)
fig, ax = plt.subplots(figsize=(7.5, 6))
ax.scatter(P[:ntr_, 0], P[:ntr_, 1], s=6, alpha=.22, color=C["train"], label=f"train ({len(tr_q)})")
ax.scatter(P[ntr_:ntr_+nrag_, 0], P[ntr_:ntr_+nrag_, 1], s=40, marker="^", edgecolor="k", linewidth=.4, color=C["RAG"], label=f"RAG ({nrag_})")
ax.scatter(P[ntr_+nrag_:, 0], P[ntr_+nrag_:, 1], s=10, alpha=.5, color=C["test"], label=f"test ({len(te_q)})")
ax.set_title("Semantic map (multilingual-MiniLM embeddings, SVD-2D)"); ax.legend(markerscale=1.4)
savefig("v2_3_map.png")


# ================================================================ PART B  (accuracy on 347 set)
gt5 = {r["id"]: r for r in load_jsonl(os.path.join(DM5, "test.clean.jsonl"))}
PAT = {  # condition -> {model: [files]}
    "sql":   {"GPT-OSS-120B": ["sql/eval_test_results_openrouter_openai_gpt-oss-120b_iter{}.jsonl"],
              "Qwen3-4B-LoRA": ["sql/eval_test_results_vllm_qwen-sql-v2_iter{}.jsonl"]},
    "w_rag": {"GPT-OSS-120B": ["w_rag/eval_test_results_openrouter_openai_gpt-oss-120b_iter{}.jsonl"],
              "Qwen3-4B-LoRA": ["w_rag/eval_test_results_vllm_qwen-sql-v2_iter{}.jsonl"]},
}
ITERS = [1, 2]  # w_rag only has iter1-2, so compare on the same iters


def score_condition(cond):
    """Return {model: {qid: mean correctness over iters}}."""
    res = {}
    for model, pats in PAT[cond].items():
        per_q = defaultdict(list)
        for pat in pats:
            for it in ITERS:
                fp = os.path.join(PRED, pat.format(it))
                if not os.path.exists(fp):
                    continue
                seen = set()
                for item in load_jsonl(fp):
                    qid = item.get("id")
                    if qid not in gt5 or qid in seen:
                        continue
                    seen.add(qid)
                    rec = analyze.analyze_record(item, gt5[qid])
                    per_q[qid].append(1.0 if rec["status"] != "failed" else 0.0)
        res[model] = {q: float(np.mean(v)) for q, v in per_q.items()}
    return res


acc_sql = score_condition("sql")
acc_rag = score_condition("w_rag")

# accuracy by answer_type (sql condition, pooled models)
def acc_by(field, cond_res):
    agg = defaultdict(list)
    for model, qd in cond_res.items():
        for qid, a in qd.items():
            agg[gt5[qid].get(field, "?")].append(a)
    return {k: float(np.mean(v)) for k, v in agg.items()}, {k: len(v) for k, v in agg.items()}

acc_at, n_at = acc_by("answer_type", acc_sql)
acc_fam, n_fam = acc_by("question_family", acc_sql)
summary["accuracy_347"] = {"by_answer_type": acc_at, "by_family": acc_fam,
                           "overall_sql": float(np.mean([a for qd in acc_sql.values() for a in qd.values()])),
                           "overall_wrag": float(np.mean([a for qd in acc_rag.values() for a in qd.values()]))}

fig, axes = plt.subplots(1, 2, figsize=(13, 4.4))
cats = ["entity", "tuple"]
axes[0].bar(cats, [acc_at.get(c, 0) for c in cats], color=C["test"])
for i, c in enumerate(cats):
    axes[0].text(i, acc_at.get(c, 0) + .01, f"{acc_at.get(c,0):.0%}\n(n={n_at.get(c,0)})", ha="center", fontsize=9)
axes[0].set_title("Accuracy by answer_type (347, sql)"); axes[0].set_ylabel("solved rate"); axes[0].set_ylim(0, 1)
famc = ["drill_down", "calculate", "compare", "roll_up"]
axes[1].bar(range(len(famc)), [acc_fam.get(c, 0) for c in famc], color=C["train"])
axes[1].set_xticks(range(len(famc))); axes[1].set_xticklabels(famc, rotation=15)
axes[1].set_title("Accuracy by question_family (347, sql)"); axes[1].set_ylim(0, 1)
savefig("v2_4_accuracy.png")

# --- accuracy vs novelty (embedding NN-dist of 347 test to train_final) ---
v5_q = [qtext(gt5[q]) for q in gt5]
v5_ids = list(gt5.keys())
Ev5 = embed(v5_q, "v2_v5test")
nov = 1 - nn_max_sim(Ev5, Etr)         # novelty vs train_final
rag_sim = nn_max_sim(Ev5, Erag)        # similarity to RAG pool
nov_map = {qid: float(d) for qid, d in zip(v5_ids, nov)}
ragsim_map = {qid: float(s) for qid, s in zip(v5_ids, rag_sim)}

# pooled per-question accuracy (avg over models) for sql and wrag
def pooled(cond_res):
    out = {}
    allq = set().union(*[set(qd) for qd in cond_res.values()])
    for q in allq:
        vals = [cond_res[m][q] for m in cond_res if q in cond_res[m]]
        out[q] = float(np.mean(vals))
    return out
psql, prag = pooled(acc_sql), pooled(acc_rag)
common = [q for q in psql if q in prag and q in nov_map]

# bin by novelty -> accuracy
def binned(xs, ys, nb=5):
    xs = np.array(xs); ys = np.array(ys)
    qs = np.quantile(xs, np.linspace(0, 1, nb + 1))
    cx, cy, cn = [], [], []
    for i in range(nb):
        lo, hi = qs[i], qs[i + 1]
        m = (xs >= lo) & (xs <= hi if i == nb - 1 else xs < hi)
        if m.sum():
            cx.append(xs[m].mean()); cy.append(ys[m].mean()); cn.append(int(m.sum()))
    return cx, cy, cn

fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
bx, by, bn = binned([nov_map[q] for q in common], [psql[q] for q in common])
axes[0].plot(bx, by, "o-", color=C["train"])
axes[0].set_xlabel("novelty: embedding NN-distance to train_final")
axes[0].set_ylabel("solved rate (sql)"); axes[0].set_title("Accuracy vs novelty (347)"); axes[0].set_ylim(0, 1)
axes[0].grid(alpha=.3)

# --- RAG-similarity -> accuracy uplift (w_rag - sql) ---
sim = np.array([ragsim_map[q] for q in common])
up = np.array([prag[q] - psql[q] for q in common])
sx, _, sn = binned(sim, up)
# recompute per-bin sql/wrag/uplift
xs = sim; qs = np.quantile(xs, np.linspace(0, 1, 5 + 1))
bins_s, bins_r, bins_u, bins_c, bins_x = [], [], [], [], []
for i in range(5):
    lo, hi = qs[i], qs[i + 1]
    m = (xs >= lo) & (xs <= hi if i == 4 else xs < hi)
    if m.sum():
        idxs = [common[k] for k in range(len(common)) if m[k]]
        bins_x.append(float(xs[m].mean()))
        bins_s.append(float(np.mean([psql[q] for q in idxs])))
        bins_r.append(float(np.mean([prag[q] for q in idxs])))
        bins_u.append(float(np.mean([prag[q] - psql[q] for q in idxs])))
        bins_c.append(int(m.sum()))
axes[1].plot(bins_x, bins_s, "o-", label="sql (no RAG)", color="#888")
axes[1].plot(bins_x, bins_r, "o-", label="w_rag (with RAG)", color=C["RAG"])
axes[1].bar(bins_x, bins_u, width=(bins_x[1]-bins_x[0])*0.5 if len(bins_x) > 1 else 0.02,
            alpha=.3, color="red", label="uplift (w_rag − sql)")
axes[1].axhline(0, color="k", lw=.6)
axes[1].set_xlabel("RAG similarity (max cos to example pool)")
axes[1].set_ylabel("solved rate / uplift"); axes[1].set_title("RAG similarity → accuracy uplift (347)")
axes[1].legend(fontsize=8); axes[1].grid(alpha=.3)
savefig("v2_5_rag_accuracy.png")

# correlation
from scipy.stats import pearsonr, spearmanr
pr = pearsonr(sim, up); sp = spearmanr(sim, up)
summary["rag_study"] = {
    "overall_sql": summary["accuracy_347"]["overall_sql"],
    "overall_wrag": summary["accuracy_347"]["overall_wrag"],
    "bins_ragsim": bins_x, "bins_sql": bins_s, "bins_wrag": bins_r, "bins_uplift": bins_u, "bins_n": bins_c,
    "corr_ragsim_vs_uplift_pearson": float(pr[0]), "p_pearson": float(pr[1]),
    "corr_ragsim_vs_uplift_spearman": float(sp.correlation), "p_spearman": float(sp.pvalue),
    "rag_sim_median": float(np.median(sim)),
}
print("rag_study", json.dumps(summary["rag_study"], indent=2, default=float))

with open(os.path.join(HERE, "summary_v2.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
print("wrote summary_v2.json")
