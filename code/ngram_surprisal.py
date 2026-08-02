"""Leave-one-source-out token-bigram surprisal for the horizon assay.

This deliberately simple model uses the byte spans produced by the fixed
Goedel-Prover tokenizer, but estimates probabilities only from documents in
other source groups.  It is a contamination-resistant sensitivity check, not a
competitive language model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--skeleton", type=Path,
        default=Path("results/horizon/token_surprisal.tsv"),
        help="token offsets; its model NLL values are ignored",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("results/horizon/token_surprisal_loso_bigram.tsv"),
    )
    parser.add_argument("--alpha", type=float, default=10.0)
    parser.add_argument("--beta", type=float, default=0.1)
    args = parser.parse_args()

    root = args.root.resolve()
    skeleton_path = args.skeleton if args.skeleton.is_absolute() else root / args.skeleton
    output_path = args.output if args.output.is_absolute() else root / args.output
    tokens = pd.read_csv(skeleton_path, sep="\t")
    sources = pd.read_csv(root / "results/horizon/source_pairs.csv.gz")
    source_map = sources.set_index("pair").source.to_dict()
    docs_dir = root / "tmp/horizon/surprisal_docs"

    documents: dict[str, tuple[str, list[bytes], pd.DataFrame]] = {}
    document_digest = hashlib.sha256()
    for document, frame in tokens.groupby("document", sort=False):
        raw = (docs_dir / f"{document}.lean").read_bytes()
        document_digest.update(document.encode("utf-8") + b"\0" + raw + b"\0")
        frame = frame.sort_values("token_index")
        sequence = [
            raw[int(start) : int(end)]
            for start, end in zip(frame.byte_start, frame.byte_end)
        ]
        documents[document] = (source_map.get(document[:-2], "unknown"), sequence, frame)

    global_uni: Counter[bytes] = Counter()
    global_bi: Counter[tuple[bytes, bytes]] = Counter()
    global_prev: Counter[bytes] = Counter()
    by_source: dict[str, tuple[Counter[bytes], Counter[tuple[bytes, bytes]], Counter[bytes]]] = {}
    bos = b"<BOS>"
    for source, sequence, _frame in documents.values():
        uni, bi, prev_counts = by_source.setdefault(source, (Counter(), Counter(), Counter()))
        previous = bos
        for token in sequence:
            global_uni[token] += 1
            global_bi[(previous, token)] += 1
            global_prev[previous] += 1
            uni[token] += 1
            bi[(previous, token)] += 1
            prev_counts[previous] += 1
            previous = token

    total = sum(global_uni.values())
    vocabulary = len(global_uni) + 1
    rows: list[tuple[str, int, int, int, float]] = []
    for document, (source, sequence, frame) in documents.items():
        source_uni, source_bi, source_prev = by_source[source]
        training_total = total - sum(source_uni.values())
        previous = bos
        for (_, record), token in zip(frame.iterrows(), sequence):
            unigram_count = global_uni[token] - source_uni[token]
            unigram_probability = (
                (unigram_count + args.beta)
                / (training_total + args.beta * vocabulary)
            )
            bigram_count = global_bi[(previous, token)] - source_bi[(previous, token)]
            previous_count = global_prev[previous] - source_prev[previous]
            probability = (
                (bigram_count + args.alpha * unigram_probability)
                / (previous_count + args.alpha)
            )
            rows.append((
                document, int(record.token_index), int(record.byte_start),
                int(record.byte_end), -math.log(probability),
            ))
            previous = token

    output = pd.DataFrame(
        rows, columns=["document", "token_index", "byte_start", "byte_end", "nll_nats"]
    )
    output.to_csv(output_path, sep="\t", index=False)
    provenance = {
        "model": "leave-one-source-out interpolated token bigram",
        "training_exclusion": "all documents in the held-out document's coarse source group",
        "token_offsets_from": str(skeleton_path.relative_to(root)),
        "token_offsets_sha256": hashlib.sha256(skeleton_path.read_bytes()).hexdigest(),
        "document_bytes_sha256": document_digest.hexdigest(),
        "source_pairs_sha256": hashlib.sha256(
            (root / "results/horizon/source_pairs.csv.gz").read_bytes()
        ).hexdigest(),
        "alpha_bigram_backoff": args.alpha,
        "beta_unigram_smoothing": args.beta,
        "documents": len(documents),
        "documents_by_source": dict(sorted(Counter(
            source for source, _sequence, _frame in documents.values()
        ).items())),
        "documents_labeled_unknown_source": sum(
            source == "unknown" for source, _sequence, _frame in documents.values()
        ),
        "tokens": len(output),
        "vocabulary": vocabulary,
    }
    provenance_path = root / "results/horizon/surprisal_loso_bigram_provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2))
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
