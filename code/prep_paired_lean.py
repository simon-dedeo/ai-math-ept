"""Materialize paired NuminaMath-LEAN artifacts as standalone Lean files.

The default recreates the historical 500-pair, moderate-length sample.  Use
``--full`` for every pair admitted by ``paired_horizon.load_pairs``.  The full
mode defaults to a separate directory so it cannot silently alter experiments
that used the historical sample.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from paired_horizon import load_pairs, serialized_target_signature


DECL = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:private\s+|protected\s+|noncomputable\s+)*"
    r"(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_'.!?«»]*)",
    re.MULTILINE,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output
    if output is None:
        output = root / "census" / ("paired_numina_full" if args.full else "paired_numina")
    elif not output.is_absolute():
        output = root / output
    human_dir, ai_dir = output / "human", output / "ai"
    human_dir.mkdir(parents=True, exist_ok=True)
    ai_dir.mkdir(parents=True, exist_ok=True)

    frame = load_pairs(root).copy()
    if not args.full:
        for column, short in (("human_formal_proof", "hl"), ("prover_formal_proof", "al")):
            frame[short] = frame[column].astype(str).map(lambda text: len(text.splitlines()))
        frame = frame[frame.hl.between(8, 200) & frame.al.between(8, 200)]
        frame = frame.sample(n=min(args.sample_size, len(frame)), random_state=args.seed)

    written = 0
    seen: set[str] = set()
    targets: list[dict[str, str]] = []
    for record in frame.itertuples(index=False):
        pair = "pair_" + str(record.uuid)[:8]
        if pair in seen:
            raise RuntimeError(f"8-character UUID prefix collision: {pair}")
        seen.add(pair)
        human, ai = str(record.human_formal_proof), str(record.prover_formal_proof)
        if not DECL.findall(human) or not DECL.findall(ai):
            continue
        (human_dir / f"{pair}.lean").write_text(human)
        (ai_dir / f"{pair}.lean").write_text(ai)
        human_signature = serialized_target_signature(record.human_declarations)
        ai_signature = serialized_target_signature(record.prover_declarations)
        if human_signature is None or ai_signature is None:
            raise RuntimeError(f"missing structured target signature: {pair}")
        targets.append({
            "pair": pair,
            "h_target": human_signature[1],
            "a_target": ai_signature[1],
        })
        written += 1

    with (output / "targets.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pair", "h_target", "a_target"])
        writer.writeheader()
        writer.writerows(targets)

    print({
        "mode": "full" if args.full else "sample",
        "eligible": len(frame),
        "written_pairs": written,
        "output": str(output),
    })


if __name__ == "__main__":
    main()
