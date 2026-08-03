#!/usr/bin/env python3
"""Fetch the pinned NuminaMath-LEAN lite shards used by the horizon paper."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "census" / "numinamath-proof-artifacts"
REPOSITORY = "iiis-lean/NuminaMath-LEAN-Proof-Artifacts"
REVISION = "43f4ea4da40c48be8e89edb84cb0825d8a4dfe2d"
EXPECTED = {
    "numinamath_lean_proof_artifacts_lite-00000.parquet":
        "76ce5011716cbb139ea2eeecd15babddbfe8d169f1c1b7d93fd5167af5ec8b4c",
    "numinamath_lean_proof_artifacts_lite-00001.parquet":
        "385aadfa283d12202d1ebe7b805e99c8db7c99d9b609eac9b796a02554951cec",
    "numinamath_lean_proof_artifacts_lite-00002.parquet":
        "b408909d0036b4c453a035acf591e356ed60458ad2685701e95b983b05012fb7",
    "numinamath_lean_proof_artifacts_lite-00003.parquet":
        "e46bc255fd8e1ec8925aa86ede1fba7534f90927ff9a4b1098921b2026f6e1ae",
    "numinamath_lean_proof_artifacts_lite-00004.parquet":
        "09b6241b8a436387eadd9448b844c098b4e8b1f0fd7125a3e90544e4e77b24d6",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    shard_dir = DESTINATION / "data" / "lite" / "shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for filename, expected in EXPECTED.items():
        destination = shard_dir / filename
        if destination.is_file() and sha256(destination) == expected:
            print(f"already verified: {filename}")
            continue
        partial = destination.with_suffix(destination.suffix + ".partial")
        url = (
            f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/"
            f"data/lite/shards/{filename}?download=true"
        )
        print(f"downloading: {filename}")
        urllib.request.urlretrieve(url, partial)
        if sha256(partial) != expected:
            partial.unlink(missing_ok=True)
            raise SystemExit(f"download hash mismatch for {filename}")
        os.replace(partial, destination)
    actual = {path.name: sha256(path) for path in sorted(shard_dir.glob("*.parquet"))}
    if actual != EXPECTED:
        raise SystemExit(f"download hash mismatch:\nexpected={EXPECTED}\nactual={actual}")
    print(f"verified {len(actual)} pinned shards in {shard_dir}")


if __name__ == "__main__":
    main()
