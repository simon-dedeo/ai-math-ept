"""Match source ``have`` claims to de-Bruijn-aware elaborated let binders.

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
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


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
) -> list[float]:
    grouped = frame.groupby("source")[[numerator, denominator]].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
    sample = grouped[draws]
    ratios = sample[:, :, 0].sum(axis=1) / np.maximum(sample[:, :, 1].sum(axis=1), 1)
    return [float(x) for x in np.percentile(ratios, [2.5, 97.5])]


def rate_summary(
    proof_frame: pd.DataFrame,
    side: str,
    numerator: str,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    num, den = f"{side}_{numerator}", f"{side}_matched"
    return {
        "numerator": int(proof_frame[num].sum()),
        "denominator": int(proof_frame[den].sum()),
        "estimate": float(proof_frame[num].sum() / max(proof_frame[den].sum(), 1)),
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
    parser.add_argument("--boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260802)
    args = parser.parse_args()
    root = args.root.resolve()
    outdir = root / "results" / "horizon"

    extraction = json.loads((outdir / "binder_extraction.json").read_text())
    claims = pd.read_csv(outdir / "claims.csv.gz").sort_values(
        ["pair", "side", "claim_index"]
    )
    source_proofs = pd.read_csv(outdir / "source_pairs.csv.gz")[
        ["pair", "source", "h_named_haves", "a_named_haves"]
    ]
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
                "name": source_names[source_i],
                "explicit_uses": int(claim.explicit_uses),
                "term_uses": uses,
                "zero_term_use": int(uses == 0),
                "one_term_use": int(uses == 1),
                "multi_term_use": int(uses > 1),
                "reuse_excess": max(uses - 1, 0),
                "value_nodes": int(binder["value_nodes"]),
                "potential_inlining_nodes": max(uses - 1, 0) * int(binder["value_nodes"]),
                "placeholder_name": bool(claim.placeholder_name),
                "redeclared_name": bool(claim.redeclared_name),
                "unambiguous_name": unambiguous,
                "source_position": source_i,
                "term_position": term_i,
            }
            rows.append(row)
            matched_records.append(row)

        base.update(
            {
                "root_nodes": int(record["root_nodes"]),
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
                "reuse_excess": sum(row["reuse_excess"] for row in matched_records),
                "potential_inlining_nodes": sum(row["potential_inlining_nodes"] for row in matched_records),
            }
        )
        proof_rows.append(base)

    binder_claims = pd.DataFrame(rows)
    task_proofs = pd.DataFrame(proof_rows)
    binder_claims.to_csv(outdir / "binder_claims.csv.gz", index=False, compression="gzip")
    task_proofs.to_csv(outdir / "binder_tasks.csv", index=False)

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
    by_source_term.to_csv(outdir / "binder_by_source.csv", index=False)
    rng = np.random.default_rng(args.seed)
    rates: dict[str, Any] = {}
    for side, label in (("h", "human"), ("a", "ai")):
        rates[label] = {
            metric: rate_summary(complete, side, metric, rng, args.boot)
            for metric in ("term_uses", "zero_term_use", "one_term_use", "multi_term_use", "reuse_excess")
        }

    paired = {
        metric: paired_summary(complete, metric)
        for metric in ("matched", "match_share", "term_uses", "zero_term_use", "multi_term_use", "reuse_excess")
    }
    summary = {
        "seed": args.seed,
        "bootstraps": args.boot,
        "tasks": len(task_proofs),
        "task_status": task_proofs.status.value_counts().to_dict(),
        "pairs_with_both_sides": len(complete),
        "source_groups_with_both_sides": int(complete.source.nunique()),
        "claims_matched": int(len(binder_claims)),
        "claims_unambiguous": int(binder_claims.unambiguous_name.sum()),
        "source_claims_in_successful_tasks": int(
            task_proofs.loc[task_proofs.status.eq("ok"), "source_claims"].sum()
        ),
        "matching_method": "exact-name longest common subsequence in pre-order term traversal",
        "paired": paired,
        "claim_rates_complete_pairs": rates,
        "unambiguous_claim_sensitivity": {
            label: {
                "claims": int(len(group)),
                "zero_term_use_share": float(group.zero_term_use.mean()),
                "one_term_use_share": float(group.one_term_use.mean()),
                "multi_term_use_share": float(group.multi_term_use.mean()),
                "median_term_uses": float(group.term_uses.median()),
                "mean_term_uses": float(group.term_uses.mean()),
            }
            for side, label in (("h", "human"), ("a", "ai"))
            for group in [complete_claims[
                complete_claims.side.eq(side) & complete_claims.unambiguous_name
            ]]
        },
        "by_source_file": "results/horizon/binder_by_source.csv",
    }
    (outdir / "binder_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
