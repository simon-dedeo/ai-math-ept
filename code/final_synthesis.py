"""Final, auditable synthesis tables and figures for the EPT/AI-math report.

This script deliberately limits itself to designs that support their estimand:

* source-level paired Lean scripts (same statement, coarse source clustering),
* paired elaborated proof-term DAGs, excluding error-recovery terms, and
* complete matched theorem-by-system blocks for descriptive rank/variance tests.

It does not reuse the old overlapping one-way variance percentages.  For a
complete block, log-scale sums of squares partition exactly into theorem,
system, and residual/interaction components.  Source-paired effects are shown
both pair-weighted and source-balanced so one large source cannot silently set
the estimand.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matched_stats import complete_block, friedman_block


def percentile_ci(x: np.ndarray, rng: np.random.Generator, n_boot: int) -> list[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    vals = [np.median(rng.choice(x, len(x), replace=True)) for _ in range(n_boot)]
    return [float(v) for v in np.percentile(vals, [2.5, 97.5])]


def source_paired(df: pd.DataFrame, h: str, a: str, metric: str,
                  n_boot: int, seed: int) -> tuple[dict, pd.DataFrame]:
    d = df.dropna(subset=[h, a, "source"]).copy()
    d["diff"] = d[a].astype(float) - d[h].astype(float)
    by = d.groupby("source", as_index=False).agg(
        n=("diff", "size"), human_median=(h, "median"),
        ai_median=(a, "median"), diff_median=("diff", "median"))
    rng = np.random.default_rng(seed)
    groups = [g for _, g in d.groupby("source")]
    pooled = []
    balanced = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(groups), len(groups))
        pooled.append(float(np.median(np.concatenate(
            [groups[i]["diff"].to_numpy(float) for i in pick]))))
        balanced.append(float(np.median(
            [np.median(groups[i]["diff"].to_numpy(float)) for i in pick])))
    try:
        p_pair = float(stats.wilcoxon(d["diff"]).pvalue)
    except ValueError:
        p_pair = float("nan")
    try:
        p_source = float(stats.wilcoxon(by["diff_median"]).pvalue)
    except ValueError:
        p_source = float("nan")
    hiqr = float(d[h].quantile(.75) - d[h].quantile(.25))
    rec = {
        "metric": metric, "n_pairs": int(len(d)),
        "n_sources": int(by.source.nunique()),
        "human_median": float(d[h].median()), "ai_median": float(d[a].median()),
        "pair_median_diff": float(d["diff"].median()),
        "pair_boot_ci": percentile_ci(d["diff"].to_numpy(), rng, n_boot),
        "source_cluster_ci_pair_weighted": [float(x) for x in np.percentile(pooled, [2.5, 97.5])],
        "source_balanced_median_diff": float(by.diff_median.median()),
        "source_balanced_ci": [float(x) for x in np.percentile(balanced, [2.5, 97.5])],
        "wilcoxon_pair_p": p_pair, "wilcoxon_source_medians_p": p_source,
        "prob_ai_greater": float((d["diff"] > 0).mean()),
        "prob_equal": float((d["diff"] == 0).mean()),
        "human_iqr": hiqr,
    }
    return rec, by.assign(metric=metric)


def block_variance(block: pd.DataFrame, n_boot: int, seed: int) -> dict:
    """Exact two-way SS partition on log1p values in a complete block."""
    y = np.log1p(block.to_numpy(float))

    def one(z: np.ndarray) -> np.ndarray:
        n, k = z.shape
        grand = z.mean()
        total = ((z - grand) ** 2).sum()
        sp = k * ((z.mean(axis=1) - grand) ** 2).sum()
        ss = n * ((z.mean(axis=0) - grand) ** 2).sum()
        sr = max(float(total - sp - ss), 0.0)
        return np.array([sp, ss, sr], float) / total if total else np.zeros(3)

    obs = one(y)
    rng = np.random.default_rng(seed)
    boots = np.array([one(y[rng.integers(0, len(y), len(y))])
                      for _ in range(n_boot)])
    names = ["problem", "system", "residual_interaction"]
    return {
        "scale": "log1p", "components": {
            name: {"share": float(obs[i]),
                   "bootstrap_ci": [float(x) for x in np.percentile(boots[:, i], [2.5, 97.5])]}
            for i, name in enumerate(names)}}


def analyse_matched(path: Path, problem: str, system: str,
                    n_boot: int, n_perm: int) -> dict:
    d = pd.read_csv(path)
    pm = d.groupby([problem, system]).median(numeric_only=True).reset_index()
    pm = pm.rename(columns={problem: "problem", system: "system"})
    out = {}
    for j, metric in enumerate(["vocab_ratio", "n_lines", "n_have", "n_distinct_premises"]):
        if metric not in pm:
            continue
        block = complete_block(pm, metric)
        if block is None:
            continue
        out[metric] = {
            "systems": [str(x) for x in block.columns],
            "friedman": friedman_block(block, n_perm=n_perm, seed=100 + j),
            "variance_partition": block_variance(block, n_boot=n_boot, seed=200 + j),
        }
    return out


def forest_plot(summary: pd.DataFrame, out: Path, title: str) -> None:
    labels = summary.metric.tolist()
    scale = summary.human_iqr.replace(0, np.nan)
    point = summary.pair_median_diff / scale
    lo = summary.source_cluster_ci_pair_weighted.map(lambda x: x[0]) / scale
    hi = summary.source_cluster_ci_pair_weighted.map(lambda x: x[1]) / scale
    y = np.arange(len(summary))[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(summary) + 1.7))
    ax.axvline(0, color="#333333", lw=1)
    ax.errorbar(point, y, xerr=[point - lo, hi - point], fmt="o",
                color="#1f5a85", ecolor="#82a9c5", capsize=3)
    ax.set_yticks(y, labels)
    ax.set_xlabel("median paired difference / human IQR\n(source-cluster 95% interval)")
    ax.set_title(title, loc="left", weight="bold")
    ax.grid(axis="x", alpha=.2)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".pdf"))
    fig.savefig(out.with_suffix(".png"), dpi=180)
    plt.close(fig)


def alpha_plot(term: pd.DataFrame, out: Path) -> None:
    xs, med, lo, hi = [], [], [], []
    rng = np.random.default_rng(991)
    for xmin in [2, 5, 10]:
        d = (term[f"a_alpha_x{xmin}"] - term[f"h_alpha_x{xmin}"]).dropna().to_numpy(float)
        xs.append(xmin); med.append(float(np.median(d)))
        ci = percentile_ci(d, rng, 10000); lo.append(ci[0]); hi.append(ci[1])
    fig, ax = plt.subplots(figsize=(6.5, 3.7))
    ax.axhline(0, color="#333333", lw=1)
    ax.errorbar(xs, med, yerr=[np.array(med) - lo, np.array(hi) - med],
                marker="o", color="#8e3b46", capsize=4)
    ax.set_xticks(xs)
    ax.set_xlabel(r"fixed tail cutoff $x_{min}$")
    ax.set_ylabel(r"AI $-$ human median paired $\Delta\alpha$")
    ax.set_title("Tail-exponent contrast is cutoff-dependent", loc="left", weight="bold")
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".pdf"))
    fig.savefig(out.with_suffix(".png"), dpi=180)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--boot", type=int, default=10000)
    ap.add_argument("--perm", type=int, default=10000)
    args = ap.parse_args()
    root = Path(args.root)
    out = root / "results" / "final_synthesis"
    figs = root / "report" / "final" / "figures"
    out.mkdir(parents=True, exist_ok=True); figs.mkdir(parents=True, exist_ok=True)

    source = pd.read_csv(root / "results" / "paired_numina_corrected.csv")
    source_metrics = {
        "script lines": "n_lines", "tactic invocations": "n_tactics",
        "inline have steps": "n_have", "premises (loose regex)": "premises_loose",
        "premises (strict dotted)": "premises_strict"}
    source_rows, source_by = [], []
    for j, (label, col) in enumerate(source_metrics.items()):
        rec, by = source_paired(source, f"h_{col}", f"a_{col}", label,
                                args.boot, 1000 + j)
        source_rows.append(rec); source_by.append(by)
    source_summary = pd.DataFrame(source_rows)
    source_summary.to_json(out / "paired_source_summary.json", orient="records", indent=2)
    pd.concat(source_by).to_csv(out / "paired_source_by_cluster.csv", index=False)

    term = pd.read_csv(root / "results" / "paired_term_structure" / "term0.csv")
    term_metrics = {
        "term nodes": "N", "term edges": "E", "sharing ratio": "dedup_ratio",
        "DAG depth": "depth", "maximum reuse": "max_outdeg",
        "reuse Gini": "out_gini", "distinct constants": "n_distinct_constants",
        "constant-node share": "constant_share", r"alpha (xmin=2)": "alpha_x2",
        r"alpha (xmin=5)": "alpha_x5", r"alpha (xmin=10)": "alpha_x10"}
    term_rows, term_by = [], []
    for j, (label, col) in enumerate(term_metrics.items()):
        rec, by = source_paired(term, f"h_{col}", f"a_{col}", label,
                                args.boot, 2000 + j)
        term_rows.append(rec); term_by.append(by)
    term_summary = pd.DataFrame(term_rows)
    term_summary.to_json(out / "paired_term_summary.json", orient="records", indent=2)
    pd.concat(term_by).to_csv(out / "paired_term_by_cluster.csv", index=False)

    matched = {
        "lean_eval": analyse_matched(root / "results" / "matched_leaneval" / "records.csv",
                                     "problem", "model", args.boot, args.perm),
        "hf_census": analyse_matched(root / "results" / "matched_hf_records.csv.gz",
                                     "prob", "system", args.boot, args.perm),
    }
    (out / "matched_blocks.json").write_text(json.dumps(matched, indent=2))

    forest_plot(source_summary, figs / "paired_source_effects",
                "Same statement: source-level proof-script effects")
    forest_plot(term_summary.iloc[:8], figs / "paired_term_effects",
                "Same statement: elaborated proof-term effects")
    alpha_plot(term, figs / "alpha_sensitivity")

    manifest = {
        "bootstraps": args.boot, "permutations": args.perm,
        "paired_source_n": int(len(source)), "paired_source_clusters": int(source.source.nunique()),
        "paired_term_clean_n": int(len(term)), "paired_term_clusters": int(term.source.nunique()),
        "paired_term_exclusion": "both graphs required; excludes either graph containing sorry/SyntheticOpaque",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
