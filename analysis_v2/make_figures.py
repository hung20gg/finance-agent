"""Aggregate analysis_v2/records.jsonl, dump summary.json, render all figures (matplotlib only)."""
import os, sys, json, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

df = pd.read_json(os.path.join(HERE, "records.jsonl"), lines=True)
MODELS = ["GPT-OSS-120B", "Qwen3-4B-LoRA"]
C = {"GPT-OSS-120B": "#4C72B0", "Qwen3-4B-LoRA": "#DD8452"}
NITERS = df["iteration"].nunique()
summary = {}


def savefig(name):
    plt.tight_layout()
    plt.savefig(os.path.join(FIG, name), dpi=150, bbox_inches="tight")
    plt.close()
    print("wrote", name)


def grouped_bar(ax, cats, series_by_model, ylabel, title):
    x = np.arange(len(cats)); w = 0.38
    for i, m in enumerate(MODELS):
        ax.bar(x + (i - 0.5) * w, [series_by_model[m].get(c, 0) for c in cats],
               w, label=m, color=C[m])
    ax.set_xticks(x); ax.set_xticklabels(cats, rotation=0)
    ax.set_ylabel(ylabel); ax.set_title(title); ax.legend(); ax.grid(axis="y", alpha=.3)


# ---------------------------------------------------------------- 1. status overall
def fig_status():
    cats = ["advanced", "standard_only", "failed"]
    s = {m: (df[df.model == m].groupby("status").size() / NITERS).to_dict() for m in MODELS}
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_bar(ax, cats, s, "Mean count / iteration",
                f"Overall status (mean over {NITERS} iterations, N=347)")
    for i, m in enumerate(MODELS):
        for j, c in enumerate(cats):
            v = s[m].get(c, 0)
            ax.text(j + (i - .5) * .38, v + 1, f"{v:.0f}", ha="center", fontsize=9)
    savefig("fig1_status_overall.png")
    summary["status"] = s


# ---------------------------------------------------------------- 2. standard_only reasons
def fig_gap():
    cats = ["too_many_tools", "tool_error", "both"]
    so = df[df.status == "standard_only"]
    s = {m: (so[so.model == m].groupby("reason").size() / NITERS).to_dict() for m in MODELS}
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_bar(ax, cats, s, "Mean count / iteration", "Why a correct answer is downgraded (standard_only)")
    savefig("fig2_gap_reasons.png")
    summary["gap_reasons"] = s


# ---------------------------------------------------------------- 3-5 failed cuts
def fig_failed_cut(col, order, fname, title):
    fa = df[df.status == "failed"]
    s = {m: (fa[fa.model == m].groupby(col).size() / NITERS).to_dict() for m in MODELS}
    cats = [c for c in order if any(c in s[m] for m in MODELS)]
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_bar(ax, cats, s, "Mean failed / iteration", title)
    savefig(fname)
    summary[fname] = s


# ---------------------------------------------------------------- 6. top failed subtypes
def fig_subtypes():
    fa = df[df.status == "failed"]
    top = (fa.groupby("subtype").size() / NITERS).nlargest(10)
    cats = list(top.index)
    s = {m: (fa[fa.model == m].groupby("subtype").size() / NITERS).to_dict() for m in MODELS}
    labels = [c.replace("_", " ")[:34] for c in cats]
    x = np.arange(len(cats)); w = .38
    fig, ax = plt.subplots(figsize=(11, 6))
    for i, m in enumerate(MODELS):
        ax.barh(x + (i - .5) * w, [s[m].get(c, 0) for c in cats], w, label=m, color=C[m])
    ax.set_yticks(x); ax.set_yticklabels(labels, fontsize=8); ax.invert_yaxis()
    ax.set_xlabel("Mean failed / iteration"); ax.set_title("Top-10 failed subtypes"); ax.legend()
    ax.grid(axis="x", alpha=.3)
    savefig("fig6_top_subtypes.png")
    summary["top_subtypes"] = {"order": cats, "counts": s}


