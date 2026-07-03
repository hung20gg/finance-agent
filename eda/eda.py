"""
Data-side EDA for FinStat2Vis: distribution + OOD between train / RAG / test.

  train : data_mix_v5/train.clean.jsonl  (fine-tuning questions)
  test  : data_mix_v5/test.clean.jsonl
  RAG   : mcp-server/src/tools/example.md (retrieval pool of (question, SQL) examples)

Outputs: eda/summary.json and eda/figures/*.png
"""
import os, sys, json, re, math
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from sklearn.decomposition import TruncatedSVD

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIG = os.path.join(HERE, "figures")
DM = os.path.join(ROOT, "data_processing", "data_mix_v5")
SPLITS = {"train": "train.clean.jsonl", "val": "val.clean.jsonl", "test": "test.clean.jsonl"}
COL = {"train": "#4C72B0", "RAG": "#55A868", "test": "#DD8452", "val": "#8172B3"}
summary = {}


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def qtext(r):
    return (r.get("question_raw") or r.get("question") or "").strip()


def load_rag():
    c = open(os.path.join(ROOT, "mcp-server", "src", "tools", "example.md"), encoding="utf-8").read()
    out = []
    for b in c.split("## "):
        b = b.strip()
        if not b:
            continue
        q = b.split("\n", 1)[0].strip()
        if q:
            out.append({"question_raw": q})
    return out


def savefig(name):
    plt.tight_layout(); plt.savefig(os.path.join(FIG, name), dpi=150, bbox_inches="tight"); plt.close()
    print("wrote", name)


# ---------------------------------------------------------------- load
data = {k: load_jsonl(os.path.join(DM, v)) for k, v in SPLITS.items()}
data["RAG"] = load_rag()
N = {k: len(v) for k, v in data.items()}
print("sizes:", N)
summary["sizes"] = N

# ---------------------------------------------------------------- 1. composition (train vs test)
def dist(split, field):
    c = Counter()
    for r in data[split]:
        v = r.get(field)
        if isinstance(v, list):
            v = ", ".join(map(str, v))
        c[v] += 1
    return c


def norm_counter(c):
    t = sum(c.values()) or 1
    return {k: v / t for k, v in c.items()}


fields = [("question_family", ["drill_down", "calculate", "compare", "roll_up"]),
          ("answer_type", ["entity", "tuple"]),
          ("reasoning_hops", [1, 2, 3, 4])]
fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
comp = {}
for ax, (f, order) in zip(axes, fields):
    dtr, dte = norm_counter(dist("train", f)), norm_counter(dist("test", f))
    cats = [c for c in order] + [c for c in set(list(dtr) + list(dte)) if c not in order]
    x = np.arange(len(cats)); w = 0.38
    ax.bar(x - w/2, [dtr.get(c, 0) for c in cats], w, label="train", color=COL["train"])
    ax.bar(x + w/2, [dte.get(c, 0) for c in cats], w, label="test", color=COL["test"])
    ax.set_xticks(x); ax.set_xticklabels([str(c) for c in cats], rotation=20, ha="right", fontsize=8)
    ax.set_title(f); ax.set_ylabel("share"); ax.legend(); ax.grid(axis="y", alpha=.3)
    comp[f] = {"train": dtr, "test": dte}
savefig("eda1_composition.png")
summary["composition"] = comp

# ---------------------------------------------------------------- 2. subtype/source coverage
def values_set(split, field):
    s = set()
    for r in data[split]:
        v = r.get(field)
        if isinstance(v, list):
            s.update(map(str, v))
        elif v is not None:
            s.add(str(v))
    return s

cov = {}
for field in ["question_subtype", "sources"]:
    tr, te = values_set("train", field), values_set("test", field)
    inter = te & tr
    cov[field] = {"n_test_values": len(te), "covered_by_train": len(inter),
                  "coverage_pct": round(100 * len(inter) / max(1, len(te)), 1),
                  "test_only": sorted(te - tr)[:20]}
print("coverage:", {k: (v["covered_by_train"], v["n_test_values"]) for k, v in cov.items()})
summary["coverage"] = cov

# entity coverage (stock codes etc. mentioned in 'entities')
tr_ent, te_ent = values_set("train", "entities"), values_set("test", "entities")
summary["entity_coverage"] = {
    "n_test_entities": len(te_ent),
    "covered_by_train": len(te_ent & tr_ent),
    "coverage_pct": round(100 * len(te_ent & tr_ent) / max(1, len(te_ent)), 1),
}
print("entity coverage:", summary["entity_coverage"])

# ---------------------------------------------------------------- 3. question length
fig, ax = plt.subplots(figsize=(7, 4.2))
for k in ["train", "RAG", "test"]:
    L = [len(qtext(r)) for r in data[k]]
    ax.hist(L, bins=40, density=True, histtype="step", lw=2, label=f"{k} (n={N[k]})", color=COL[k])
ax.set_xlabel("question length (chars)"); ax.set_ylabel("density")
ax.set_title("Question-length distribution"); ax.legend(); ax.set_xlim(0, 300)
savefig("eda2_length.png")

