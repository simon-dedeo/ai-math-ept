"""Compare source-claim retention across two Lean/Mathlib elaboration snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_binder_use import lcs_matches


def pooled_rate(frame: pd.DataFrame, numerator: str, denominator: str) -> float:
    return float(frame[numerator].sum() / max(frame[denominator].sum(), 1))


def cluster_difference(
    frame: pd.DataFrame,
    left_num: str,
    left_den: str,
    right_num: str,
    right_den: str,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    columns = [left_num, left_den, right_num, right_den]
    grouped = frame.groupby("source")[columns].sum().to_numpy(float)
    draws = rng.integers(0, len(grouped), size=(boot, len(grouped)))
    sampled = grouped[draws].sum(axis=1)
    differences = (
        sampled[:, 2] / np.maximum(sampled[:, 3], 1)
        - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
    )
    left = pooled_rate(frame, left_num, left_den)
    right = pooled_rate(frame, right_num, right_den)
    return {
        "left": left,
        "right": right,
        "right_minus_left": right - left,
        "source_cluster_ci": [
            float(x) for x in np.percentile(differences, [2.5, 97.5])
        ],
    }


def cluster_mean_difference(
    frame: pd.DataFrame,
    left: str,
    right: str,
    rng: np.random.Generator,
    boot: int,
) -> dict[str, Any]:
    """Right-minus-left mean, resampling the paired source groups."""
    if frame.empty:
        return {
            "left": None, "right": None, "right_minus_left": None,
            "source_cluster_ci": [None, None],
        }
    grouped = frame.groupby("source")[[left, right]].agg(["sum", "count"])
    values = np.column_stack([
        grouped[(left, "sum")], grouped[(left, "count")],
        grouped[(right, "sum")], grouped[(right, "count")],
    ]).astype(float)
    draws = rng.integers(0, len(values), size=(boot, len(values)))
    sampled = values[draws].sum(axis=1)
    differences = sampled[:, 2] / sampled[:, 3] - sampled[:, 0] / sampled[:, 1]
    left_value, right_value = float(frame[left].mean()), float(frame[right].mean())
    return {
        "left": left_value,
        "right": right_value,
        "right_minus_left": right_value - left_value,
        "source_cluster_ci": [
            float(x) for x in np.percentile(differences, [2.5, 97.5])
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260802)
    args = parser.parse_args()
    root = args.root.resolve()
    outdir = root / "results/horizon"

    def load(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
        resolved = path if path.is_absolute() else root / path
        return {
            (str(row["pair"]), str(row["side"])): row
            for row in json.loads(resolved.read_text())
        }

    native = load(args.native)
    current = load(args.current)
    source_claims = pd.read_csv(outdir / "claims.csv.gz").sort_values(
        ["pair", "side", "claim_index"]
    )
    source_pairs = pd.read_csv(outdir / "source_pairs.csv.gz")
    source_map = source_pairs.set_index("pair").source.to_dict()
    common_ok = {
        key for key in native.keys() & current.keys()
        if native[key]["status"] == "ok" and current[key]["status"] == "ok"
    }
    complete_pairs = {
        pair for pair, _side in common_ok
        if (pair, "h") in common_ok and (pair, "a") in common_ok
    }

    task_rows: list[dict[str, Any]] = []
    claim_rows: list[dict[str, Any]] = []
    for pair in sorted(complete_pairs):
        for side in ("h", "a"):
            selected = source_claims[
                source_claims.pair.eq(pair) & source_claims.side.eq(side)
            ]
            names = selected.name.astype(str).tolist()
            native_lets = native[(pair, side)].get("lets", [])
            current_lets = current[(pair, side)].get("lets", [])
            native_matches = dict(lcs_matches(names, [str(x["name"]) for x in native_lets]))
            current_matches = dict(lcs_matches(names, [str(x["name"]) for x in current_lets]))
            task_rows.append({
                "pair": pair,
                "side": side,
                "source": source_map[pair],
                "source_claims": len(names),
                "native_retained": len(native_matches),
                "current_retained": len(current_matches),
            })
            for source_i, claim in enumerate(selected.itertuples(index=False)):
                native_i = native_matches.get(source_i)
                current_i = current_matches.get(source_i)
                claim_rows.append({
                    "pair": pair,
                    "side": side,
                    "source": source_map[pair],
                    "claim_index": int(claim.claim_index),
                    "name": str(claim.name),
                    "explicit_uses": int(claim.explicit_uses),
                    "native_retained": int(native_i is not None),
                    "current_retained": int(current_i is not None),
                    "native_term_uses": (
                        int(native_lets[native_i]["uses"]) if native_i is not None else None
                    ),
                    "current_term_uses": (
                        int(current_lets[current_i]["uses"]) if current_i is not None else None
                    ),
                })

    tasks = pd.DataFrame(task_rows)
    claims = pd.DataFrame(claim_rows)
    tasks.to_csv(outdir / "binder_toolchain_tasks.csv", index=False)
    claims.to_csv(
        outdir / "binder_toolchain_claims.csv.gz", index=False,
        compression={"method": "gzip", "mtime": 0},
    )
    rng = np.random.default_rng(args.seed)
    summary: dict[str, Any] = {
        "seed": args.seed,
        "bootstraps": args.boot,
        "native_file": str(args.native),
        "current_file": str(args.current),
        "tasks_successful_in_both": len(common_ok),
        "pairs_with_both_sides_successful_in_both": len(complete_pairs),
        "source_groups": int(tasks.source.nunique()) if len(tasks) else 0,
        "retention_by_side": {},
    }
    for side, label in (("h", "human"), ("a", "ai")):
        selected = tasks[tasks.side.eq(side)]
        summary["retention_by_side"][label] = cluster_difference(
            selected,
            "native_retained", "source_claims",
            "current_retained", "source_claims",
            rng, args.boot,
        )

    for tool in ("native", "current"):
        human = tasks[tasks.side.eq("h")]
        ai = tasks[tasks.side.eq("a")]
        h_rate = pooled_rate(human, f"{tool}_retained", "source_claims")
        a_rate = pooled_rate(ai, f"{tool}_retained", "source_claims")
        by_source = []
        for source in sorted(tasks.source.unique()):
            h = human[human.source.eq(source)]
            a = ai[ai.source.eq(source)]
            by_source.append([
                h[f"{tool}_retained"].sum(), h.source_claims.sum(),
                a[f"{tool}_retained"].sum(), a.source_claims.sum(),
            ])
        values = np.asarray(by_source, dtype=float)
        draws = rng.integers(0, len(values), size=(args.boot, len(values)))
        sampled = values[draws].sum(axis=1)
        differences = (
            sampled[:, 2] / np.maximum(sampled[:, 3], 1)
            - sampled[:, 0] / np.maximum(sampled[:, 1], 1)
        )
        summary[f"{tool}_retention_ai_minus_human"] = {
            "human": h_rate,
            "ai": a_rate,
            "ai_minus_human": a_rate - h_rate,
            "source_cluster_ci": [
                float(x) for x in np.percentile(differences, [2.5, 97.5])
            ],
        }

    retained_both = claims[
        claims.native_retained.eq(1) & claims.current_retained.eq(1)
    ].copy()
    retained_both["native_use_class"] = np.select(
        [retained_both.native_term_uses.eq(0), retained_both.native_term_uses.eq(1)],
        ["zero", "one"], default="multi",
    )
    retained_both["current_use_class"] = np.select(
        [retained_both.current_term_uses.eq(0), retained_both.current_term_uses.eq(1)],
        ["zero", "one"], default="multi",
    )
    summary["conditional_use_stability"] = {}
    for side, label in (("h", "human"), ("a", "ai")):
        selected = retained_both[retained_both.side.eq(side)].copy()
        block: dict[str, Any] = {
            "claims_retained_in_both": len(selected),
            "exact_count_agreement": (
                float(selected.native_term_uses.eq(selected.current_term_uses).mean())
                if len(selected) else None
            ),
            "zero_one_multi_agreement": (
                float(selected.native_use_class.eq(selected.current_use_class).mean())
                if len(selected) else None
            ),
            "rates_current_minus_native": {},
        }
        for category in ("zero", "one", "multi"):
            native_column = f"native_{category}"
            current_column = f"current_{category}"
            selected[native_column] = selected.native_use_class.eq(category).astype(int)
            selected[current_column] = selected.current_use_class.eq(category).astype(int)
            block["rates_current_minus_native"][category] = cluster_mean_difference(
                selected, native_column, current_column, rng, args.boot
            )
        summary["conditional_use_stability"][label] = block

    (outdir / "binder_toolchain_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
