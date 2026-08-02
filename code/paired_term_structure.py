"""Fast paired structural analysis of elaborated human and AI proof terms.

This deliberately avoids the expensive Ising simulations.  It compares raw
proof-term DAGs (``term0``) for the same formal statement, using only metrics
that can be computed directly from the extracted graph.  Results are paired by
NuminaMath UUID prefix and cluster-bootstrap uncertainty is reported over the
dataset's coarse ``source`` field.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import deque

import numpy as np
import pandas as pd
from scipy import stats


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    if len(x) == 0 or x.sum() == 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def fixed_alpha(deg: np.ndarray, xmin: int) -> float:
    """Discrete-tail approximation used by the replication scripts."""
    x = np.asarray([d for d in deg if d >= xmin], dtype=float)
    if len(x) < 20:
        return float("nan")
    return float(1.0 + len(x) / np.log(x / (xmin - 0.5)).sum())


def dag_depth(n: int, edges: list[list[int]]) -> int:
    succ = [[] for _ in range(n)]
    indeg = np.zeros(n, dtype=np.int64)
    for u, v in edges:
        if 0 <= u < n and 0 <= v < n and u != v:
            succ[u].append(v)
            indeg[v] += 1
    q = deque(np.flatnonzero(indeg == 0).tolist())
    depth = np.zeros(n, dtype=np.int64)
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in succ[u]:
            if depth[v] < depth[u] + 1:
                depth[v] = depth[u] + 1
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return int(depth.max()) if seen == n else -1


def measure(path: str) -> dict:
    with open(path) as f:
        d = json.load(f)
    n = int(d["nodes"])
    edges = d["edges"]
    outdeg = np.zeros(n, dtype=np.int64)
    indeg = np.zeros(n, dtype=np.int64)
    for u, v in edges:
        if 0 <= u < n and 0 <= v < n and u != v:
            outdeg[u] += 1
            indeg[v] += 1
    labels = d.get("labels", [])
    const_labels = [x for x in labels if isinstance(x, str) and x.startswith("C:")]
    has_sorry = any(
        "sorry" in str(x).lower() or "syntheticopaque" in str(x).lower()
        for x in labels
    )
    return {
        "N": n,
        "E": int(len(edges)),
        "visits": int(d.get("visits", len(edges))),
        "dedup_ratio": float(d.get("visits", len(edges)) / max(n, 1)),
        "depth": dag_depth(n, edges),
        "mean_indeg": float(indeg.mean()),
        "max_outdeg": int(outdeg.max()) if n else 0,
        "out_gini": gini(outdeg),
        "n_constants": int(len(const_labels)),
        "n_distinct_constants": int(len(set(const_labels))),
        "constant_share": float(len(const_labels) / max(n, 1)),
        "alpha_x2": fixed_alpha(outdeg, 2),
        "alpha_x5": fixed_alpha(outdeg, 5),
        "alpha_x10": fixed_alpha(outdeg, 10),
        "has_sorry": has_sorry,
        "truncated": bool(d.get("truncated", False)),
    }


def bootstrap_diff(df: pd.DataFrame, h: str, a: str, cluster: str,
                   n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    groups = [g for _, g in df.dropna(subset=[h, a, cluster]).groupby(cluster)]
    vals = []
    for _ in range(n_boot):
        sample = pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        vals.append(float(np.median(sample[a].to_numpy(float) - sample[h].to_numpy(float))))
    return tuple(float(x) for x in np.percentile(vals, [2.5, 97.5]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/ai_math_ept"))
    ap.add_argument("--mode", default="term0", choices=["term0", "term"])
    ap.add_argument("--human-dir", default="",
                    help="override directory containing human network JSON files")
    ap.add_argument("--ai-dir", default="",
                    help="override directory containing AI network JSON files")
    ap.add_argument("--outdir", default="",
                    help="override results directory")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--allow-sorry", action="store_true",
                    help="include networks containing sorryAx/SyntheticOpaque labels")
    args = ap.parse_args()

    hdir = args.human_dir or os.path.join(args.root, "networks", "paired_human")
    adir = args.ai_dir or os.path.join(args.root, "networks", "paired_ai")
    hpat = os.path.join(hdir, f"*_{args.mode}.json")
    apat = os.path.join(adir, f"*_{args.mode}.json")
    suffix = f"_{args.mode}.json"
    human = {os.path.basename(p)[:-len(suffix)]: p for p in glob.glob(hpat)}
    ai = {os.path.basename(p)[:-len(suffix)]: p for p in glob.glob(apat)}
    common = sorted(set(human) & set(ai))

    # Prefer metadata for every validated human/prover pair.  The corrected
    # source-level CSV excludes proofs with zero regex-counted premises, which
    # previously lumped 129/312 retained term pairs into one artificial
    # ``unknown`` cluster and distorted the cluster bootstrap.
    shard_pat = os.path.join(
        args.root, "census", "numinamath-proof-artifacts", "data", "lite",
        "shards", "*.parquet")
    shards = glob.glob(shard_pat)
    if shards:
        pieces = []
        cols = ["uuid", "source", "human_validation_status",
                "prover_validation_status", "human_proof_available",
                "prover_proof_available"]
        for path in shards:
            p = pd.read_parquet(path, columns=cols)
            p = p[(p.human_proof_available == True)
                  & (p.prover_proof_available == True)
                  & (p.human_validation_status == "valid")
                  & (p.prover_validation_status == "valid")]
            pieces.append(p[["uuid", "source"]])
        meta = pd.concat(pieces, ignore_index=True).drop_duplicates("uuid")
    else:
        meta_path = os.path.join(args.root, "results", "paired_numina_corrected.csv")
        meta = pd.read_csv(meta_path, usecols=["uuid", "source"])
    source = {"pair_" + str(r.uuid)[:8]: str(r.source) for r in meta.itertuples(index=False)}

    rows = []
    for i, key in enumerate(common, 1):
        try:
            hm, am = measure(human[key]), measure(ai[key])
            if not args.allow_sorry and (hm["has_sorry"] or am["has_sorry"]):
                continue
            rows.append({"pair": key, "source": source.get(key, "unknown"),
                         **{f"h_{k}": v for k, v in hm.items()},
                         **{f"a_{k}": v for k, v in am.items()}})
        except Exception as exc:
            print(f"[fail] {key}: {exc}", flush=True)
        if i % 25 == 0:
            print(f"{i}/{len(common)}", flush=True)

    df = pd.DataFrame(rows)
    outdir = args.outdir or os.path.join(args.root, "results", "paired_term_structure")
    os.makedirs(outdir, exist_ok=True)
    df.to_csv(os.path.join(outdir, f"{args.mode}.csv"), index=False)

    metrics = [
        "N", "E", "dedup_ratio", "depth", "max_outdeg", "out_gini",
        "n_constants", "n_distinct_constants", "constant_share",
        "alpha_x2", "alpha_x5", "alpha_x10",
    ]
    summary = {"mode": args.mode, "n_pairs": int(len(df)),
               "n_sources": int(df.source.nunique()), "metrics": {}}
    print(f"\nmode={args.mode} pairs={len(df)} sources={df.source.nunique()}")
    print(f"{'metric':24s} {'human':>11s} {'AI':>11s} {'med.diff':>11s} {'CI(cluster)':>23s} {'p':>10s}")
    for metric in metrics:
        h, a = f"h_{metric}", f"a_{metric}"
        ok = df[h].notna() & df[a].notna()
        d = df.loc[ok]
        if len(d) < 8:
            continue
        diff = d[a].astype(float) - d[h].astype(float)
        try:
            p = float(stats.wilcoxon(d[h].astype(float), d[a].astype(float)).pvalue)
        except Exception:
            p = float("nan")
        lo, hi = bootstrap_diff(d, h, a, "source", n_boot=args.boot)
        rec = {
            "n": int(len(d)), "human_median": float(d[h].median()),
            "ai_median": float(d[a].median()), "median_paired_diff": float(diff.median()),
            "cluster_ci": [lo, hi], "wilcoxon_p": p,
            "prob_ai_greater": float((diff > 0).mean()),
        }
        summary["metrics"][metric] = rec
        print(f"{metric:24s} {rec['human_median']:11.4g} {rec['ai_median']:11.4g} "
              f"{rec['median_paired_diff']:11.4g} [{lo:8.3g},{hi:8.3g}] {p:10.3g}")

    with open(os.path.join(outdir, f"{args.mode}.json"), "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