# ---------------------------------------------------------------- 4. OOD via TF-IDF NN-distance
tr_q = [qtext(r) for r in data["train"]]
te_q = [qtext(r) for r in data["test"]]
rag_q = [qtext(r) for r in data["RAG"]]

vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)
vec.fit(tr_q + te_q + rag_q)
Xtr, Xte, Xrag = vec.transform(tr_q), vec.transform(te_q), vec.transform(rag_q)


def nn_dist(Xq, Xref, exclude_self=False):
    out = np.zeros(Xq.shape[0]); blk = 128
    for i in range(0, Xq.shape[0], blk):
        sims = linear_kernel(Xq[i:i+blk], Xref)
        if exclude_self:
            for j in range(sims.shape[0]):
                sims[j, i + j] = -1
        out[i:i+blk] = sims.max(axis=1)
    return 1.0 - out


d_te_tr = nn_dist(Xte, Xtr)      # test novelty vs train
d_te_rag = nn_dist(Xte, Xrag)    # test distance to RAG pool
d_tr_rag = nn_dist(Xtr, Xrag)    # train distance to RAG pool (how well RAG covers train)
d_rag_tr = nn_dist(Xrag, Xtr)    # are RAG examples themselves in-distribution wrt train

# size-matched control: a random 100-question train subset, so the RAG comparison
# is fair (NN distance shrinks automatically as the reference pool grows)
rng = np.random.default_rng(0)
sub = rng.choice(Xtr.shape[0], size=len(rag_q), replace=False)
d_te_tr100 = nn_dist(Xte, Xtr[sub])

fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
axes[0].hist(d_te_tr, bins=30, density=True, histtype="step", lw=2, label="test → train (full, 7176)", color=COL["train"])
axes[0].hist(d_te_tr100, bins=30, density=True, histtype="step", lw=2, ls="--", label="test → train (100, control)", color="#777")
axes[0].hist(d_te_rag, bins=30, density=True, histtype="step", lw=2, label="test → RAG (100)", color=COL["RAG"])
axes[0].set_xlabel("nearest-neighbour cosine distance"); axes[0].set_ylabel("density")
axes[0].set_title("How close is each TEST question to train vs. RAG pool"); axes[0].legend(fontsize=8)

axes[1].hist(d_tr_rag, bins=30, density=True, histtype="step", lw=2, label="train → RAG", color=COL["train"])
axes[1].hist(d_te_rag, bins=30, density=True, histtype="step", lw=2, label="test → RAG", color=COL["test"])
axes[1].set_xlabel("nearest-neighbour cosine distance"); axes[1].set_ylabel("density")
axes[1].set_title("RAG-pool coverage of train vs. test"); axes[1].legend()
savefig("eda3_ood_hist.png")

summary["ood"] = {
    "test_to_train": {"median": float(np.median(d_te_tr)), "p90": float(np.quantile(d_te_tr, .9))},
    "test_to_train100_control": {"median": float(np.median(d_te_tr100))},
    "test_to_rag":   {"median": float(np.median(d_te_rag)), "p90": float(np.quantile(d_te_rag, .9))},
    "train_to_rag":  {"median": float(np.median(d_tr_rag)), "p90": float(np.quantile(d_tr_rag, .9))},
    "rag_to_train":  {"median": float(np.median(d_rag_tr))},
}
# fraction of test "well-covered" by RAG (a near example exists, dist<0.4)
for thr in (0.3, 0.4):
    summary["ood"][f"test_covered_by_rag_<{thr}"] = float((d_te_rag < thr).mean())
    summary["ood"][f"test_covered_by_train_<{thr}"] = float((d_te_tr < thr).mean())
print("OOD summary:", json.dumps(summary["ood"], indent=2))

# ---------------------------------------------------------------- 5. 2D map (SVD on TF-IDF)
svd = TruncatedSVD(n_components=2, random_state=0)
# fit on a subset of train for speed + all rag/test
idx = np.linspace(0, len(tr_q) - 1, min(1500, len(tr_q))).astype(int)
allX = vec.transform([tr_q[i] for i in idx] + rag_q + te_q)
P = svd.fit_transform(allX)
ntr, nrag = len(idx), len(rag_q)
fig, ax = plt.subplots(figsize=(7.5, 6))
ax.scatter(P[:ntr, 0], P[:ntr, 1], s=6, alpha=.25, color=COL["train"], label=f"train (n={N['train']})")
ax.scatter(P[ntr:ntr+nrag, 0], P[ntr:ntr+nrag, 1], s=40, alpha=.9, color=COL["RAG"],
           marker="^", edgecolor="k", linewidth=.4, label=f"RAG (n={nrag})")
ax.scatter(P[ntr+nrag:, 0], P[ntr+nrag:, 1], s=12, alpha=.6, color=COL["test"], label=f"test (n={N['test']})")
ax.set_title("TF-IDF semantic map (Truncated SVD)"); ax.set_xlabel("dim 1"); ax.set_ylabel("dim 2")
ax.legend(markerscale=1.5)
savefig("eda4_map.png")

with open(os.path.join(HERE, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
print("wrote summary.json")
