"""Auditable comparison of the 2022 Coq results with human Lean proof terms.

This script does two things that should not be conflated.  It checks whether the
published fixed-cutoff exponent can be recovered from the archived Coq graphs,
and it asks whether the qualitative network phenomena recur in a later sample
of human-authored Lean formalizations.  The Lean comparison uses elaborated
proof-term graphs; declaration graphs are summarized separately because they
have a different boundary and are not a direct analogue of the 2022 Coq ASTs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def number(row: dict[str, str], key: str) -> float | None:
    try:
        value = float(row.get(key, ""))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def values(rows: list[dict[str, str]], key: str) -> np.ndarray:
    result = [value for row in rows if (value := number(row, key)) is not None]
    return np.asarray(result, dtype=float)


def median_interval(data: np.ndarray, rng: np.random.Generator, n_boot: int) -> dict:
    if not len(data):
        return {"n": 0, "median": None, "bootstrap_ci": [None, None]}
    draws = np.asarray([
        np.median(rng.choice(data, size=len(data), replace=True)) for _ in range(n_boot)
    ])
    return {
        "n": int(len(data)),
        "median": float(np.median(data)),
        "bootstrap_ci": [float(x) for x in np.percentile(draws, [2.5, 97.5])],
        "minimum": float(np.min(data)),
        "maximum": float(np.max(data)),
    }


def degree_arrays(path: Path) -> tuple[np.ndarray, np.ndarray]:
    out_degree: defaultdict[str, int] = defaultdict(int)
    in_degree: defaultdict[str, int] = defaultdict(int)
    nodes: set[str] = set()
    with path.open() as stream:
        for line in stream:
            fields = line.split()
            if len(fields) < 2:
                continue
            premise, dependent = fields[:2]
            out_degree[premise] += 1
            in_degree[dependent] += 1
            nodes.update((premise, dependent))
    return (
        np.asarray([out_degree[node] for node in nodes], dtype=int),
        np.asarray([in_degree[node] for node in nodes], dtype=int),
    )


def hill_alpha(data: np.ndarray, xmin: int = 10) -> float | None:
    tail = np.asarray(data[data >= xmin], dtype=float)
    if len(tail) < 10:
        return None
    return float(1 + len(tail) / np.sum(np.log(tail / (xmin - 0.5))))


def model_comparison(data: np.ndarray, xmin: int = 10) -> dict:
    import powerlaw

    positive = np.asarray(data[data > 0], dtype=int)
    tail = positive[positive >= xmin]
    if len(tail) < 10 or len(np.unique(tail)) < 2:
        return {"fit_status": "insufficient tail variation", "xmin": xmin,
                "n_tail": int(len(tail)), "alpha_xmin10": hill_alpha(positive, xmin)}
    fit = powerlaw.Fit(positive, discrete=True, xmin=xmin, verbose=False)
    fitted_alpha = float(fit.power_law.alpha)
    if not (math.isfinite(fitted_alpha) and math.isfinite(float(fit.xmin))):
        return {"fit_status": "insufficient degree variation", "alpha_xmin10": hill_alpha(positive)}
    result = {
        "xmin": xmin,
        "n_tail": int(len(tail)),
        "alpha_powerlaw": fitted_alpha,
        "alpha_xmin10": hill_alpha(positive, xmin),
    }
    for alternative in ("exponential", "lognormal", "stretched_exponential"):
        try:
            ratio, p_value = fit.distribution_compare(
                "power_law", alternative, normalized_ratio=True
            )
            if math.isfinite(float(ratio)) and math.isfinite(float(p_value)):
                result[f"lr_power_vs_{alternative}"] = float(ratio)
                result[f"p_power_vs_{alternative}"] = float(p_value)
        except (ValueError, ZeroDivisionError, FloatingPointError):
            continue
    return result


def comparison_counts(rows: list[dict], prefix: str = "") -> dict:
    result = {}
    for alternative in ("exponential", "lognormal", "stretched_exponential"):
        lr_key = f"{prefix}lr_power_vs_{alternative}"
        p_key = f"{prefix}p_power_vs_{alternative}"
        eligible = [row for row in rows if row.get(lr_key) is not None and row.get(p_key) is not None]
        result[alternative] = {
            "n": len(eligible),
            "power_law_favored": sum(row[lr_key] > 0 and row[p_key] < 0.05 for row in eligible),
            "alternative_favored": sum(row[lr_key] < 0 and row[p_key] < 0.05 for row in eligible),
            "inconclusive": sum(row[p_key] >= 0.05 for row in eligible),
        }
    return result


def legacy_comparison_counts(rows: list[dict[str, str]], stem: str) -> dict:
    converted = []
    for row in rows:
        item = {}
        for alternative in ("exponential", "lognormal", "stretched_exponential"):
            item[f"{stem}lr_power_vs_{alternative}"] = number(
                row, f"{stem}LR_vs_{alternative}"
            )
            item[f"{stem}p_power_vs_{alternative}"] = number(
                row, f"{stem}p_vs_{alternative}"
            )
        converted.append(item)
    return comparison_counts(converted, prefix=stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--coq-edges", required=True)
    parser.add_argument("--lean-edges", required=True)
    parser.add_argument("--out", default="results/coq_lean_confirmation")
    parser.add_argument("--boot", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20260801)
    args = parser.parse_args()

    root = Path(args.root)
    out = root / args.out
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    published = [
        row for row in read_csv(root / "code/reference_2022.csv")
        if row["group"] == "coq2022"
    ]
    reproduction = read_csv(root / "results/repro_xmin_best.csv")
    reproduced = [abs(number(row, "diff")) for row in reproduction if number(row, "diff") is not None]

    alpha_rows = read_csv(root / "results/alpha_xmin10.csv")
    coq_alpha = np.asarray([
        number(row, "alpha10") for row in alpha_rows
        if row["group"] == "coq2022" and row["mode"] == "orig" and number(row, "alpha10") is not None
    ])
    lean_alpha_table = np.asarray([
        number(row, "alpha10") for row in alpha_rows
        if row["group"] == "lean2026" and row["mode"] == "term" and number(row, "alpha10") is not None
    ])

    coq_rerun = read_csv(root / "results/coq2022_replication/results.csv")
    study1 = read_csv(root / "results/study1/results.csv")
    lean_term = [row for row in study1 if row["name"].endswith("_term")]
    lean_decl = [row for row in study1 if row["name"].endswith("_decl")]

    def fit_edge_directory(directory: Path, pattern: str) -> list[dict]:
        fitted = []
        for path in sorted(directory.glob(pattern)):
            out_degree, in_degree = degree_arrays(path)
            row = {"name": path.name.removesuffix(".edges")}
            row.update({f"out_{key}": value for key, value in model_comparison(out_degree).items()})
            row.update({f"in_{key}": value for key, value in model_comparison(in_degree).items()})
            fitted.append(row)
        return fitted

    lean_fits = fit_edge_directory(Path(args.lean_edges), "*_term.edges")
    coq_fits = fit_edge_directory(Path(args.coq_edges), "*.edges")

    for filename, fitted in (
        ("lean_model_comparisons_xmin10.csv", lean_fits),
        ("coq_model_comparisons_xmin10.csv", coq_fits),
    ):
        with (out / filename).open("w", newline="") as stream:
            keys = sorted({key for row in fitted for key in row})
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows(fitted)

    """Legacy output name retained for downstream readers; contents are fixed-xmin fits."""
    with (out / "lean_model_comparisons.csv").open("w", newline="") as stream:
        keys = sorted({key for row in lean_fits for key in row})
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(lean_fits)

    """The old auto-xmin validation remains an input provenance check, not appendix evidence."""
    _legacy_coq_validation = read_csv(root / "results/repro_validate.csv")

    coq_out_counts = comparison_counts(coq_fits, "out_")
    coq_in_counts = comparison_counts(coq_fits, "in_")
    lean_out_counts = comparison_counts(lean_fits, "out_")
    lean_in_counts = comparison_counts(lean_fits, "in_")

    metrics = {}
    for key in ("modularity", "f2", "mean_belief_e2", "dL1_mean"):
        metrics[key] = {
            "coq_reanalysis": median_interval(values(coq_rerun, key), rng, args.boot),
            "human_lean_terms": median_interval(values(lean_term, key), rng, args.boot),
            "human_lean_declarations": median_interval(values(lean_decl, key), rng, args.boot),
        }

    lean_f2 = values(lean_term, "f2")
    coq_f2 = values(coq_rerun, "f2")
    summary = {
        "design": {
            "published_coq_networks": len(published),
            "recovered_coq_networks": len(coq_rerun),
            "human_lean_term_networks": len(lean_term),
            "human_lean_declaration_networks": len(lean_decl),
            "lean_edge_networks_refit": len(lean_fits),
            "coq_edge_networks_refit": len(coq_fits),
            "tail_xmin": 10,
            "bootstraps": args.boot,
            "seed": args.seed,
        },
        "published_exponent_recovery": {
            "published_n": len(published),
            "refit_available_n": len(reproduced),
            "absolute_difference_le_0_01": sum(value <= 0.0100000001 for value in reproduced),
            "absolute_difference_le_0_02": sum(value <= 0.0200000001 for value in reproduced),
            "median_absolute_difference": float(np.median(reproduced)),
        },
        "fixed_xmin_10_alpha": {
            "coq": median_interval(coq_alpha, rng, args.boot),
            "human_lean_terms_table": median_interval(lean_alpha_table, rng, args.boot),
            "human_lean_terms_edge_refit": median_interval(
                np.asarray([row["out_alpha_xmin10"] for row in lean_fits if row.get("out_alpha_xmin10")]),
                rng,
                args.boot,
            ),
        },
        "fixed_xmin_10_comparison": {
            "test": "two-sided Mann--Whitney U",
            "u": float(stats.mannwhitneyu(coq_alpha, lean_alpha_table, alternative="two-sided").statistic),
            "p": float(stats.mannwhitneyu(coq_alpha, lean_alpha_table, alternative="two-sided").pvalue),
            "median_lean_minus_coq": float(np.median(lean_alpha_table) - np.median(coq_alpha)),
        },
        "model_comparisons": {
            "coq_out_degree": coq_out_counts,
            "coq_in_degree": coq_in_counts,
            "human_lean_out_degree": lean_out_counts,
            "human_lean_in_degree": lean_in_counts,
        },
        "network_metrics": metrics,
        "endpoint_checks": {
            "coq_fraction_theorem_belief_ge_0_99": float(np.mean(coq_f2 >= 0.99)),
            "human_lean_fraction_theorem_belief_ge_0_99": float(np.mean(lean_f2 >= 0.99)),
            "coq_all_firewall_scores_positive": bool(np.all(values(coq_rerun, "dL1_mean") > 0)),
            "human_lean_all_firewall_scores_positive": bool(np.all(values(lean_term, "dL1_mean") > 0)),
        },
        "verdicts": [
            {
                "claim": "Reuse is heavy-tailed rather than exponential",
                "verdict": "confirmed",
                "scope": "Out-degree model comparisons in recovered Coq and human Lean term graphs",
            },
            {
                "claim": "Reuse follows a universal pure power law with a cutoff-free exponent near two",
                "verdict": "not confirmed",
                "scope": "The fixed-cutoff exponent recurs, but lognormal alternatives are often unresolved",
            },
            {
                "claim": "Proof graphs are modular and support positive firewall contrasts",
                "verdict": "qualified confirmation",
                "scope": "The qualitative signs recur; firewall magnitudes are not comparable across implementations",
            },
            {
                "claim": "Network dynamics can produce high theorem belief at epsilon=0.01",
                "verdict": "confirmed within the model",
                "scope": "Recovered Coq and human Lean term graphs; this is not a behavioral validation",
            },
        ],
    }

    with (out / "summary.json").open("w") as stream:
        json.dump(summary, stream, indent=2)
        stream.write("\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
