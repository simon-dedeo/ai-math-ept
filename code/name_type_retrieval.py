"""Model-relative assay of whether local-claim names retrieve their own types.

This is deliberately a paired, within-proof task.  For each proof with two to
eight uniquely named ``have`` claims, embed every naturalized name and every
claim type.  A name succeeds to the extent that its own type ranks above the
other types in that same proof.  Percentile rank has chance expectation 1/2
regardless of the number of claims.  Human and AI scores are compared only for
identical theorem pairs retained on both sides.

The script prepares newline-delimited prompts for ``llama-embedding`` and then
analyzes its OpenAI-style JSON output.  Goedel-Prover is not contrastively
trained as an embedding model, so this is an exploratory interface assay, not a
semantic ground truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from paired_horizon import named_have_declarations, proof_body


DELIMITER_CLOSE = {"(": ")", "[": "]", "{": "}"}


def claim_type(body: str, declaration: dict[str, Any]) -> str | None:
    """Return the explicit type between the header colon and top-level ``:=``."""
    start = int(declaration["end"])
    if start == 0 or body[start - 1] != ":":
        return None
    stack: list[str] = []
    i = start
    while i + 1 < len(body):
        char = body[i]
        if char in DELIMITER_CLOSE:
            stack.append(DELIMITER_CLOSE[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and body[i : i + 2] == ":=":
            value = " ".join(body[start:i].split())
            return value or None
        i += 1
    return None


def naturalize(name: str) -> str:
    value = name.replace("_", " ")
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    value = re.sub(r"(?<=[A-Za-z])(?=[0-9₀-₉])", " ", value)
    # Lean accepts identifiers consisting entirely of underscores.  Preserve the
    # raw spelling in that rare case rather than emitting an empty prompt.
    return " ".join(value.split()) or name


def prepare(root: Path, outdir: Path, max_pairs: int, seed: int) -> None:
    claims = pd.read_csv(root / "results/horizon/claims.csv.gz")
    pairs = pd.read_csv(root / "results/horizon/source_pairs.csv.gz")[["pair", "source"]]
    counts = claims.groupby(["pair", "side"]).agg(
        claims=("name", "size"), unique_names=("name", "nunique")
    ).reset_index()
    eligible = counts[
        counts.claims.between(2, 8) & counts.claims.eq(counts.unique_names)
    ]
    both = eligible.pivot(index="pair", columns="side", values="claims").dropna().index
    candidates = pairs[pairs.pair.isin(both)].copy()
    if len(candidates) > max_pairs:
        # Preserve every source group approximately in proportion to its mass.
        rng = np.random.default_rng(seed)
        candidates["key"] = rng.random(len(candidates))
        total_candidates = len(candidates)
        pieces = [
            group.nsmallest(
                max(1, round(max_pairs * len(group) / total_candidates)), "key"
            )
            for _source, group in candidates.groupby("source", sort=False)
        ]
        candidates = pd.concat(pieces)

    rows: list[dict[str, Any]] = []
    prompts: list[str] = []
    for pair_row in candidates.sort_values("pair").itertuples(index=False):
        for side, folder in (("h", "human"), ("a", "ai")):
            path = root / "census/paired_numina_exact" / folder / f"{pair_row.pair}.lean"
            body = proof_body(path.read_text())
            declarations = named_have_declarations(body)
            selected = claims[claims.pair.eq(pair_row.pair) & claims.side.eq(side)].sort_values(
                "claim_index"
            )
            if len(declarations) != len(selected):
                continue
            typed: list[tuple[int, str, str]] = []
            for row in selected.itertuples(index=False):
                declaration = declarations[int(row.claim_index)]
                type_text = claim_type(body, declaration)
                if type_text is None:
                    break
                typed.append((int(row.claim_index), str(row.name), type_text))
            if len(typed) != len(selected):
                continue
            for claim_index, name, type_text in typed:
                name_prompt_index = len(prompts)
                prompts.append(f"Lean mathematical concept: {naturalize(name)}")
                type_prompt_index = len(prompts)
                prompts.append(f"Lean mathematical concept: {type_text}")
                rows.append({
                    "pair": pair_row.pair,
                    "source": pair_row.source,
                    "side": side,
                    "claim_index": claim_index,
                    "name": name,
                    "type": type_text,
                    "name_prompt_index": name_prompt_index,
                    "type_prompt_index": type_prompt_index,
                })

    frame = pd.DataFrame(rows)
    complete = frame.groupby("pair").side.nunique()
    keep = complete[complete.eq(2)].index
    frame = frame[frame.pair.isin(keep)].copy()
    used_indices = sorted(
        set(frame.name_prompt_index.astype(int)) | set(frame.type_prompt_index.astype(int))
    )
    remap = {old: new for new, old in enumerate(used_indices)}
    prompt_subset = [prompts[index] for index in used_indices]
    frame["name_prompt_index"] = frame.name_prompt_index.map(remap)
    frame["type_prompt_index"] = frame.type_prompt_index.map(remap)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "prompts.txt").write_text("\n".join(prompt_subset) + "\n")
    frame.to_csv(outdir / "manifest.csv", index=False)
    print({"pairs": int(frame.pair.nunique()), "claims": len(frame), "prompts": len(prompt_subset)})


def average_tied_percentile(similarities: np.ndarray, target: int) -> float:
    value = similarities[target]
    better = int((similarities > value + 1e-12).sum())
    tied = int((np.abs(similarities - value) <= 1e-12).sum())
    mean_rank_zero_based = better + (tied - 1) / 2
    n = len(similarities)
    return 1.0 if n == 1 else float(1 - mean_rank_zero_based / (n - 1))


def cluster_ci(frame: pd.DataFrame, boot: int, seed: int) -> list[float]:
    grouped = frame.groupby("source")[["human", "ai"]].agg(["sum", "count"])
    values = np.column_stack([
        grouped[("human", "sum")], grouped[("human", "count")],
        grouped[("ai", "sum")], grouped[("ai", "count")],
    ]).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(boot, len(values)))
    sample = values[draws].sum(axis=1)
    delta = sample[:, 2] / sample[:, 3] - sample[:, 0] / sample[:, 1]
    return [float(x) for x in np.percentile(delta, [2.5, 97.5])]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analyze(root: Path, outdir: Path, embeddings_path: Path, pooling: str,
            boot: int, seed: int) -> None:
    manifest = pd.read_csv(outdir / "manifest.csv")
    payload = json.loads(embeddings_path.read_text())
    embeddings = np.asarray([row["embedding"] for row in payload["data"]], dtype=np.float32)
    embeddings /= np.maximum(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-12)
    if len(embeddings) != 2 * len(manifest):
        raise ValueError(f"{len(embeddings)} embeddings for {len(manifest)} claims")

    claim_rows: list[dict[str, Any]] = []
    for (pair, side), group in manifest.groupby(["pair", "side"], sort=False):
        group = group.sort_values("claim_index")
        name_vectors = embeddings[group.name_prompt_index.astype(int)]
        type_vectors = embeddings[group.type_prompt_index.astype(int)]
        similarity = name_vectors @ type_vectors.T
        for index, row in enumerate(group.itertuples(index=False)):
            claim_rows.append({
                "pair": pair,
                "source": row.source,
                "side": side,
                "claim_index": int(row.claim_index),
                "name": row.name,
                "candidate_types": len(group),
                "own_similarity": float(similarity[index, index]),
                "retrieval_percentile": average_tied_percentile(similarity[index], index),
                "top1": float(similarity[index, index] >= similarity[index].max() - 1e-12),
            })
    claim_frame = pd.DataFrame(claim_rows)
    proof_frame = claim_frame.groupby(["pair", "source", "side"]).agg(
        retrieval_percentile=("retrieval_percentile", "mean"),
        top1=("top1", "mean"), claims=("name", "size")
    ).reset_index()
    proof_frame["top1_excess_chance"] = (
        (proof_frame.top1 - 1 / proof_frame.claims)
        / (1 - 1 / proof_frame.claims)
    )
    paired = proof_frame.pivot(index=["pair", "source"], columns="side")
    paired.columns = [f"{metric}_{side}" for metric, side in paired.columns]
    paired = paired.reset_index()
    for metric in ("retrieval_percentile", "top1", "top1_excess_chance"):
        paired[f"human_{metric}"] = paired[f"{metric}_h"]
        paired[f"ai_{metric}"] = paired[f"{metric}_a"]

    shared_model_provenance = json.loads(
        (root / "results/horizon/surprisal_provenance.json").read_text()
    )
    summary: dict[str, Any] = {
        "model_relative_warning": (
            "Goedel-Prover is a causal proof model, not a contrastively trained semantic encoder"
        ),
        "pairs": len(paired),
        "claims": len(claim_frame),
        "embedding_provenance": {
            "pooling": pooling,
            "prompt": "Lean mathematical concept: <naturalized name or exact explicit type>",
            "prompt_file_sha256": sha256(outdir / "prompts.txt"),
            "manifest_sha256": sha256(outdir / "manifest.csv"),
            "embedding_output_sha256": sha256(embeddings_path),
            "model": {
                key: shared_model_provenance[key]
                for key in (
                    "base_model", "quantization", "gguf_source", "gguf_filename",
                    "gguf_sha256", "llama_cpp_version", "hardware",
                )
            },
        },
        "metrics": {},
        "equal_claim_count_sensitivity": {},
    }
    for metric in ("retrieval_percentile", "top1", "top1_excess_chance"):
        human, ai = paired[f"human_{metric}"], paired[f"ai_{metric}"]
        difference = ai - human
        try:
            p = float(wilcoxon(difference).pvalue)
        except ValueError:
            p = 1.0
        summary["metrics"][metric] = {
            "human": float(human.mean()),
            "ai": float(ai.mean()),
            "ai_minus_human": float(difference.mean()),
            "paired_wilcoxon_p": p,
            "source_cluster_ci": cluster_ci(
                paired[["source", f"human_{metric}", f"ai_{metric}"]].rename(
                    columns={f"human_{metric}": "human", f"ai_{metric}": "ai"}
                ), boot, seed,
            ),
        }
        equal = paired[paired.claims_h.eq(paired.claims_a)]
        human_equal, ai_equal = equal[f"human_{metric}"], equal[f"ai_{metric}"]
        summary["equal_claim_count_sensitivity"][metric] = {
            "pairs": len(equal),
            "human": float(human_equal.mean()),
            "ai": float(ai_equal.mean()),
            "ai_minus_human": float((ai_equal - human_equal).mean()),
        }
    claim_frame.to_csv(outdir / "claim_scores.csv.gz", index=False,
                       compression={"method": "gzip", "mtime": 0})
    paired.to_csv(outdir / "proof_scores.csv", index=False)
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "analyze"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--outdir", type=Path, default=Path("tmp/horizon/name_retrieval"))
    parser.add_argument("--embeddings", type=Path)
    parser.add_argument("--pooling", default="mean")
    parser.add_argument("--max-pairs", type=int, default=300)
    parser.add_argument("--boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260802)
    args = parser.parse_args()
    root = args.root.resolve()
    outdir = args.outdir if args.outdir.is_absolute() else root / args.outdir
    if args.mode == "prepare":
        prepare(root, outdir, args.max_pairs, args.seed)
    else:
        if args.embeddings is None:
            parser.error("analyze requires --embeddings")
        embeddings = args.embeddings if args.embeddings.is_absolute() else root / args.embeddings
        analyze(root, outdir, embeddings, args.pooling, args.boot, args.seed)


if __name__ == "__main__":
    main()
