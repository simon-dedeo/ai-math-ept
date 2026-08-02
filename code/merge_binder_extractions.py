"""Merge independently extracted binder-use shards with strict provenance checks."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output", type=Path,
        default=Path("results/horizon/binder_extraction.json"),
    )
    parser.add_argument("--expected-pairs", type=int, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    inputs = [path if path.is_absolute() else root / path for path in args.inputs]
    output = args.output if args.output.is_absolute() else root / args.output

    rows: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    static_keys = (
        "corpus", "lean_version", "mathlib_commit", "template_sha256",
        "extractor_sha256", "shard_count",
    )
    shared: dict[str, Any] | None = None
    shard_indices: set[int] = set()
    for path in inputs:
        if not path.exists():
            raise FileNotFoundError(path)
        provenance_path = path.with_name(path.stem.replace("binder_extraction", "binder_extraction_provenance") + path.suffix)
        provenance = json.loads(provenance_path.read_text())
        current = {key: provenance.get(key) for key in static_keys}
        if shared is None:
            shared = current
        elif current != shared:
            raise ValueError(f"incompatible provenance in {provenance_path}: {current} != {shared}")
        shard_index = int(provenance["shard_index"])
        if shard_index in shard_indices:
            raise ValueError(f"duplicate shard index {shard_index}")
        shard_indices.add(shard_index)
        payload = json.loads(path.read_text())
        rows.extend(payload)
        components.append({
            "file": str(path.relative_to(root) if path.is_relative_to(root) else path),
            "sha256": sha256(path),
            "tasks": len(payload),
            "shard_index": shard_index,
            "runs": provenance.get("runs", []),
            "resume_origin": provenance.get("resume_origin"),
        })

    assert shared is not None
    expected_shards = set(range(int(shared["shard_count"])))
    if shard_indices != expected_shards:
        raise ValueError(f"shards {sorted(shard_indices)} != expected {sorted(expected_shards)}")
    keys = [(str(row["pair"]), str(row["side"])) for row in rows]
    if len(set(keys)) != len(keys):
        duplicates = [key for key, count in Counter(keys).items() if count > 1]
        raise ValueError(f"duplicate task keys: {duplicates[:10]}")
    expected_tasks = 2 * args.expected_pairs
    if len(rows) != expected_tasks:
        raise ValueError(f"merged {len(rows)} tasks, expected {expected_tasks}")
    pair_counts = Counter(pair for pair, _side in keys)
    pair_sides: dict[str, set[str]] = defaultdict(set)
    for pair, side in keys:
        pair_sides[pair].add(side)
    malformed = [
        pair for pair, count in pair_counts.items()
        if count != 2 or pair_sides[pair] != {"h", "a"}
    ]
    if len(pair_counts) != args.expected_pairs or malformed:
        raise ValueError(
            f"pair coverage is {len(pair_counts)}; malformed side counts: {malformed[:10]}"
        )

    rows.sort(key=lambda row: (row["pair"], row["side"]))
    output.write_text(json.dumps(rows, indent=2))
    status_counts = dict(sorted(Counter(row["status"] for row in rows).items()))
    status_by_side = {
        side: dict(sorted(Counter(
            row["status"] for row in rows if row["side"] == side
        ).items()))
        for side in ("h", "a")
    }
    target_manifest = root / str(shared["corpus"]) / "targets.csv"
    if not target_manifest.exists():
        raise FileNotFoundError(target_manifest)
    corpus_root = target_manifest.parent
    corpus_digest = hashlib.sha256()
    corpus_files = sorted(
        list((corpus_root / "human").glob("pair_*.lean"))
        + list((corpus_root / "ai").glob("pair_*.lean"))
    )
    for path in corpus_files:
        corpus_digest.update(
            str(path.relative_to(corpus_root)).encode("utf-8")
            + b"\0" + path.read_bytes() + b"\0"
        )
    merged_provenance = {
        **shared,
        "tasks": len(rows),
        "pairs": len(pair_counts),
        "status_counts": status_counts,
        "status_by_side": status_by_side,
        "target_manifest": str(target_manifest.relative_to(root)),
        "target_manifest_sha256": sha256(target_manifest),
        "corpus_source_files": len(corpus_files),
        "corpus_source_tree_sha256": corpus_digest.hexdigest(),
        "components": sorted(components, key=lambda item: item["shard_index"]),
        "output_sha256": sha256(output),
    }
    provenance_output = output.with_name(
        output.stem.replace("binder_extraction", "binder_extraction_provenance") + output.suffix
    )
    provenance_output.write_text(json.dumps(merged_provenance, indent=2))
    print(json.dumps(merged_provenance, indent=2))


if __name__ == "__main__":
    main()
