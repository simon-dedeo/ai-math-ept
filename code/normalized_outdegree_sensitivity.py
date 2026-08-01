"""Test reuse tails after Coq and Lean constructor normalization.

This is the out-degree companion to ``normalized_term_arity.py``.  It uses the
same root-proof boundary, binary applications, and binder-name removal, then
refits power-law alternatives on the declared tail k >= 10.  Results are a
representation-sensitivity check, not a replacement for the archived Coq
replication: recursively expanded library proofs and the root proof value are
different scientific objects.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from coq_lean_confirmation import comparison_counts, model_comparison
from normalized_term_arity import CORE, ROOT, coq_root_dag, lean_root_dag


OUT = ROOT / "results" / "normalized_outdegree"


def out_degrees(dag, shared_core: bool) -> np.ndarray:
    """Return reuse degree in the induced normalized constructor graph."""
    included = np.asarray(
        [label == "Atom" or label in CORE for label in dag.labels]
        if shared_core else [True] * len(dag.labels),
        dtype=bool,
    )
    parents: defaultdict[int, set[int]] = defaultdict(set)
    for parent, children in enumerate(dag.children):
        if not included[parent]:
            continue
        for child in set(children):
            if included[child]:
                parents[child].add(parent)
    return np.asarray([len(parents[node]) for node in range(len(dag.labels)) if included[node]],
                      dtype=int)


def fit_row(corpus: str, name: str, dag, schema: str) -> dict:
    degrees = out_degrees(dag, shared_core=schema == "shared binary core")
    fit = model_comparison(degrees, xmin=10)
    row = {
        "corpus": corpus,
        "name": name,
        "schema": schema,
        "nodes": int(len(degrees)),
        "positive_nodes": int(np.sum(degrees > 0)),
        "maximum_out_degree": int(np.max(degrees, initial=0)),
    }
    row.update(fit)
    return row


def summarize(rows: list[dict]) -> dict:
    result: dict = {}
    for schema in ("shared binary core", "all normalized constructors"):
        result[schema] = {}
        for corpus in sorted({row["corpus"] for row in rows}):
            group = [row for row in rows if row["schema"] == schema and row["corpus"] == corpus]
            fitted = [row for row in group if row.get("alpha_powerlaw") is not None]
            alphas = [row["alpha_powerlaw"] for row in fitted]
            result[schema][corpus] = {
                "n_networks": len(group),
                "n_fixed_xmin_fits": len(fitted),
                "median_nodes": float(np.median([row["nodes"] for row in group])),
                "median_maximum_out_degree": float(np.median(
                    [row["maximum_out_degree"] for row in group])),
                "median_tail_n_when_fitted": (
                    float(np.median([row["n_tail"] for row in fitted])) if fitted else None
                ),
                "median_alpha_xmin10": float(np.median(alphas)) if alphas else None,
                "model_comparisons": comparison_counts(fitted),
            }
    return result


def paired_summary(rows: list[dict], schema: str) -> dict:
    by_side = {
        corpus: {row["name"]: row for row in rows
                 if row["schema"] == schema and row["corpus"] == corpus}
        for corpus in ("Matched human Lean root values", "Matched AI Lean root values")
    }
    common = sorted(set.intersection(*(set(value) for value in by_side.values())))
    eligible = [name for name in common
                if all(by_side[corpus][name].get("alpha_powerlaw") is not None
                       for corpus in by_side)]
    if not eligible:
        return {"n_pairs": 0}
    human = np.asarray([by_side["Matched human Lean root values"][name]["alpha_powerlaw"]
                        for name in eligible])
    ai = np.asarray([by_side["Matched AI Lean root values"][name]["alpha_powerlaw"]
                     for name in eligible])
    test = stats.wilcoxon(ai, human) if np.any(ai != human) else None
    return {
        "n_pairs": len(eligible),
        "median_human_alpha_xmin10": float(np.median(human)),
        "median_ai_alpha_xmin10": float(np.median(ai)),
        "median_paired_difference_ai_minus_human": float(np.median(ai - human)),
        "wilcoxon_p": float(test.pvalue) if test is not None else 1.0,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    exclusions: list[dict] = []

    def add(corpus: str, name: str, dag) -> None:
        for schema in ("shared binary core", "all normalized constructors"):
            rows.append(fit_row(corpus, name, dag, schema))

    manifest = json.loads((ROOT / "networks/coq2022_edges/manifest.json").read_text())
    for item in manifest:
        if item["name"] == "euclid_book":
            exclusions.append({"corpus": "Coq root values", "name": item["name"],
                               "reason": "hand-coded dependency list has no root proof AST"})
            continue
        add("Coq root values", item["name"], coq_root_dag(item["name"]))

    study1 = pd.read_csv(ROOT / "results/study1/results.csv")
    lean_names = sorted(study1.loc[study1.name.str.endswith("_term"), "name"])
    for name in lean_names:
        add("Human Lean root values", name,
            lean_root_dag(ROOT / "networks/batch1" / f"{name}.json"))

    pair_ids = pd.read_csv(ROOT / "results/final_synthesis/paired_belief_term0.csv").pair.tolist()
    for pair_id in pair_ids:
        add("Matched human Lean root values", pair_id,
            lean_root_dag(ROOT / "networks/paired_human" / f"{pair_id}_term0.json"))
        add("Matched AI Lean root values", pair_id,
            lean_root_dag(ROOT / "networks/paired_ai" / f"{pair_id}_term0.json"))

    summary = {
        "scope": "normalized root proof values; fixed out-degree tail xmin=10",
        "warning": "not directly interchangeable with recursively expanded historical graphs",
        "exclusions": exclusions,
        "corpora": summarize(rows),
        "matched_pairs": {
            schema: paired_summary(rows, schema)
            for schema in ("shared binary core", "all normalized constructors")
        },
    }
    keys = sorted({key for row in rows for key in row})
    with (OUT / "per_network.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    core = summary["corpora"]["shared binary core"]
    paired = summary["matched_pairs"]["shared binary core"]
    coq = core["Coq root values"]
    lean = core["Human Lean root values"]
    macros = (
        "% Generated by code/normalized_outdegree_sensitivity.py\n"
        f"\\newcommand{{\\NormOutCoqN}}{{{coq['n_networks']}}}\n"
        f"\\newcommand{{\\NormOutCoqFits}}{{{coq['n_fixed_xmin_fits']}}}\n"
        f"\\newcommand{{\\NormOutCoqAlpha}}{{{coq['median_alpha_xmin10']:.3f}}}\n"
        f"\\newcommand{{\\NormOutLeanN}}{{{lean['n_networks']}}}\n"
        f"\\newcommand{{\\NormOutLeanFits}}{{{lean['n_fixed_xmin_fits']}}}\n"
        f"\\newcommand{{\\NormOutLeanAlpha}}{{{lean['median_alpha_xmin10']:.3f}}}\n"
        f"\\newcommand{{\\NormOutPairN}}{{{paired['n_pairs']}}}\n"
        f"\\newcommand{{\\NormOutHumanAlpha}}{{{paired['median_human_alpha_xmin10']:.3f}}}\n"
        f"\\newcommand{{\\NormOutAIAlpha}}{{{paired['median_ai_alpha_xmin10']:.3f}}}\n"
        f"\\newcommand{{\\NormOutPairDiff}}{{{paired['median_paired_difference_ai_minus_human']:.3f}}}\n"
        f"\\newcommand{{\\NormOutPairP}}{{{paired['wilcoxon_p']:.3f}}}\n"
    )
    (ROOT / "report/standalone/normalized_outdegree_numbers.tex").write_text(macros)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
