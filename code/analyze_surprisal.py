"""Analyze information flow around local-claim boundaries in Lean proofs."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from paired_horizon import HAVE, TOKEN


def overlap_mean(tokens: pd.DataFrame, start: int, end: int) -> float:
    selected = tokens[(tokens.byte_end > start) & (tokens.byte_start < end)]
    return float(selected.nll_nats.mean()) if len(selected) else math.nan


def paired_summary(frame: pd.DataFrame, metric: str) -> dict[str, Any]:
    wide = frame.pivot(index=["pair", "source"], columns="side", values=metric).dropna()
    h, a = wide["h"].to_numpy(float), wide["a"].to_numpy(float)
    try:
        pvalue = float(stats.wilcoxon(h, a).pvalue)
    except ValueError:
        pvalue = 1.0
    return {
        "n_pairs": len(wide),
        "human_median": float(np.median(h)),
        "ai_median": float(np.median(a)),
        "median_paired_difference": float(np.median(a - h)),
        "probability_ai_greater": float(np.mean(a > h)),
        "wilcoxon_p": pvalue,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--window", type=int, default=8)
    parser.add_argument("--tag", default="")
    parser.add_argument("--token-file", type=Path, default=Path("results/horizon/token_surprisal.tsv"))
    parser.add_argument("--model-label", default="Goedel-LM/Goedel-Prover-V2-8B, Q4_K_M quantization")
    parser.add_argument(
        "--caveat",
        default=(
            "Exploratory model-relative information, not human cognitive surprisal; "
            "training-set overlap and theorem-prover style affinity are not excluded."
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    outdir = root / "results" / "horizon"
    docs_dir = root / "tmp" / "horizon" / "surprisal_docs"

    token_path = args.token_file if args.token_file.is_absolute() else root / args.token_file
    token_data = pd.read_csv(token_path, sep="\t")
    sources = pd.read_csv(outdir / "source_pairs.csv.gz")[["pair", "source"]]
    source_map = sources.set_index("pair").source.to_dict()
    source_claims = pd.read_csv(outdir / "claims.csv.gz")
    term_path = outdir / "binder_claims.csv.gz"
    term_claims = pd.read_csv(term_path) if term_path.exists() else pd.DataFrame()

    proof_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    for document, token_frame in token_data.groupby("document", sort=True):
        pair, side = document[:-2], document[-1]
        text = (docs_dir / f"{document}.lean").read_text(encoding="utf-8")
        token_frame = token_frame.sort_values("token_index").reset_index(drop=True)
        matches = list(HAVE.finditer(text))
        boundary_rows: list[dict[str, Any]] = []
        boundary_indices: list[int] = []
        for match in matches:
            candidates = token_frame.index[token_frame.byte_end > match.start()].tolist()
            if not candidates:
                continue
            boundary_indices.append(candidates[0])

        eligible = np.arange(args.window, max(args.window, len(token_frame) - args.window))
        forbidden = {
            index for boundary in boundary_indices
            for index in range(max(0, boundary - args.window), min(len(token_frame), boundary + args.window + 1))
        }
        controls = np.asarray([index for index in eligible if index not in forbidden], dtype=int)
        control_deltas = [
            float(token_frame.iloc[index : index + args.window].nll_nats.mean())
            - float(token_frame.iloc[index - args.window : index].nll_nats.mean())
            for index in controls
        ]
        document_control_delta = float(np.mean(control_deltas)) if control_deltas else math.nan

        for claim_index, (match, boundary) in enumerate(zip(matches, boundary_indices)):
            if boundary < args.window or boundary + args.window > len(token_frame):
                continue
            pre = float(token_frame.iloc[boundary - args.window : boundary].nll_nats.mean())
            post = float(token_frame.iloc[boundary : boundary + args.window].nll_nats.mean())
            after_name_candidates = token_frame.index[token_frame.byte_end > match.end()].tolist()
            after_name = after_name_candidates[0] if after_name_candidates else boundary
            content_post = float(
                token_frame.iloc[after_name : after_name + args.window].nll_nats.mean()
            )
            control_delta = document_control_delta

            name = match.group(1)
            name_start, name_end = match.span(1)
            definition_nll = overlap_mean(token_frame, name_start, name_end)
            next_same = next(
                (later.start() for later in matches[claim_index + 1 :] if later.group(1) == name),
                len(text),
            )
            references = [
                token for token in TOKEN.finditer(text, match.end(), next_same)
                if token.group(0) == name
            ]
            reference_nlls = [overlap_mean(token_frame, ref.start(), ref.end()) for ref in references]
            row = {
                "pair": pair,
                "source": source_map.get(pair, "unknown"),
                "side": side,
                "claim_index": claim_index,
                "name": name,
                "boundary_token_index": int(token_frame.iloc[boundary].token_index),
                "pre_nll": pre,
                "post_nll": post,
                "boundary_delta_nll": post - pre,
                "content_boundary_delta_nll": content_post - pre,
                "content_boundary_excess_nll": content_post - pre - control_delta,
                "control_delta_nll": control_delta,
                "boundary_excess_nll": post - pre - control_delta,
                "definition_name_nll": definition_nll,
                "mean_reference_name_nll": (
                    float(np.nanmean(reference_nlls)) if reference_nlls else math.nan
                ),
                "name_reuse_relief_nll": (
                    definition_nll - float(np.nanmean(reference_nlls))
                    if reference_nlls else math.nan
                ),
            }
            metadata = source_claims[
                source_claims.pair.eq(pair)
                & source_claims.side.eq(side)
                & source_claims.claim_index.eq(claim_index)
            ]
            if len(metadata):
                for key in (
                    "explicit_uses", "placeholder_name", "redeclared_name",
                    "intervening_claims_to_last_use",
                ):
                    row[key] = metadata.iloc[0][key]
            term = term_claims[
                term_claims.pair.eq(pair)
                & term_claims.side.eq(side)
                & term_claims.claim_index.eq(claim_index)
            ] if len(term_claims) else pd.DataFrame()
            if len(term):
                row["term_uses"] = int(term.iloc[0].term_uses)
            claim_rows.append(row)
            boundary_rows.append(row)

        proof_rows.append(
            {
                "pair": pair,
                "source": source_map.get(pair, "unknown"),
                "side": side,
                "tokens_scored": len(token_frame),
                "mean_nll": float(token_frame.nll_nats.mean()),
                "median_nll": float(token_frame.nll_nats.median()),
                "p95_nll": float(token_frame.nll_nats.quantile(0.95)),
                "claim_boundaries": len(boundary_rows),
                "mean_boundary_delta_nll": (
                    float(np.mean([row["boundary_delta_nll"] for row in boundary_rows]))
                    if boundary_rows else math.nan
                ),
                "mean_boundary_excess_nll": (
                    float(np.mean([row["boundary_excess_nll"] for row in boundary_rows]))
                    if boundary_rows else math.nan
                ),
                "mean_content_boundary_delta_nll": (
                    float(np.mean([row["content_boundary_delta_nll"] for row in boundary_rows]))
                    if boundary_rows else math.nan
                ),
                "mean_content_boundary_excess_nll": (
                    float(np.mean([row["content_boundary_excess_nll"] for row in boundary_rows]))
                    if boundary_rows else math.nan
                ),
            }
        )

    proofs = pd.DataFrame(proof_rows)
    claims = pd.DataFrame(claim_rows)
    suffix = f"_{args.tag}" if args.tag else ""
    proofs.to_csv(outdir / f"surprisal_proofs{suffix}.csv", index=False)
    claims.to_csv(
        outdir / f"surprisal_claims{suffix}.csv.gz", index=False,
        compression={"method": "gzip", "mtime": 0},
    )
    summary = {
        "model": args.model_label,
        "window_tokens": args.window,
        "documents": len(proofs),
        "pairs": int(proofs.groupby("pair").side.nunique().eq(2).sum()),
        "claims": len(claims),
        "paired": {
            metric: paired_summary(proofs.dropna(subset=[metric]), metric)
            for metric in (
                "mean_nll", "p95_nll", "mean_boundary_delta_nll",
                "mean_boundary_excess_nll", "mean_content_boundary_delta_nll",
                "mean_content_boundary_excess_nll",
            )
        },
        "claim_level": {
            label: {
                "claims": int(len(group)),
                "median_boundary_delta_nll": float(group.boundary_delta_nll.median()),
                "median_boundary_excess_nll": float(group.boundary_excess_nll.median()),
                "median_definition_name_nll": float(group.definition_name_nll.median()),
                "median_reference_name_nll": float(group.mean_reference_name_nll.median()),
                "median_name_reuse_relief_nll": float(group.name_reuse_relief_nll.median()),
            }
            for side, label in (("h", "human"), ("a", "ai"))
            for group in [claims[claims.side.eq(side)]]
        },
        "caveat": args.caveat,
    }
    (outdir / f"surprisal_summary{suffix}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
