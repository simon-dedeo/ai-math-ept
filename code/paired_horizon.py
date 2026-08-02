"""Same-theorem tests of the proof-construction horizon.

This analysis uses every NuminaMath-LEAN artifact for which both the human
annotation and the prover output are marked valid.  Unlike the earlier source
analysis, it does not require a regex-detected library premise, so the inclusion
rule is independent of the outcome metrics.

The primary source-level object is a named ``have`` claim.  For each claim we
count later *explicit* references to its name, stopping before a later claim
that shadows the same name.  This is intentionally not called semantic use:
context-sensitive tactics can consume a hypothesis without naming it.  A
separate elaborated-term analysis is needed for that stronger claim.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from census import proof_bodies, strip_noncode  # noqa: E402


LEAN_IDENT = r"(?:«[^»\n]+»|[^\W\d][\w']*|_[\w']+)"
HAVE = re.compile(rf"\bhave\s+({LEAN_IDENT})\s*(?::|:=)", re.UNICODE)
ANON_HAVE = re.compile(r"\bhave\s*(?=:)")
TOKEN = re.compile(LEAN_IDENT, re.UNICODE)
TACTIC_HEAD = re.compile(r"(?:[·.\-+]\s*)?([A-Za-z_][A-Za-z0-9_?']*)")
PLACEHOLDER_NAME = re.compile(
    r"(?:h|h[a-z]?|this|step|eq|ineq|hx|hy|hz|ha|hb|hc|aux|claim)\d*", re.I
)


def proof_body(source: str) -> str:
    """Return the final theorem body's comment/string-free source.

    Numina artifacts may include helper declarations before the target theorem.
    Restricting to the final declaration keeps the paired comparison at the
    same target rather than silently pooling artifact-level helper libraries.
    """
    clean = strip_noncode(source if isinstance(source, str) else "")
    bodies = list(proof_bodies(clean, strip=False))
    return bodies[-1][2] if bodies else clean


def named_have_claims(source: str) -> list[dict[str, Any]]:
    """Extract named haves and count later explicit uptake.

    If a name is declared again, the first claim's counting window ends at the
    second declaration.  This conservative rule prevents obvious shadowing from
    being mistaken for reuse.  Lean scoping is richer than this lexical rule;
    ``redeclared_name`` is retained for sensitivity audits.
    """
    body = proof_body(source)
    matches = list(HAVE.finditer(body))
    next_same: dict[int, int] = {}
    next_by_name: dict[str, int] = {}
    for i in range(len(matches) - 1, -1, -1):
        name = matches[i].group(1)
        next_same[i] = next_by_name.get(name, len(body))
        next_by_name[name] = matches[i].start()

    claims: list[dict[str, Any]] = []
    counts = Counter(match.group(1) for match in matches)
    for i, match in enumerate(matches):
        name = match.group(1)
        token_matches = [
            token for token in TOKEN.finditer(body, match.end(), next_same[i])
            if token.group(0) == name
        ]
        use_positions = [token.start() for token in token_matches]
        first_delay = (
            len(TOKEN.findall(body[match.end() : use_positions[0]]))
            if use_positions else None
        )
        last_delay = (
            len(TOKEN.findall(body[match.end() : use_positions[-1]]))
            if use_positions else None
        )
        claim_span = (
            sum(match.start() < later.start() < use_positions[-1] for later in matches)
            if use_positions else None
        )
        claims.append(
            {
                "claim_index": i,
                "name": name,
                "explicit_uses": len(use_positions),
                "first_use_delay_tokens": first_delay,
                "last_use_delay_tokens": last_delay,
                "intervening_claims_to_last_use": claim_span,
                "redeclared_name": counts[name] > 1,
                "placeholder_name": bool(
                    PLACEHOLDER_NAME.fullmatch(unicodedata.normalize("NFKC", name))
                ),
            }
        )
    return claims


def tactic_annotation_metrics(value: Any) -> dict[str, Any]:
    """Summarize the dataset's elaborator-generated tactic annotations.

    Nested tactic annotations overlap, so event and reference totals are only
    descriptive.  The union of ``used_constants`` is invariant to duplicate
    nesting and is the primary annotation-based interface measure.
    """
    if not isinstance(value, (list, np.ndarray)):
        return {
            "tactic_events": 0,
            "tactic_types": 0,
            "used_constants": 0,
            "constant_annotations": 0,
        }
    heads: list[str] = []
    constants: list[str] = []
    for event in value:
        if not isinstance(event, dict):
            continue
        match = TACTIC_HEAD.match(str(event.get("tactic", "")).strip())
        if match:
            heads.append(match.group(1))
        used = event.get("used_constants", [])
        if isinstance(used, (list, np.ndarray)):
            constants.extend(str(item) for item in used)
    out: dict[str, Any] = {
        "tactic_events": len(value),
        "tactic_types": len(set(heads)),
        "used_constants": len(set(constants)),
        "constant_annotations": len(constants),
    }
    for head in (
        "aesop", "apply", "constructor", "exact", "linarith", "nlinarith",
        "norm_num", "omega", "ring", "ring_nf", "rw", "simp", "simpa",
    ):
        out[f"event_{head}"] = heads.count(head)
    return out


def side_metrics(source: str, tactics: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    body = proof_body(source)
    claims = named_have_claims(source)
    uses = np.asarray([claim["explicit_uses"] for claim in claims], dtype=int)
    spans = np.asarray([
        claim["intervening_claims_to_last_use"]
        for claim in claims if claim["intervening_claims_to_last_use"] is not None
    ], dtype=int)
    metrics: dict[str, Any] = {
        "tokens": len(re.findall(r"\S+", body)),
        "chars": len(body),
        "named_haves": len(claims),
        "anonymous_haves": len(ANON_HAVE.findall(body)),
        "explicit_uses": int(uses.sum()) if len(uses) else 0,
        "zero_uptake_haves": int((uses == 0).sum()) if len(uses) else 0,
        "one_uptake_haves": int((uses == 1).sum()) if len(uses) else 0,
        "multi_uptake_haves": int((uses > 1).sum()) if len(uses) else 0,
        "reuse_excess": int(np.maximum(uses - 1, 0).sum()) if len(uses) else 0,
        "long_horizon_haves": int((spans > 0).sum()) if len(spans) else 0,
        "total_claim_span": int(spans.sum()) if len(spans) else 0,
        "max_claim_span": int(spans.max()) if len(spans) else 0,
        "placeholder_haves": sum(claim["placeholder_name"] for claim in claims),
        "redeclared_haves": sum(claim["redeclared_name"] for claim in claims),
    }
    metrics.update(tactic_annotation_metrics(tactics))
    return metrics, claims


def _cluster_ratio_bootstrap(
    frame: pd.DataFrame,
    numerator: str,
    denominator: str,
    n_boot: int,
    rng: np.random.Generator,
) -> list[float]:
    grouped = frame.groupby("source")[[numerator, denominator]].sum()
    values = grouped.to_numpy(float)
    draws = rng.integers(0, len(values), size=(n_boot, len(values)))
    selected = values[draws]
    num = selected[:, :, 0].sum(axis=1)
    den = selected[:, :, 1].sum(axis=1)
    return [float(x) for x in num / np.maximum(den, 1.0)]


def _cluster_median_bootstrap(
    frame: pd.DataFrame,
    values: np.ndarray,
    n_boot: int,
    rng: np.random.Generator,
) -> list[float]:
    grouped = [values[index] for index in frame.groupby("source").indices.values()]
    draws: list[float] = []
    for _ in range(n_boot):
        selected = rng.integers(0, len(grouped), len(grouped))
        draws.append(float(np.median(np.concatenate([grouped[i] for i in selected]))))
    return draws


def _ci(values: Iterable[float]) -> list[float]:
    return [float(x) for x in np.percentile(list(values), [2.5, 97.5])]


def paired_metric(
    frame: pd.DataFrame,
    metric: str,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    human = frame[f"h_{metric}"].to_numpy(float)
    ai = frame[f"a_{metric}"].to_numpy(float)
    difference = ai - human
    try:
        pvalue = float(stats.wilcoxon(human, ai).pvalue)
    except ValueError:
        pvalue = 1.0
    return {
        "n": len(frame),
        "human_median": float(np.median(human)),
        "ai_median": float(np.median(ai)),
        "median_paired_difference": float(np.median(difference)),
        "probability_ai_greater": float(np.mean(difference > 0)),
        "cluster_ci": _ci(_cluster_median_bootstrap(frame, difference, n_boot, rng)),
        "wilcoxon_p": pvalue,
    }


def claim_rate(
    frame: pd.DataFrame,
    side: str,
    numerator: str,
    n_boot: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    num = f"{side}_{numerator}"
    den = f"{side}_named_haves"
    estimate = float(frame[num].sum() / max(frame[den].sum(), 1))
    return {
        "numerator": int(frame[num].sum()),
        "denominator": int(frame[den].sum()),
        "estimate": estimate,
        "source_cluster_ci": _ci(_cluster_ratio_bootstrap(frame, num, den, n_boot, rng)),
    }


def name_lexicon(frame: pd.DataFrame, side: str) -> dict[str, Any]:
    """Descriptive diversity of source-level claim names.

    Entropy is computed on pooled name tokens and is therefore a corpus
    descriptor, not an independent-observation significance test.
    """
    names = [unicodedata.normalize("NFKC", str(x))
             for x in frame.loc[frame.side.eq(side), "name"]]
    counts = Counter(names)
    total = max(sum(counts.values()), 1)
    probabilities = np.asarray(list(counts.values()), dtype=float) / total
    entropy_bits = float(-(probabilities * np.log2(probabilities)).sum())
    return {
        "tokens": len(names),
        "types": len(counts),
        "shannon_entropy_bits": entropy_bits,
        "effective_vocabulary": float(2 ** entropy_bits),
        "mean_name_length": float(np.mean([len(x) for x in names])) if names else 0.0,
        "share_length_at_least_4": float(np.mean([len(x) >= 4 for x in names])) if names else 0.0,
        "share_with_underscore": float(np.mean(["_" in x for x in names])) if names else 0.0,
    }


def load_pairs(root: Path) -> pd.DataFrame:
    paths = sorted(glob.glob(str(
        root / "census" / "numinamath-proof-artifacts" / "data" / "lite" / "shards" / "*.parquet"
    )))
    if not paths:
        raise FileNotFoundError("NuminaMath proof-artifact shards are not available")
    columns = [
        "uuid", "source", "human_formal_proof", "prover_formal_proof",
        "human_validation_status", "prover_validation_status",
        "human_proof_available", "prover_proof_available",
        "human_ground_truth_type", "human_sorries", "prover_sorries",
        "human_all_tactics", "prover_all_tactics",
    ]
    frame = pd.concat(
        [pd.read_parquet(path, columns=columns) for path in paths],
        ignore_index=True,
    )
    frame = frame[
        frame.human_proof_available
        & frame.prover_proof_available
        & frame.human_validation_status.eq("valid")
        & frame.prover_validation_status.eq("valid")
        & frame.human_ground_truth_type.eq("complete")
    ].drop_duplicates("uuid")
    return frame.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260802)
    args = parser.parse_args()

    root = args.root.resolve()
    outdir = root / "results" / "horizon"
    outdir.mkdir(parents=True, exist_ok=True)
    raw = load_pairs(root)

    proof_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    for record in raw.itertuples(index=False):
        row: dict[str, Any] = {
            "pair": "pair_" + str(record.uuid)[:8],
            "uuid": record.uuid,
            "source": str(record.source),
        }
        for side, source, tactics in (
            ("h", record.human_formal_proof, record.human_all_tactics),
            ("a", record.prover_formal_proof, record.prover_all_tactics),
        ):
            metrics, claims = side_metrics(source, tactics)
            row.update({f"{side}_{key}": value for key, value in metrics.items()})
            for claim in claims:
                claim_rows.append(
                    {
                        "pair": row["pair"], "source": row["source"], "side": side,
                        **claim,
                    }
                )
        proof_rows.append(row)

    proofs = pd.DataFrame(proof_rows).sort_values("pair")
    claims = pd.DataFrame(claim_rows).sort_values(["pair", "side", "claim_index"])
    gzip = {"method": "gzip", "mtime": 0}
    proofs.to_csv(outdir / "source_pairs.csv.gz", index=False, compression=gzip)
    claims.to_csv(outdir / "claims.csv.gz", index=False, compression=gzip)

    rng = np.random.default_rng(args.seed)
    metrics = [
        "tokens", "named_haves", "explicit_uses", "zero_uptake_haves",
        "one_uptake_haves", "multi_uptake_haves", "reuse_excess",
        "long_horizon_haves", "total_claim_span", "max_claim_span",
        "placeholder_haves", "tactic_events", "tactic_types", "used_constants",
    ]
    summary: dict[str, Any] = {
        "seed": args.seed,
        "bootstraps": args.boot,
        "inclusion_rule": (
            "both proofs available; both validation statuses valid; human ground truth complete; "
            "no outcome-dependent premise filter"
        ),
        "pairs": len(proofs),
        "source_groups": int(proofs.source.nunique()),
        "paired": {metric: paired_metric(proofs, metric, args.boot, rng) for metric in metrics},
        "claim_rates": {},
        "name_lexicon": {
            "human": name_lexicon(claims, "h"),
            "ai": name_lexicon(claims, "a"),
        },
    }
    for side, label in (("h", "human"), ("a", "ai")):
        summary["claim_rates"][label] = {
            "explicit_uses_per_claim": claim_rate(
                proofs, side, "explicit_uses", args.boot, rng),
            "zero_uptake_share": claim_rate(
                proofs, side, "zero_uptake_haves", args.boot, rng),
            "one_uptake_share": claim_rate(
                proofs, side, "one_uptake_haves", args.boot, rng),
            "multi_uptake_share": claim_rate(
                proofs, side, "multi_uptake_haves", args.boot, rng),
            "long_horizon_share": claim_rate(
                proofs, side, "long_horizon_haves", args.boot, rng),
            "placeholder_name_share": claim_rate(
                proofs, side, "placeholder_haves", args.boot, rng),
        }

    by_source: list[dict[str, Any]] = []
    for source, group in proofs.groupby("source"):
        row = {"source": source, "n_pairs": len(group)}
        for metric in ("named_haves", "used_constants", "tokens"):
            row[f"delta_{metric}"] = float(
                np.median(group[f"a_{metric}"] - group[f"h_{metric}"])
            )
        for side, label in (("h", "human"), ("a", "ai")):
            row[f"{label}_explicit_uses_per_claim"] = float(
                group[f"{side}_explicit_uses"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
            row[f"{label}_zero_uptake_share"] = float(
                group[f"{side}_zero_uptake_haves"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
            row[f"{label}_long_horizon_share"] = float(
                group[f"{side}_long_horizon_haves"].sum()
                / max(group[f"{side}_named_haves"].sum(), 1)
            )
        by_source.append(row)
    pd.DataFrame(by_source).sort_values("source").to_csv(outdir / "by_source.csv", index=False)
    summary["by_source_file"] = "results/horizon/by_source.csv"

    # A coarse tactic-family sensitivity: within pairs where both sides invoke
    # a tactic at least once, and within pairs where neither side does.
    tactic_strata: list[dict[str, Any]] = []
    for tactic in ("linarith", "nlinarith", "norm_num", "omega", "ring", "simp"):
        human_uses = proofs[f"h_event_{tactic}"].gt(0)
        ai_uses = proofs[f"a_event_{tactic}"].gt(0)
        for stratum, mask in (("both_use", human_uses & ai_uses),
                              ("neither_uses", ~human_uses & ~ai_uses)):
            group = proofs[mask]
            if group.empty:
                continue
            row = {"tactic": tactic, "stratum": stratum, "n_pairs": len(group)}
            for side, label in (("h", "human"), ("a", "ai")):
                denominator = max(group[f"{side}_named_haves"].sum(), 1)
                row[f"{label}_explicit_uses_per_claim"] = float(
                    group[f"{side}_explicit_uses"].sum() / denominator
                )
                row[f"{label}_zero_uptake_share"] = float(
                    group[f"{side}_zero_uptake_haves"].sum() / denominator
                )
            tactic_strata.append(row)
    pd.DataFrame(tactic_strata).to_csv(outdir / "tactic_matched_strata.csv", index=False)
    summary["tactic_sensitivity_file"] = "results/horizon/tactic_matched_strata.csv"

    with (outdir / "source_summary.json").open("w") as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