# ---------------------------------------------------------------- 7. hallucination / failure mechanism
def fig_mechanism():
    cats = ["grounded_error", "unit_scale_error", "ungrounded", "no_answer"]
    nice = {"grounded_error": "grounded\nreasoning err",
            "unit_scale_error": "unit/scale\nerror",
            "ungrounded": "ungrounded\n(hallucination)",
            "no_answer": "no parseable\nanswer"}
    fa = df[df.status == "failed"]
    s = {m: (fa[fa.model == m].groupby("hallucination").size() / NITERS).to_dict() for m in MODELS}
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(cats)); w = .38
    for i, m in enumerate(MODELS):
        vals = [s[m].get(c, 0) for c in cats]
        ax.bar(x + (i - .5) * w, vals, w, label=m, color=C[m])
        for j, v in enumerate(vals):
            ax.text(j + (i - .5) * w, v + .5, f"{v:.0f}", ha="center", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels([nice[c] for c in cats])
    ax.set_ylabel("Mean count / iteration")
    ax.set_title("Failure mechanism decomposition of the failed pool")
    ax.legend(); ax.grid(axis="y", alpha=.3)
    savefig("fig7_failure_mechanism.png")
    summary["mechanism"] = s


# ---------------------------------------------------------------- 8. entropy / stability
def fig_stability():
    rows = []
    for (m, qid), g in df.groupby(["model", "id"]):
        if len(g) < 2:
            continue
        counts = list(g["pred_norm"].value_counts().values)
        H = 0.0; tot = sum(counts)
        for c in counts:
            p = c / tot; H -= p * math.log2(p)
        n_correct = (g["status"] != "failed").sum()  # advanced+standard_only = value-correct
        if len(counts) == 1:
            stab = "stable"
        elif max(counts) >= 2:
            stab = "majority"
        else:
            stab = "unstable"
        # correctness x stability quadrant (value correctness = score==1 i.e. not failed)
        maj_correct = n_correct > len(g) / 2
        if stab == "stable" and maj_correct:
            quad = "robust_correct"
        elif maj_correct:
            quad = "lucky_correct"
        elif stab == "stable":
            quad = "systematic_wrong"
        else:
            quad = "confused_wrong"
        rows.append({"model": m, "id": qid, "entropy": H, "stability": stab,
                     "quad": quad, "n_correct": n_correct})
    sdf = pd.DataFrame(rows)
    sdf.to_json(os.path.join(HERE, "stability.jsonl"), orient="records", lines=True)

    # mean entropy + stability mix
    stab_cats = ["stable", "majority", "unstable"]
    s_stab = {m: (sdf[sdf.model == m].groupby("stability").size()).reindex(stab_cats).fillna(0).to_dict()
              for m in MODELS}
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    grouped_bar(axes[0], stab_cats, s_stab, "# questions (out of 347)",
                "Answer stability across 3 runs")
    axes[0].text(.5, -.16, f"mean entropy (bits): "
                 + "  ".join(f"{m}={sdf[sdf.model==m].entropy.mean():.3f}" for m in MODELS),
                 transform=axes[0].transAxes, ha="center", fontsize=9)
    quad_cats = ["robust_correct", "lucky_correct", "systematic_wrong", "confused_wrong"]
    s_quad = {m: (sdf[sdf.model == m].groupby("quad").size()).reindex(quad_cats).fillna(0).to_dict()
              for m in MODELS}
    grouped_bar(axes[1], [q.replace("_", "\n") for q in quad_cats],
                {m: {q.replace("_", "\n"): s_quad[m][q] for q in quad_cats} for m in MODELS},
                "# questions", "Correctness x stability")
    savefig("fig8_stability.png")
    summary["stability_mix"] = s_stab
    summary["quadrants"] = s_quad
    summary["mean_entropy"] = {m: float(sdf[sdf.model == m].entropy.mean()) for m in MODELS}


# ---------------------------------------------------------------- 9. OOD
def fig_ood():
    # NN-distance distribution + accuracy/hallucination by ID vs OOD
    per_q = df.drop_duplicates("id")[["id", "nn_dist", "ood"]]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].hist(per_q["nn_dist"], bins=30, color="#777", alpha=.8)
    thr = per_q[per_q.ood].nn_dist.min()
    axes[0].axvline(thr, color="red", ls="--", label=f"OOD threshold={thr:.3f}")
    axes[0].set_xlabel("NN cosine distance to training set")
    axes[0].set_ylabel("# test questions"); axes[0].set_title("Novelty distribution (TF-IDF)")
    axes[0].legend()

    rows = {}
    for m in MODELS:
        for ood in [False, True]:
            g = df[(df.model == m) & (df.ood == ood)]
            rows[(m, ood)] = {
                "advanced": (g.status == "advanced").mean(),
                "failed": (g.status == "failed").mean(),
            }
    x = np.arange(2); w = .38
    for i, m in enumerate(MODELS):
        adv = [rows[(m, False)]["advanced"], rows[(m, True)]["advanced"]]
        axes[1].bar(x + (i - .5) * w, adv, w, label=m, color=C[m])
        for j, v in enumerate(adv):
            axes[1].text(j + (i - .5) * w, v + .005, f"{v:.0%}", ha="center", fontsize=9)
    axes[1].set_xticks(x); axes[1].set_xticklabels(["In-distribution", "OOD (top-20%)"])
    axes[1].set_ylabel("Advanced rate"); axes[1].set_title("Advanced rate: ID vs OOD"); axes[1].legend()
    axes[1].grid(axis="y", alpha=.3)
    savefig("fig9_ood.png")
    summary["ood"] = {f"{m}|{'OOD' if o else 'ID'}": rows[(m, o)] for m in MODELS for o in [False, True]}
    summary["ood_n"] = {"OOD": int(per_q.ood.sum()), "ID": int((~per_q.ood).sum())}


fig_status()
fig_gap()
fig_failed_cut("family", ["drill_down", "calculate", "compare", "roll_up"],
               "fig3_failed_family.png", "Failed by question family")
fig_failed_cut("answer_type", ["tuple", "entity"], "fig4_failed_answer_type.png", "Failed by answer type")
fig_failed_cut("hops", [1, 2, 3, 4], "fig5_failed_hops.png", "Failed by reasoning hops")
fig_subtypes()
fig_mechanism()
fig_stability()
fig_ood()

with open(os.path.join(HERE, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2, default=float)
print("\nwrote summary.json")
