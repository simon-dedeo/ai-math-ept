"""Match source ``have`` claims to de-Bruijn-aware decoded core binders.

The extractor traverses the final theorem value in pre-order. User-written
``have`` declarations are therefore expected to occur in source order, but
tactic-generated lets may appear between them. We use an exact-name longest
common subsequence (LCS), retain diagnostics for the ambiguity this creates,
and report a conservative subset in which a source name occurs exactly once in
both the source and the elaborated term.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import optimize, stats


def lcs_matches(source_names: list[str], term_names: list[str]) -> list[tuple[int, int]]:
    """Return deterministic exact-name LCS index pairs."""
    n, m = len(source_names), len(term_names)
    table = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if source_names[i] == term_names[j]:
                table[i, j] = table[i + 1, j + 1] + 1
            else:
                table[i, j] = max(table[i + 1, j], table[i, j + 1])
    out: list[tuple[int, int]] = []
    i = j = 0
    while i < n and j < m:
        if source_names[i] == term_names[j] and table[i, j] == table[i + 1, j + 1] + 1:
            out.append((i, j))
            i += 1
            j += 1
        elif table[i + 1, j] >= table[i, j + 1]:
            i += 1
        else:
            j += 1
    return out


def cluster_ratio_ci(
    frame: pd.DataFrame,
    numerator: str,
    denominator: str,
    rng: np.random.Generator,
    boot: int,
) -> list[float | None]:
    if frame[denominator].sum() == 0:
        return [None, None]
    grouped = frame.groupby("source")[[numerator, denominator]].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
    sample = grouped[draws]
    ratios = sample[:, :, 0].sum(axis=1) / np.maximum(sample[:, :, 1].sum(axis=1), 1)
    return [float(x) for x in np.percentile(ratios, [2.5, 97.5])]


def cluster_ratio_difference(
    frame: pd.DataFrame,
    metric: str,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    """AI-minus-human pooled claim-rate difference, resampling sources jointly."""
    h_denominator = float(frame.h_matched.sum())
    a_denominator = float(frame.a_matched.sum())
    if h_denominator == 0 or a_denominator == 0:
        return {
            "estimate_ai_minus_human": None,
            "source_cluster_ci": [None, None],
        }
    columns = [f"h_{metric}", "h_matched", f"a_{metric}", "a_matched"]
    grouped = frame.groupby("source")[columns].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
    sample = grouped[draws].sum(axis=1)
    differences = (
        sample[:, 2] / np.maximum(sample[:, 3], 1)
        - sample[:, 0] / np.maximum(sample[:, 1], 1)
    )
    estimate = (
        frame[f"a_{metric}"].sum() / max(frame.a_matched.sum(), 1)
        - frame[f"h_{metric}"].sum() / max(frame.h_matched.sum(), 1)
    )
    return {
        "estimate_ai_minus_human": float(estimate),
        "source_cluster_ci": [float(x) for x in np.percentile(differences, [2.5, 97.5])],
    }


def retention_difference(
    frame: pd.DataFrame,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    columns = ["h_matched", "h_source_claims", "a_matched", "a_source_claims"]
    grouped = frame.groupby("source")[columns].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
    sampled = grouped[draws].sum(axis=1)
    differences = (
        sampled[:, 2] / np.maximum(sampled[:, 3], 1)
        - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
    )
    human = float(frame.h_matched.sum() / max(frame.h_source_claims.sum(), 1))
    ai = float(frame.a_matched.sum() / max(frame.a_source_claims.sum(), 1))
    return {
        "human": human,
        "ai": ai,
        "ai_minus_human": ai - human,
        "source_cluster_ci": [
            float(x) for x in np.percentile(differences, [2.5, 97.5])
        ],
    }


def conditional_retained_multi_use(
    frame: pd.DataFrame,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    """Multi-occurrence rate conditional on a matched binder occurring at all."""
    work = frame.copy()
    for side in ("h", "a"):
        work[f"{side}_retained"] = (
            work[f"{side}_matched"] - work[f"{side}_zero_term_use"]
        )
    columns = [
        "h_multi_term_use", "h_retained", "a_multi_term_use", "a_retained"
    ]
    grouped = work.groupby("source")[columns].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
    sampled = grouped[draws].sum(axis=1)
    differences = (
        sampled[:, 2] / np.maximum(sampled[:, 3], 1)
        - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
    )
    output: dict[str, Any] = {}
    for side, label in (("h", "human"), ("a", "ai")):
        numerator = int(work[f"{side}_multi_term_use"].sum())
        denominator = int(work[f"{side}_retained"].sum())
        output[label] = {
            "numerator": numerator,
            "denominator": denominator,
            "estimate": float(numerator / denominator) if denominator else None,
        }
    output["ai_minus_human"] = {
        "estimate": output["ai"]["estimate"] - output["human"]["estimate"],
        "source_cluster_ci": [
            float(x) for x in np.percentile(differences, [2.5, 97.5])
        ],
    }
    return output


def transition_summary(
    claims: pd.DataFrame,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    """Source-uptake to term-use transition rates and paired source CIs."""
    frame = claims.copy()
    frame["source_use_class"] = np.select(
        [frame.explicit_uses.eq(0), frame.explicit_uses.eq(1)],
        ["zero", "one"],
        default="multi",
    )
    frame["term_use_class"] = np.select(
        [frame.term_uses.eq(0), frame.term_uses.eq(1)],
        ["zero", "one"],
        default="multi",
    )
    output: dict[str, Any] = {}
    for source_class in ("zero", "one", "multi"):
        stratum = frame[frame.source_use_class.eq(source_class)]
        output[source_class] = {}
        for term_class in ("zero", "one", "multi"):
            cells = (
                stratum.assign(hit=stratum.term_use_class.eq(term_class).astype(int))
                .groupby(["source", "side"])
                .agg(hits=("hit", "sum"), claims=("hit", "size"))
                .reset_index()
            )
            side_summary: dict[str, Any] = {}
            for side, label in (("h", "human"), ("a", "ai")):
                selected = cells[cells.side.eq(side)]
                hits, denominator = int(selected.hits.sum()), int(selected.claims.sum())
                side_summary[label] = {
                    "numerator": hits,
                    "denominator": denominator,
                    "estimate": float(hits / denominator) if denominator else None,
                }

            if cells.empty:
                side_summary["ai_minus_human"] = {
                    "estimate": None,
                    "source_cluster_ci": [None, None],
                }
                output[source_class][term_class] = side_summary
                continue

            wide = cells.pivot(index="source", columns="side", values=["hits", "claims"]).fillna(0)
            for metric, side in (("hits", "h"), ("claims", "h"), ("hits", "a"), ("claims", "a")):
                if (metric, side) not in wide.columns:
                    wide[(metric, side)] = 0
            values = wide[[
                ("hits", "h"), ("claims", "h"), ("hits", "a"), ("claims", "a")
            ]].to_numpy(float)
            draws = rng.integers(0, len(values), size=(boot, len(values)))
            sampled = values[draws].sum(axis=1)
            differences = (
                sampled[:, 2] / np.maximum(sampled[:, 3], 1)
                - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
            )
            side_summary["ai_minus_human"] = {
                "estimate": (
                    side_summary["ai"]["estimate"] - side_summary["human"]["estimate"]
                    if side_summary["ai"]["estimate"] is not None
                    and side_summary["human"]["estimate"] is not None
                    else None
                ),
                "source_cluster_ci": [
                    float(x) for x in np.percentile(differences, [2.5, 97.5])
                ],
            }
            output[source_class][term_class] = side_summary
    return output


def within_proof_generality_term_association(
    claims: pd.DataFrame,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    """Family-minus-instance term outcomes, restricted to proofs containing both.

    Proofs, rather than claims, receive equal weight.  Confidence intervals
    resample source projects so that repeated theorem pairs from one corpus do
    not masquerade as independent evidence.
    """
    output: dict[str, Any] = {}
    outcomes = ("zero_term_use", "one_term_use", "multi_term_use", "term_uses")
    for side, label in (("h", "human"), ("a", "ai")):
        side_claims = claims[claims.side.eq(side)]
        proof_rows: list[dict[str, Any]] = []
        for (pair, source), group in side_claims.groupby(["pair", "source"]):
            family = group[group.generalized_claim]
            instance = group[~group.generalized_claim]
            if family.empty or instance.empty:
                continue
            row: dict[str, Any] = {
                "pair": pair,
                "source": source,
                "family_claims": len(family),
                "instance_claims": len(instance),
            }
            for metric in outcomes:
                row[f"family_{metric}"] = float(family[metric].mean())
                row[f"instance_{metric}"] = float(instance[metric].mean())
                row[f"difference_{metric}"] = (
                    row[f"family_{metric}"] - row[f"instance_{metric}"]
                )
            proof_rows.append(row)

        frame = pd.DataFrame(proof_rows)
        side_output: dict[str, Any] = {
            "proofs": len(frame),
            "source_groups": int(frame.source.nunique()) if len(frame) else 0,
            "family_claims": int(frame.family_claims.sum()) if len(frame) else 0,
            "instance_claims": int(frame.instance_claims.sum()) if len(frame) else 0,
        }
        for metric in outcomes:
            if frame.empty:
                side_output[metric] = {
                    "family_proof_mean": None,
                    "instance_proof_mean": None,
                    "family_minus_instance": None,
                    "source_cluster_ci": [None, None],
                    "paired_wilcoxon_p": None,
                }
                continue
            difference = frame[f"difference_{metric}"].to_numpy(float)
            by_source = (
                frame.groupby("source")[f"difference_{metric}"]
                .agg(["sum", "count"])
                .to_numpy(float)
            )
            draws = rng.integers(0, len(by_source), size=(boot, len(by_source)))
            sampled = by_source[draws].sum(axis=1)
            distribution = sampled[:, 0] / np.maximum(sampled[:, 1], 1)
            try:
                p_value = float(stats.wilcoxon(difference).pvalue)
            except ValueError:
                p_value = 1.0
            side_output[metric] = {
                "family_proof_mean": float(frame[f"family_{metric}"].mean()),
                "instance_proof_mean": float(frame[f"instance_{metric}"].mean()),
                "family_minus_instance": float(difference.mean()),
                "source_cluster_ci": [
                    float(x) for x in np.percentile(distribution, [2.5, 97.5])
                ],
                "paired_wilcoxon_p": p_value,
            }
        output[label] = side_output
    return output


def position_matched_generality_term_association(
    claims: pd.DataFrame,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    """Family-minus-instance term outcomes after within-proof position matching."""
    work = claims.copy()
    outcomes = ("zero_term_use", "one_term_use", "multi_term_use")
    sources = sorted(work.source.unique())
    output: dict[str, Any] = {
        "estimand": (
            "proof-mean family-minus-instance term fate after minimum-cost one-to-one "
            "matching on source claim position"
        )
    }
    for block, caliper in (("all_matches", None), ("caliper_0_25", 0.25)):
        output[block] = {}
        side_frames: dict[str, pd.DataFrame] = {}
        for side, label in (("h", "human"), ("a", "ai")):
            proof_rows: list[dict[str, Any]] = []
            for (pair, source), group in work[work.side.eq(side)].groupby(
                ["pair", "source"]
            ):
                family = group[group.generalized_claim].copy()
                instance = group[~group.generalized_claim].copy()
                if family.empty or instance.empty:
                    continue
                scale = max(float(group.source_claims_in_proof.iloc[0] - 1), 1.0)
                family_position = family.claim_index.to_numpy(float) / scale
                instance_position = instance.claim_index.to_numpy(float) / scale
                cost = np.abs(
                    family_position[:, None] - instance_position[None, :]
                )
                family_i, instance_i = optimize.linear_sum_assignment(cost)
                gaps = cost[family_i, instance_i]
                keep = np.ones(len(gaps), dtype=bool)
                if caliper is not None:
                    keep = gaps <= caliper
                if not keep.any():
                    continue
                family_i, instance_i, gaps = (
                    family_i[keep], instance_i[keep], gaps[keep]
                )
                row: dict[str, Any] = {
                    "pair": pair,
                    "source": source,
                    "matches": int(len(gaps)),
                    "mean_abs_relative_position_gap": float(gaps.mean()),
                }
                for metric in outcomes:
                    row[metric] = float(
                        family.iloc[family_i][metric].to_numpy(float).mean()
                        - instance.iloc[instance_i][metric].to_numpy(float).mean()
                    )
                proof_rows.append(row)

            contrasts = pd.DataFrame(
                proof_rows,
                columns=[
                    "pair", "source", "matches", "mean_abs_relative_position_gap",
                    *outcomes,
                ],
            )
            side_frames[side] = contrasts
            side_output: dict[str, Any] = {
                "eligible_proofs": int(len(contrasts)),
                "matched_claim_pairs": (
                    int(contrasts.matches.sum()) if len(contrasts) else 0
                ),
                "mean_abs_relative_position_gap": (
                    float(contrasts.mean_abs_relative_position_gap.mean())
                    if len(contrasts) else None
                ),
            }
            for metric in outcomes:
                if contrasts.empty:
                    side_output[metric] = {
                        "family_minus_instance": None,
                        "source_cluster_ci": [None, None],
                    }
                    continue
                grouped = (
                    contrasts.groupby("source")[metric]
                    .agg(["sum", "size"])
                    .reindex(sources, fill_value=0)
                    .to_numpy(float)
                )
                draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
                sampled = grouped[draws].sum(axis=1)
                distribution = sampled[:, 0] / np.maximum(sampled[:, 1], 1)
                leave_one_source_out = [
                    float(contrasts.loc[contrasts.source.ne(source), metric].mean())
                    for source in sources
                    if contrasts.source.ne(source).any()
                ]
                if not leave_one_source_out:
                    leave_one_source_out = [float(contrasts[metric].mean())]
                side_output[metric] = {
                    "family_minus_instance": float(contrasts[metric].mean()),
                    "source_cluster_ci": [
                        float(x) for x in np.percentile(distribution, [2.5, 97.5])
                    ],
                    "leave_one_source_out_range": [
                        min(leave_one_source_out), max(leave_one_source_out)
                    ],
                }
            output[block][label] = side_output

        paired = side_frames["h"].merge(
            side_frames["a"], on=["pair", "source"], suffixes=("_human", "_ai")
        )
        paired_output: dict[str, Any] = {
            "eligible_pairs": int(len(paired)),
            "estimand": "AI minus human position-matched family association",
        }
        for metric in outcomes:
            if paired.empty:
                paired_output[metric] = {
                    "ai_minus_human": None,
                    "source_cluster_ci": [None, None],
                }
                continue
            paired_difference = (
                paired[f"{metric}_ai"] - paired[f"{metric}_human"]
            )
            grouped = (
                pd.DataFrame({"source": paired.source, "difference": paired_difference})
                .groupby("source").difference.agg(["sum", "size"])
                .reindex(sources, fill_value=0)
                .to_numpy(float)
            )
            draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
            sampled = grouped[draws].sum(axis=1)
            distribution = sampled[:, 0] / np.maximum(sampled[:, 1], 1)
            paired_output[metric] = {
                "ai_minus_human": float(paired_difference.mean()),
                "source_cluster_ci": [
                    float(x) for x in np.percentile(distribution, [2.5, 97.5])
                ],
            }
        output[block]["paired_both_tracks"] = paired_output
    return output


def tactic_matched_strata(
    claims: pd.DataFrame,
    source_proofs: pd.DataFrame,
    complete_pairs: set[str],
) -> pd.DataFrame:
    """Term-use rates where both proofs use, or both omit, a tactic family."""
    rows: list[dict[str, Any]] = []
    for tactic in ("linarith", "nlinarith", "norm_num", "omega", "ring", "simp"):
        h_col, a_col = f"h_event_{tactic}", f"a_event_{tactic}"
        for condition, mask in (
            ("both", source_proofs[h_col].gt(0) & source_proofs[a_col].gt(0)),
            ("neither", source_proofs[h_col].eq(0) & source_proofs[a_col].eq(0)),
        ):
            eligible = set(source_proofs.loc[mask, "pair"])
            paired_ids = eligible & complete_pairs
            subset = claims[claims.pair.isin(paired_ids)]
            row: dict[str, Any] = {
                "tactic": tactic,
                "condition": condition,
                "pairs": len(paired_ids),
            }
            for side, label in (("h", "human"), ("a", "ai")):
                side_claims = subset[subset.side.eq(side)]
                denominator = len(side_claims)
                row[f"{label}_claims"] = len(side_claims)
                row[f"{label}_zero_share"] = (
                    float(side_claims.term_uses.eq(0).sum() / denominator)
                    if denominator else None
                )
                row[f"{label}_one_share"] = (
                    float(side_claims.term_uses.eq(1).sum() / denominator)
                    if denominator else None
                )
                row[f"{label}_multi_share"] = (
                    float(side_claims.term_uses.gt(1).sum() / denominator)
                    if denominator else None
                )
                row[f"{label}_polarized_share"] = (
                    float(side_claims.term_uses.ne(1).sum() / denominator)
                    if denominator else None
                )
            row["polarized_ai_minus_human"] = (
                row["ai_polarized_share"] - row["human_polarized_share"]
                if row["ai_polarized_share"] is not None
                and row["human_polarized_share"] is not None
                else None
            )
            rows.append(row)
    return pd.DataFrame(rows)


def rate_summary(
    proof_frame: pd.DataFrame,
    side: str,
    numerator: str,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    num, den = f"{side}_{numerator}", f"{side}_matched"
    denominator = int(proof_frame[den].sum())
    return {
        "numerator": int(proof_frame[num].sum()),
        "denominator": denominator,
        "estimate": float(proof_frame[num].sum() / denominator) if denominator else None,
        "source_cluster_ci": cluster_ratio_ci(proof_frame, num, den, rng, boot),
    }


def paired_summary(proofs: pd.DataFrame, metric: str) -> dict[str, Any]:
    subset = proofs.dropna(subset=[f"h_{metric}", f"a_{metric}"])
    h = subset[f"h_{metric}"].to_numpy(float)
    a = subset[f"a_{metric}"].to_numpy(float)
    try:
        p = float(stats.wilcoxon(h, a).pvalue)
    except ValueError:
        p = 1.0
    return {
        "n_pairs": len(subset),
        "human_median": float(np.median(h)) if len(h) else None,
        "ai_median": float(np.median(a)) if len(a) else None,
        "median_paired_difference": float(np.median(a - h)) if len(h) else None,
        "probability_ai_greater": float(np.mean(a > h)) if len(h) else None,
        "wilcoxon_p": p,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--extraction-file", type=Path,
        default=Path("results/horizon/binder_extraction.json"),
    )
    parser.add_argument("--boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument(
        "--output-tag", default="",
        help="suffix analysis outputs so toolchain sensitivities can coexist",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    outdir = root / "results" / "horizon"
    if args.output_tag and not re.fullmatch(r"[A-Za-z0-9_-]+", args.output_tag):
        raise ValueError("--output-tag may contain only letters, digits, underscore, and hyphen")
    suffix = f"_{args.output_tag}" if args.output_tag else ""

    extraction_path = (
        args.extraction_file if args.extraction_file.is_absolute()
        else root / args.extraction_file
    )
    extraction = json.loads(extraction_path.read_text())
    claims = pd.read_csv(outdir / "claims.csv.gz").sort_values(
        ["pair", "side", "claim_index"]
    )
    source_all = pd.read_csv(outdir / "source_pairs.csv.gz")
    source_proofs = source_all[["pair", "source", "h_named_haves", "a_named_haves"]]
    rows: list[dict[str, Any]] = []
    proof_rows: list[dict[str, Any]] = []

    for record in extraction:
        pair, side = record["pair"], record["side"]
        source = source_proofs.loc[source_proofs.pair.eq(pair), "source"]
        source_name = str(source.iloc[0]) if len(source) else "unknown"
        source_claims = claims[(claims.pair == pair) & (claims.side == side)].copy()
        base: dict[str, Any] = {
            "pair": pair,
            "side": side,
            "source": source_name,
            "status": record["status"],
            "source_claims": len(source_claims),
        }
        if record["status"] != "ok":
            proof_rows.append(base)
            continue

        lets = record.get("lets", [])
        source_names = source_claims.name.astype(str).tolist()
        term_names = [str(item["name"]) for item in lets]
        matches = lcs_matches(source_names, term_names)
        source_counts, term_counts = Counter(source_names), Counter(term_names)
        matched_records: list[dict[str, Any]] = []
        for source_i, term_i in matches:
            claim = source_claims.iloc[source_i]
            binder = lets[term_i]
            uses = int(binder["uses"])
            unambiguous = source_counts[source_names[source_i]] == 1 and term_counts[term_names[term_i]] == 1
            row = {
                "pair": pair,
                "side": side,
                "source": source_name,
                "claim_index": int(claim.claim_index),
                "source_claims_in_proof": int(len(source_claims)),
                "name": source_names[source_i],
                "binder_kind": str(binder.get("kind", "unknown")),
                "explicit_uses": int(claim.explicit_uses),
                "term_uses": uses,
                "zero_term_use": int(uses == 0),
                "one_term_use": int(uses == 1),
                "multi_term_use": int(uses > 1),
                "polarized_term_use": int(uses != 1),
                "reuse_excess": max(uses - 1, 0),
                "value_nodes": int(binder["value_nodes"]),
                "potential_inlining_nodes": max(uses - 1, 0) * int(binder["value_nodes"]),
                "placeholder_name": bool(claim.placeholder_name),
                "redeclared_name": bool(claim.redeclared_name),
                "parametric_claim": bool(claim.parametric_claim),
                "universal_claim": bool(claim.universal_claim),
                "generalized_claim": bool(claim.generalized_claim),
                "unambiguous_name": unambiguous,
                "source_position": source_i,
                "term_position": term_i,
            }
            rows.append(row)
            matched_records.append(row)

        base.update(
            {
                "root_nodes": int(record["root_nodes"]),
                "root_node_digits": len(str(record["root_nodes"])),
                "term_lets": len(lets),
                "matched": len(matches),
                "match_share": (
                    len(matches) / len(source_claims) if len(source_claims) else 1.0
                ),
                "unambiguous_matched": sum(row["unambiguous_name"] for row in matched_records),
                "term_uses": sum(row["term_uses"] for row in matched_records),
                "zero_term_use": sum(row["zero_term_use"] for row in matched_records),
                "one_term_use": sum(row["one_term_use"] for row in matched_records),
                "multi_term_use": sum(row["multi_term_use"] for row in matched_records),
                "polarized_term_use": sum(row["polarized_term_use"] for row in matched_records),
                "reuse_excess": sum(row["reuse_excess"] for row in matched_records),
                "potential_inlining_nodes": sum(row["potential_inlining_nodes"] for row in matched_records),
            }
        )
        proof_rows.append(base)

    claim_columns = [
        "pair", "side", "source", "claim_index", "source_claims_in_proof", "name", "binder_kind", "explicit_uses",
        "term_uses", "zero_term_use", "one_term_use", "multi_term_use",
        "polarized_term_use", "reuse_excess", "value_nodes",
        "potential_inlining_nodes", "placeholder_name", "redeclared_name",
        "parametric_claim", "universal_claim", "generalized_claim",
        "unambiguous_name", "source_position", "term_position",
    ]
    binder_claims = pd.DataFrame(rows, columns=claim_columns)
    task_proofs = pd.DataFrame(proof_rows)
    binder_claims.to_csv(
        outdir / f"binder_claims{suffix}.csv.gz", index=False,
        compression={"method": "gzip", "mtime": 0},
    )
    task_proofs.to_csv(outdir / f"binder_tasks{suffix}.csv", index=False)

    wide = task_proofs[task_proofs.status.eq("ok")].pivot(index=["pair", "source"], columns="side")
    wide.columns = [f"{side}_{metric}" for metric, side in wide.columns]
    complete = wide.reset_index().dropna(subset=["h_matched", "a_matched"]).copy()
    complete_pairs = set(complete.pair)
    complete_claims = binder_claims[binder_claims.pair.isin(complete_pairs)].copy()
    by_source_term = (
        complete_claims.groupby(["source", "side"])
        .agg(
            claims=("pair", "size"),
            zero_share=("zero_term_use", "mean"),
            one_share=("one_term_use", "mean"),
            multi_share=("multi_term_use", "mean"),
            mean_uses=("term_uses", "mean"),
        )
        .reset_index()
    )
    by_source_term.to_csv(outdir / f"binder_by_source{suffix}.csv", index=False)
    tactic_strata = tactic_matched_strata(complete_claims, source_all, complete_pairs)
    tactic_strata.to_csv(outdir / f"binder_tactic_matched_strata{suffix}.csv", index=False)
    rng = np.random.default_rng(args.seed)
    rates: dict[str, Any] = {}
    for side, label in (("h", "human"), ("a", "ai")):
        rates[label] = {
            metric: rate_summary(complete, side, metric, rng, args.boot)
            for metric in (
                "term_uses", "zero_term_use", "one_term_use", "multi_term_use",
                "polarized_term_use", "reuse_excess",
            )
        }

    paired = {
        metric: paired_summary(complete, metric)
        for metric in (
            "root_node_digits", "term_lets", "matched", "match_share",
            "zero_term_use", "multi_term_use",
        )
    }
    rate_differences = {
        metric: cluster_ratio_difference(complete, metric, rng, args.boot)
        for metric in ("zero_term_use", "one_term_use", "multi_term_use", "polarized_term_use")
    }

    def source_profile(frame: pd.DataFrame) -> dict[str, Any]:
        profile: dict[str, Any] = {"pairs": len(frame), "source_groups": int(frame.source.nunique())}
        for side, label in (("h", "human"), ("a", "ai")):
            claims_n = max(int(frame[f"{side}_named_haves"].sum()), 1)
            profile[label] = {
                "claims_per_100_tokens": float(
                    100 * frame[f"{side}_named_haves"].sum()
                    / max(frame[f"{side}_tokens"].sum(), 1)
                ),
                "explicit_uses_per_claim": float(
                    frame[f"{side}_explicit_uses"].sum() / claims_n
                ),
                "zero_uptake_share": float(
                    frame[f"{side}_zero_uptake_haves"].sum() / claims_n
                ),
                "placeholder_name_share": float(
                    frame[f"{side}_placeholder_haves"].sum() / claims_n
                ),
            }
        return profile

    selected_pairs = set(task_proofs.pair)
    selected_label = f"materialized_{len(selected_pairs)}"
    complete_label = f"complete_{len(complete)}"
    root_extremes: dict[str, Any] = {}
    successful_tasks = task_proofs[task_proofs.status.eq("ok")]
    extreme_rows: list[pd.DataFrame] = []
    for side, label in (("h", "human"), ("a", "ai")):
        side_tasks = successful_tasks[successful_tasks.side.eq(side)]
        ranked = side_tasks.sort_values(
            ["root_node_digits", "root_nodes"], ascending=False
        ).head(20).copy()
        ranked.insert(0, "rank_within_side", np.arange(1, len(ranked) + 1))
        extreme_rows.append(ranked[[
            "rank_within_side", "pair", "side", "source", "root_nodes",
            "root_node_digits", "source_claims", "term_lets", "matched",
        ]])
        maximum = side_tasks.loc[side_tasks.root_node_digits.idxmax()]
        root_extremes[label] = {
            "max_decimal_digits": int(maximum.root_node_digits),
            "max_tree_nodes": str(maximum.root_nodes),
            "max_pair": str(maximum.pair),
            "tasks_at_least_20_digits": int(side_tasks.root_node_digits.ge(20).sum()),
            "tasks_at_least_100_digits": int(side_tasks.root_node_digits.ge(100).sum()),
        }
    pd.concat(extreme_rows, ignore_index=True).to_csv(
        outdir / f"binder_root_tree_extremes{suffix}.csv", index=False
    )
    summary = {
        "seed": args.seed,
        "bootstraps": args.boot,
        "extraction_file": str(
            extraction_path.relative_to(root) if extraction_path.is_relative_to(root)
            else extraction_path
        ),
        "tasks": len(task_proofs),
        "task_status": task_proofs.status.value_counts().to_dict(),
        "pairs_with_both_sides": len(complete),
        "source_groups_with_both_sides": int(complete.source.nunique()),
        "claims_matched": int(len(binder_claims)),
        "claims_unambiguous": int(binder_claims.unambiguous_name.sum()),
        "root_tree_representation": {
            "measure": (
                "fully expanded syntax-tree occurrence count computed by DAG recurrence; "
                "not a representation-invariant certificate size"
            ),
            **root_extremes,
        },
        "aligned_binder_kinds": {
            label: {
                str(kind): int(count)
                for kind, count in binder_claims.loc[
                    binder_claims.side.eq(side), "binder_kind"
                ].value_counts().items()
            }
            for side, label in (("h", "human"), ("a", "ai"))
        },
        "source_claims_in_successful_tasks": int(
            task_proofs.loc[task_proofs.status.eq("ok"), "source_claims"].sum()
        ),
        "matching_method": "exact-name longest common subsequence in pre-order term traversal",
        "source_sample_comparison": {
            "full_corpus": source_profile(source_all),
            selected_label: source_profile(source_all[source_all.pair.isin(selected_pairs)]),
            complete_label: source_profile(source_all[source_all.pair.isin(complete_pairs)]),
        },
        "paired": paired,
        "source_claim_retention_complete_pairs": {
            "human": {
                "numerator": int(complete.h_matched.sum()),
                "denominator": int(complete.h_source_claims.sum()),
                "estimate": float(
                    complete.h_matched.sum() / max(complete.h_source_claims.sum(), 1)
                ),
                "source_cluster_ci": cluster_ratio_ci(
                    complete, "h_matched", "h_source_claims", rng, args.boot
                ),
            },
            "ai": {
                "numerator": int(complete.a_matched.sum()),
                "denominator": int(complete.a_source_claims.sum()),
                "estimate": float(
                    complete.a_matched.sum() / max(complete.a_source_claims.sum(), 1)
                ),
                "source_cluster_ci": cluster_ratio_ci(
                    complete, "a_matched", "a_source_claims", rng, args.boot
                ),
            },
            "ai_minus_human": retention_difference(complete, rng, args.boot),
        },
        "claim_rates_complete_pairs": rates,
        "multi_term_use_conditional_on_retention": conditional_retained_multi_use(
            complete, np.random.default_rng(args.seed + 20), args.boot
        ),
        "matched_claim_profiles_by_generality": {
            f"{label}_{'generalized' if generalized else 'instance'}": {
                "claims": int(len(group)),
                "zero_term_use_share": float(group.zero_term_use.mean()) if len(group) else None,
                "one_term_use_share": float(group.one_term_use.mean()) if len(group) else None,
                "multi_term_use_share": float(group.multi_term_use.mean()) if len(group) else None,
                "mean_term_uses": float(group.term_uses.mean()) if len(group) else None,
            }
            for side, label in (("h", "human"), ("a", "ai"))
            for generalized in (False, True)
            for group in [complete_claims[
                complete_claims.side.eq(side)
                & complete_claims.generalized_claim.eq(generalized)
            ]]
        },
        "within_proof_generality_term_association": (
            within_proof_generality_term_association(
                complete_claims, np.random.default_rng(args.seed + 17), args.boot
            )
        ),
        "position_matched_generality_term_association": (
            position_matched_generality_term_association(
                complete_claims, np.random.default_rng(args.seed + 18), args.boot
            )
        ),
        "position_matched_generality_term_unambiguous_sensitivity": (
            position_matched_generality_term_association(
                complete_claims[complete_claims.unambiguous_name],
                np.random.default_rng(args.seed + 19),
                args.boot,
            )
        ),
        "claim_rate_differences_complete_pairs": rate_differences,
        "source_to_term_use_transitions": transition_summary(
            complete_claims, rng, args.boot
        ),
        "tactic_matched_polarization": {
            "strata": int(len(tactic_strata)),
            "ai_higher": int(tactic_strata.polarized_ai_minus_human.gt(0).sum()),
            "file": f"results/horizon/binder_tactic_matched_strata{suffix}.csv",
        },
        "unambiguous_claim_sensitivity": {
            label: {
                "claims": int(len(group)),
                "zero_term_use_share": float(group.zero_term_use.mean()) if len(group) else None,
                "one_term_use_share": float(group.one_term_use.mean()) if len(group) else None,
                "multi_term_use_share": float(group.multi_term_use.mean()) if len(group) else None,
                "median_term_uses": float(group.term_uses.median()) if len(group) else None,
                "mean_term_uses": float(group.term_uses.mean()) if len(group) else None,
            }
            for side, label in (("h", "human"), ("a", "ai"))
            for group in [complete_claims[
                complete_claims.side.eq(side) & complete_claims.unambiguous_name
            ]]
        },
        "by_source_file": f"results/horizon/binder_by_source{suffix}.csv",
    }
    (outdir / f"binder_summary{suffix}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
