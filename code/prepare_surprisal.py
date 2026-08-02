"""Prepare same-theorem Lean bodies for token-surprisal scoring."""
from __future__ import annotations

import argparse
from pathlib import Path

from paired_horizon import load_pairs, proof_body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pairs", type=Path, default=Path("results/paired_term_structure/term0.csv"))
    parser.add_argument("--max-pairs", type=int)
    args = parser.parse_args()
    root = args.root.resolve()

    import pandas as pd

    allowed = pd.read_csv(root / args.pairs).pair.astype(str).tolist()
    if args.max_pairs is not None:
        allowed = allowed[: args.max_pairs]
    allowed_set = set(allowed)
    raw = load_pairs(root)
    raw["pair"] = "pair_" + raw.uuid.astype(str).str[:8]
    raw = raw[raw.pair.isin(allowed_set)].set_index("pair")

    outdir = root / "tmp" / "horizon" / "surprisal_docs"
    outdir.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    for pair in allowed:
        if pair not in raw.index:
            continue
        record = raw.loc[pair]
        for side, column in (("h", "human_formal_proof"), ("a", "prover_formal_proof")):
            document = f"{pair}_{side}"
            path = outdir / f"{document}.lean"
            path.write_text(proof_body(record[column]), encoding="utf-8")
            manifest.append(f"{document}\t{path}")
    manifest_path = root / "tmp" / "horizon" / "surprisal_manifest.tsv"
    manifest_path.write_text("\n".join(manifest) + "\n")
    print(f"wrote {len(manifest)} documents to {manifest_path}")


if __name__ == "__main__":
    main()
