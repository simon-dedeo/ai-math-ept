"""Construct and score a diverse equivalence audit for binder extractors."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(json.loads(path.read_text()))
    return rows


HYGIENE_WORKDIR = re.compile(r"eptx_binder_work_[^.]+(?=\.pair_)")


def canonical_record(row: dict[str, Any]) -> dict[str, Any]:
    """Remove the expected work-directory component of generated hygienic names."""
    normalized = json.loads(json.dumps(row))
    for binder in normalized.get("lets", []):
        binder["name"] = HYGIENE_WORKDIR.sub(
            "eptx_binder_work_CANONICAL", str(binder.get("name", ""))
        )
    return normalized


def prepare(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    baselines = [root / path for path in args.baseline]
    rows = load_rows(baselines)
    by_pair: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_pair.setdefault(str(row["pair"]), []).append(row)
    complete = {
        pair: records for pair, records in by_pair.items()
        if len(records) == 2 and all(record["status"] == "ok" for record in records)
    }
    source_pairs = pd.read_csv(root / "results/horizon/source_pairs.csv.gz")
    pair_source = dict(zip(source_pairs.pair.astype(str), source_pairs.source.astype(str)))
    labels: dict[str, set[str]] = {}

    def add(pair: str, label: str) -> None:
        labels.setdefault(pair, set()).add(label)

    for pair in sorted(complete)[: args.first]:
        add(pair, "lexicographic")
    largest = sorted(
        complete,
        key=lambda pair: max(int(row["root_nodes"]) for row in complete[pair]),
        reverse=True,
    )[: args.largest]
    for pair in largest:
        add(pair, "largest_root")

    rng = np.random.default_rng(args.seed)
    sources = sorted({pair_source[pair] for pair in complete if pair in pair_source})
    for source in sources:
        candidates = sorted(
            pair for pair in complete if pair_source.get(pair) == source
        )
        count = min(args.per_source, len(candidates))
        for index in sorted(rng.choice(len(candidates), size=count, replace=False)):
            add(candidates[int(index)], f"source:{source}")

    selected = sorted(labels)
    output = root / args.output
    pd.DataFrame({
        "pair": selected,
        "selection_strata": ["|".join(sorted(labels[pair])) for pair in selected],
    }).to_csv(output, index=False)
    baseline_output = root / args.baseline_output
    selected_rows = [row for row in rows if str(row["pair"]) in set(selected)]
    baseline_output.write_text(json.dumps(selected_rows, indent=2))
    print(json.dumps({
        "output": str(output.relative_to(root)),
        "baseline_output": str(baseline_output.relative_to(root)),
        "pairs": len(selected),
        "tasks": 2 * len(selected),
        "source_groups": len({pair_source[pair] for pair in selected}),
        "largest_sampled_root_nodes": max(
            int(row["root_nodes"]) for pair in selected for row in complete[pair]
        ),
    }, indent=2))


def compare(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    baselines = [root / path for path in args.baseline]
    candidate_path = root / args.candidate
    output_path = root / args.output
    baseline_rows = load_rows(baselines)
    baseline = {
        (str(row["pair"]), str(row["side"])): row for row in baseline_rows
    }
    candidate_rows = json.loads(candidate_path.read_text())
    candidate = {
        (str(row["pair"]), str(row["side"])): row for row in candidate_rows
    }
    if args.all_baseline_ok:
        expected = {
            key for key, row in baseline.items() if row.get("status") == "ok"
        }
        selected = {pair for pair, _ in expected}
        manifest_path = None
    else:
        manifest_path = root / args.manifest
        selected = set(pd.read_csv(manifest_path).pair.astype(str))
        expected = {(pair, side) for pair in selected for side in ("h", "a")}
    if not args.all_baseline_ok and set(candidate) != expected:
        raise ValueError(
            f"candidate keys differ: missing={len(expected-set(candidate))}, "
            f"extra={len(set(candidate)-expected)}"
        )
    if args.all_baseline_ok and not expected <= set(candidate):
        raise ValueError(
            f"candidate omits {len(expected-set(candidate))} legacy-success tasks"
        )
    missing_baseline = expected - set(baseline)
    if missing_baseline:
        raise ValueError(f"baseline missing {sorted(missing_baseline)[:10]}")
    raw_mismatches = []
    mismatches = []
    for key in sorted(expected):
        if candidate[key] != baseline[key]:
            raw_mismatches.append({
                "pair": key[0], "side": key[1],
                "differing_fields": sorted(
                    field for field in set(candidate[key]) | set(baseline[key])
                    if candidate[key].get(field) != baseline[key].get(field)
                ),
            })
        if canonical_record(candidate[key]) != canonical_record(baseline[key]):
            mismatches.append({
                "pair": key[0], "side": key[1],
                "differing_fields": sorted(
                    field for field in set(candidate[key]) | set(baseline[key])
                    if canonical_record(candidate[key]).get(field)
                    != canonical_record(baseline[key]).get(field)
                ),
            })
    source_pairs = pd.read_csv(root / "results/horizon/source_pairs.csv.gz")
    sources = set(source_pairs.loc[source_pairs.pair.isin(selected), "source"])
    root_nodes = [int(baseline[key]["root_nodes"]) for key in expected]
    provenance_path = candidate_path.with_name(
        candidate_path.stem.replace(
            "binder_extraction", "binder_extraction_provenance"
        ) + candidate_path.suffix
    )
    if args.all_baseline_ok:
        selection = (
            "all tasks successfully completed by the recursive legacy extractor; "
            "the candidate may additionally recover legacy timeouts"
        )
    else:
        selection = (
            "union of first 50 lexicographic complete pairs, 50 largest-root complete pairs, "
            "and 10 seeded random complete pairs per source group"
        )
    summary = {
        "seed": args.seed,
        "selection": selection,
        "pairs_represented": len(selected),
        "tasks": len(expected),
        "source_groups": len(sources),
        "candidate_ok": sum(row.get("status") == "ok" for row in candidate_rows),
        "raw_exact_record_matches": len(expected) - len(raw_mismatches),
        "raw_mismatches": raw_mismatches,
        "canonicalization": (
            "replace only the work-tag component of Lean-generated hygienic binder names"
        ),
        "canonical_exact_record_matches": len(expected) - len(mismatches),
        "canonical_mismatches": mismatches,
        "max_baseline_root_nodes": max(root_nodes),
        "median_baseline_root_nodes": float(np.median(root_nodes)),
        "manifest": (
            str(manifest_path.relative_to(root)) if manifest_path is not None else None
        ),
        "manifest_sha256": sha256(manifest_path) if manifest_path is not None else None,
        "candidate": str(candidate_path.relative_to(root)),
        "candidate_sha256": sha256(candidate_path),
        "candidate_provenance_sha256": sha256(provenance_path),
        "baseline_components": [
            {"file": str(path.relative_to(root)), "sha256": sha256(path)}
            for path in baselines
        ],
    }
    output_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    if mismatches:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "compare"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--baseline", type=Path, nargs="+", default=[
            Path(f"tmp/horizon/binder_extraction_mathlib415semantic3_shard{s}_legacy.json")
            for s in range(3)
        ],
    )
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--first", type=int, default=50)
    parser.add_argument("--largest", type=int, default=50)
    parser.add_argument("--per-source", type=int, default=10)
    parser.add_argument(
        "--output", type=Path,
        default=Path("results/horizon/binder_memo_audit_pairs.csv"),
    )
    parser.add_argument(
        "--baseline-output", type=Path,
        default=Path("results/horizon/binder_extraction_mathlib415legacy_audit.json"),
    )
    parser.add_argument(
        "--manifest", type=Path,
        default=Path("results/horizon/binder_memo_audit_pairs.csv"),
    )
    parser.add_argument("--candidate", type=Path)
    parser.add_argument(
        "--all-baseline-ok", action="store_true",
        help="compare every successful legacy task against a full candidate extraction",
    )
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    else:
        if args.candidate is None:
            parser.error("compare requires --candidate")
        if args.output == Path("results/horizon/binder_memo_audit_pairs.csv"):
            args.output = Path("results/horizon/binder_memo_equivalence.json")
        compare(args)


if __name__ == "__main__":
    main()
