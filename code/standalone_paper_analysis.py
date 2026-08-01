"""Analyses and figures for the standalone same-theorem paper.

The paper distinguishes a proof's *interface* (named premises or elaborated
constants) from its *interior* (local steps and non-constant expression
structure).  It combines corrected source-script pairs, clean elaborated-term
pairs, and component-aware belief simulations.  Uncertainty is estimated by
resampling the 12 coarse NuminaMath source groups.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def f(row: dict[str, str], key: str) -> float:
    return float(row[key])


def percentile_ci(values: list[float] | np.ndarray) -> list[float]:
    return [float(x) for x in np.percentile(np.asarray(values), [2.5, 97.5])]


def clustered_bootstrap(
    rows: list[dict[str, str]],
    statistic: Callable[[list[dict[str, str]]], float],
    n_boot: int,
    rng: np.random.Generator,
) -> list[float]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["source"]].append(row)
    names = sorted(groups)
    draws = []
    for _ in range(n_boot):
        sampled = rng.choice(names, size=len(names), replace=True)
        sample = [row for name in sampled for row in groups[str(name)]]
        draws.append(float(statistic(sample)))
    return draws


def paired_summary(
    rows: list[dict[str, str]],
    h_value: Callable[[dict[str, str]], float],
    a_value: Callable[[dict[str, str]], float],
    n_boot: int,
    rng: np.random.Generator,
    transform: str = "difference",
) -> dict:
    def contrast(row: dict[str, str]) -> float:
        h, a = h_value(row), a_value(row)
        if transform == "log_ratio":
            return math.log(a / h)
        return a - h

    h = np.asarray([h_value(row) for row in rows], dtype=float)
    a = np.asarray([a_value(row) for row in rows], dtype=float)
    delta = np.asarray([contrast(row) for row in rows], dtype=float)
    boot = clustered_bootstrap(
        rows,
        lambda sample: float(np.median([contrast(row) for row in sample])),
        n_boot,
        rng,
    )
    result = {
        "n": len(rows),
        "human_median": float(np.median(h)),
        "ai_median": float(np.median(a)),
        "median_contrast": float(np.median(delta)),
        "cluster_ci": percentile_ci(boot),
        "probability_ai_greater": float(np.mean(delta > 0)),
    }
    if transform == "log_ratio":
        result["median_ratio"] = float(math.exp(result["median_contrast"]))
        result["ratio_cluster_ci"] = [float(math.exp(x)) for x in result["cluster_ci"]]
    return result


def paired_rank_summary(
    rows: list[dict[str, str]],
    h_value: Callable[[dict[str, str]], float],
    a_value: Callable[[dict[str, str]], float],
    n_boot: int,
    rng: np.random.Generator,
) -> dict:
    def rho(sample: list[dict[str, str]]) -> float:
        h = [h_value(row) for row in sample]
        a = [a_value(row) for row in sample]
        return float(stats.spearmanr(h, a).statistic)

    observed = rho(rows)
    boot = clustered_bootstrap(rows, rho, n_boot, rng)
    return {"spearman_rho": observed, "cluster_ci": percentile_ci(boot)}


def source_balanced(
    rows: list[dict[str, str]],
    contrast: Callable[[dict[str, str]], float],
    n_boot: int,
    rng: np.random.Generator,
) -> dict:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["source"]].append(row)
    group_values = {
        name: float(np.median([contrast(row) for row in group]))
        for name, group in groups.items()
    }
    names = sorted(group_values)
    draws = [
        float(np.median([group_values[str(name)] for name in rng.choice(names, len(names), replace=True)]))
        for _ in range(n_boot)
    ]
    return {
        "estimate": float(np.median(list(group_values.values()))),
        "cluster_ci": percentile_ci(draws),
        "by_source": group_values,
    }


def interior_per_constant(row: dict[str, str], side: str) -> float:
    interior = f(row, f"{side}_N") - f(row, f"{side}_n_constants")
    interface = f(row, f"{side}_n_distinct_constants")
    return interior / (interface + 1.0)


def have_per_tactic(row: dict[str, str], side: str) -> float:
    # Small pseudocounts keep zero-have proofs in the paired log-ratio.
    return (f(row, f"{side}_n_have") + 0.5) / (f(row, f"{side}_n_tactics") + 1.0)


def belief_average(row: dict[str, str], side: str) -> float:
    return float(np.mean([f(row, f"{side}_theorem_{eps}") for eps in ("0.1", "0.05", "0.01")]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--boot", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260801)
    args = parser.parse_args()

    root = Path(args.root)
    out = root / "results" / "standalone_paper"
    figures = root / "report" / "standalone" / "figures"
    out.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    source = read_csv(root / "results" / "paired_numina_corrected.csv")
    for row in source:
        row["pair"] = "pair_" + row["uuid"][:8]
    term = read_csv(root / "results" / "paired_term_structure" / "term0.csv")
    belief_rows = read_csv(root / "results" / "final_synthesis" / "paired_belief_term0_r32.csv")
    belief = {row["pair"]: row for row in belief_rows}
    if {row["pair"] for row in term} != set(belief):
        raise ValueError("term and belief pairs do not match exactly")
    combined = [{**row, **belief[row["pair"]]} for row in term]

    summary: dict = {
        "seed": args.seed,
        "bootstraps": args.boot,
        "source_pairs": len(source),
        "term_pairs": len(term),
        "source_groups": len({row["source"] for row in source}),
        "term_source_groups": len({row["source"] for row in term}),
        "source": {},
        "term": {},
        "belief": {},
        "cross_layer": {},
    }

    summary["source"]["lines"] = paired_summary(
        source, lambda r: f(r, "h_n_lines"), lambda r: f(r, "a_n_lines"), args.boot, rng)
    summary["source"]["have"] = paired_summary(
        source, lambda r: f(r, "h_n_have"), lambda r: f(r, "a_n_have"), args.boot, rng)
    summary["source"]["premises_loose"] = paired_summary(
        source, lambda r: f(r, "h_premises_loose"), lambda r: f(r, "a_premises_loose"), args.boot, rng)
    summary["source"]["premises_strict"] = paired_summary(
        source, lambda r: f(r, "h_premises_strict"), lambda r: f(r, "a_premises_strict"), args.boot, rng)
    summary["source"]["have_per_tactic"] = paired_summary(
        source,
        lambda r: have_per_tactic(r, "h"),
        lambda r: have_per_tactic(r, "a"),
        args.boot,
        rng,
        transform="log_ratio",
    )
    summary["source"]["line_pair_correlation"] = paired_rank_summary(
        source, lambda r: f(r, "h_n_lines"), lambda r: f(r, "a_n_lines"), args.boot, rng)
    summary["source"]["have_source_balanced"] = source_balanced(
        source, lambda r: f(r, "a_n_have") - f(r, "h_n_have"), args.boot, rng)

    summary["term"]["nodes"] = paired_summary(
        term, lambda r: f(r, "h_N"), lambda r: f(r, "a_N"), args.boot, rng)
    summary["term"]["distinct_constants"] = paired_summary(
        term,
        lambda r: f(r, "h_n_distinct_constants"),
        lambda r: f(r, "a_n_distinct_constants"),
        args.boot,
        rng,
    )
    summary["term"]["constant_share"] = paired_summary(
        term, lambda r: f(r, "h_constant_share"), lambda r: f(r, "a_constant_share"), args.boot, rng)
    summary["term"]["interior_per_constant"] = paired_summary(
        term,
        lambda r: interior_per_constant(r, "h"),
        lambda r: interior_per_constant(r, "a"),
        args.boot,
        rng,
        transform="log_ratio",
    )
    summary["term"]["node_pair_correlation"] = paired_rank_summary(
        term, lambda r: f(r, "h_N"), lambda r: f(r, "a_N"), args.boot, rng)
    summary["term"]["interior_source_balanced"] = source_balanced(
        term,
        lambda r: math.log(interior_per_constant(r, "a") / interior_per_constant(r, "h")),
        args.boot,
        rng,
    )

    source_by_pair = {row["pair"]: row for row in source}
    overlap = [{**source_by_pair[row["pair"]], **row} for row in term if row["pair"] in source_by_pair]

    def delta_source_interior(row: dict[str, str]) -> float:
        return math.log(have_per_tactic(row, "a") / have_per_tactic(row, "h"))

    def delta_term_interior(row: dict[str, str]) -> float:
        return math.log(interior_per_constant(row, "a") / interior_per_constant(row, "h"))

    def cross_layer_rho(sample: list[dict[str, str]]) -> float:
        return float(stats.spearmanr(
            [delta_source_interior(row) for row in sample],
            [delta_term_interior(row) for row in sample],
        ).statistic)

    cross_rho = cross_layer_rho(overlap)
    cross_boot = clustered_bootstrap(overlap, cross_layer_rho, args.boot, rng)
    summary["cross_layer"] = {
        "n_overlap": len(overlap),
        "spearman_rho": cross_rho,
        "cluster_ci": percentile_ci(cross_boot),
    }

    for eps in ("0.1", "0.05", "0.01"):
        h_key, a_key = f"h_theorem_{eps}", f"a_theorem_{eps}"
        diff = np.asarray([f(row, a_key) - f(row, h_key) for row in combined])
        boot = clustered_bootstrap(
            combined,
            lambda sample, hk=h_key, ak=a_key: float(np.mean([f(row, ak) - f(row, hk) for row in sample])),
            args.boot,
            rng,
        )
        summary["belief"][eps] = {
            "human_median": float(np.median([f(row, h_key) for row in combined])),
            "ai_median": float(np.median([f(row, a_key) for row in combined])),
            "mean_paired_difference": float(np.mean(diff)),
            "cluster_ci": percentile_ci(boot),
        }

    avg_diff = np.asarray([belief_average(row, "a") - belief_average(row, "h") for row in combined])
    avg_boot = clustered_bootstrap(
        combined,
        lambda sample: float(np.mean([belief_average(row, "a") - belief_average(row, "h") for row in sample])),
        args.boot,
        rng,
    )
    summary["belief"]["three_condition_average"] = {
        "mean_paired_difference": float(np.mean(avg_diff)),
        "median_paired_difference": float(np.median(avg_diff)),
        "cluster_ci": percentile_ci(avg_boot),
    }

    def delta_interior(row: dict[str, str]) -> float:
        return math.log(interior_per_constant(row, "a") / interior_per_constant(row, "h"))

    def structure_belief_rho(sample: list[dict[str, str]]) -> float:
        x = [delta_interior(row) for row in sample]
        y = [belief_average(row, "a") - belief_average(row, "h") for row in sample]
        return float(stats.spearmanr(x, y).statistic)

    rho = structure_belief_rho(combined)
    rho_boot = clustered_bootstrap(combined, structure_belief_rho, args.boot, rng)
    summary["belief"]["interior_belief_correlation"] = {
        "spearman_rho": rho,
        "cluster_ci": percentile_ci(rho_boot),
    }

    with (out / "summary.json").open("w") as stream:
        json.dump(summary, stream, indent=2)

    # Machine-readable per-pair table used by the paper's decoupling figure.
    with (out / "term_belief_pairs.csv").open("w", newline="") as stream:
        fields = ["pair", "source", "delta_log_interior_per_constant", "delta_mean_theorem_belief"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in combined:
            writer.writerow({
                "pair": row["pair"],
                "source": row["source"],
                "delta_log_interior_per_constant": delta_interior(row),
                "delta_mean_theorem_belief": belief_average(row, "a") - belief_average(row, "h"),
            })

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 160,
    })
    human_color, ai_color = "#294C60", "#B24C3D"

    # Figure: paired theorem constraint at source and term levels.
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    ax = axes[0]
    hx = np.asarray([f(row, "h_n_lines") for row in source])
    axx = np.asarray([f(row, "a_n_lines") for row in source])
    ax.hexbin(hx, axx, gridsize=34, mincnt=1, bins="log", cmap="Blues", linewidths=0)
    lim = max(np.quantile(hx, .99), np.quantile(axx, .99))
    ax.plot([0, lim], [0, lim], color="0.3", lw=1, ls="--")
    ax.set(xlim=(0, lim), ylim=(0, lim), xlabel="Human script lines", ylabel="AI script lines",
           title=f"Source scripts: $\\rho_s={summary['source']['line_pair_correlation']['spearman_rho']:.2f}$")
    ax = axes[1]
    ht = np.asarray([f(row, "h_N") for row in term])
    at = np.asarray([f(row, "a_N") for row in term])
    ax.scatter(ht, at, s=9, alpha=.35, color=ai_color, edgecolors="none")
    lims = [max(20, min(ht.min(), at.min())), max(ht.max(), at.max())]
    ax.plot(lims, lims, color="0.3", lw=1, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set(xlim=lims, ylim=lims, xlabel="Human term nodes", ylabel="AI term nodes",
           title=f"Elaborated terms: $\\rho_s={summary['term']['node_pair_correlation']['spearman_rho']:.2f}$")
    fig.tight_layout()
    fig.savefig(figures / "theorem_constraint.pdf", bbox_inches="tight")
    fig.savefig(figures / "theorem_constraint.png", bbox_inches="tight")
    plt.close(fig)

    # Figure: interface-interior contrasts and cross-layer validation.
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"width_ratios": [0.9, 1.1]})
    ax = axes[0]
    labels = ["Local claims per tactic", "Internal term nodes per constant"]
    records = [summary["source"]["have_per_tactic"], summary["term"]["interior_per_constant"]]
    estimates = np.asarray([100 * (record["median_ratio"] - 1) for record in records])
    low = np.asarray([100 * (record["ratio_cluster_ci"][0] - 1) for record in records])
    high = np.asarray([100 * (record["ratio_cluster_ci"][1] - 1) for record in records])
    y = np.arange(len(labels))[::-1]
    ax.errorbar(estimates, y, xerr=[estimates - low, high - estimates], fmt="o", color=ai_color,
                ecolor="#D99A8B", capsize=3, lw=1.4, ms=6)
    ax.axvline(0, color="0.25", lw=1)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Median AI/human contrast (%)")
    ax.set_title("Interior expansion", loc="left", weight="bold", fontsize=9, pad=6)
    ax.grid(axis="x", color="0.9")
    ax = axes[1]
    cross_x = np.asarray([delta_source_interior(row) for row in overlap])
    cross_y = np.asarray([delta_term_interior(row) for row in overlap])
    ax.scatter(cross_x, cross_y, s=13, alpha=.35, color=ai_color, edgecolors="none")
    bins = np.array_split(np.argsort(cross_x), 6)
    ax.plot([np.mean(cross_x[ix]) for ix in bins], [np.mean(cross_y[ix]) for ix in bins],
            color="black", marker="o", ms=3, lw=1.2)
    ax.axhline(0, color="0.7", lw=1); ax.axvline(0, color="0.7", lw=1)
    ax.set_xlabel("$\\Delta$ log local claims per tactic")
    ax.set_ylabel("$\\Delta$ log term interior per constant")
    ax.set_title(f"Cross-layer alignment ($n={len(overlap)}$, $\\rho_s={cross_rho:.2f}$)",
                 loc="left", weight="bold", fontsize=9, pad=6)
    fig.tight_layout(w_pad=2.5)
    fig.savefig(figures / "interior_expansion.pdf", bbox_inches="tight")
    fig.savefig(figures / "interior_expansion.png", bbox_inches="tight")
    plt.close(fig)

    # Figure: belief curves and structural/epistemic decoupling.
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"width_ratios": [0.85, 1.15]})
    eps = np.asarray([.01, .05, .10])
    h_curve = [np.mean([f(row, f"h_theorem_{e:g}") for row in combined]) for e in eps]
    a_curve = [np.mean([f(row, f"a_theorem_{e:g}") for row in combined]) for e in eps]
    axes[0].plot(eps, h_curve, marker="o", color=human_color, label="Human")
    axes[0].plot(eps, a_curve, marker="o", color=ai_color, label="AI")
    axes[0].set(xlabel="Local error rate $\\epsilon$", ylabel="Mean theorem belief",
                title="Aggregate belief profiles")
    axes[0].legend(frameon=False)
    axes[0].grid(color="0.92")
    x = np.asarray([delta_interior(row) for row in combined])
    yb = np.asarray([belief_average(row, "a") - belief_average(row, "h") for row in combined])
    axes[1].scatter(x, yb, s=11, alpha=.30, color=ai_color, edgecolors="none")
    bins = np.array_split(np.argsort(x), 8)
    bx = np.asarray([np.mean(x[ix]) for ix in bins])
    by = np.asarray([np.mean(yb[ix]) for ix in bins])
    axes[1].plot(bx, by, color="black", marker="o", ms=3, lw=1.2, label="Binned mean")
    axes[1].axhline(0, color="0.3", lw=1, ls="--")
    axes[1].axvline(0, color="0.7", lw=1)
    axes[1].set(xlabel="$\\Delta$ log internal nodes per constant",
                ylabel="$\\Delta$ mean theorem belief",
                title=f"Structural change is epistemically decoupled ($\\rho_s={rho:.2f}$)")
    axes[1].legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(figures / "belief_decoupling.pdf", bbox_inches="tight")
    fig.savefig(figures / "belief_decoupling.png", bbox_inches="tight")
    plt.close(fig)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
