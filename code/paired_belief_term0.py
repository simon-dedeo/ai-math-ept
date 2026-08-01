"""Component-aware paired belief dynamics on clean unexpanded proof terms.

This replaces the unfinished expanded-term run.  It matches the structural
``term0`` analysis, excludes Lean error-recovery terms, writes every pair
incrementally, and reports theorem belief separately from graph means.  For
each graph it also reports the weak-component coverage of the theorem root, so
an all-node mean can be distinguished from a root-component mean.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy import stats
from scipy.sparse.csgraph import connected_components

from belief import beliefs


def arrays_from_json(path: str) -> tuple[dict, int, np.ndarray, bool]:
    with open(path) as f:
        d = json.load(f)
    n = int(d["nodes"])
    edges = np.asarray(d["edges"], dtype=np.int64)
    if edges.size:
        A = sp.csr_matrix((np.ones(len(edges), dtype=np.int8),
                           (edges[:, 0], edges[:, 1])), shape=(n, n))
        A.sum_duplicates(); A.data[:] = 1; A.eliminate_zeros(); A.sort_indices()
    else:
        A = sp.csr_matrix((n, n), dtype=np.int8)
    P = A.T.tocsr()
    arrs = {"n": n, "pre_ptr": P.indptr.astype(np.int64),
            "pre_idx": P.indices.astype(np.int64),
            "dep_ptr": A.indptr.astype(np.int64),
            "dep_idx": A.indices.astype(np.int64)}
    labels = d.get("labels", [])
    roots = [i for i, x in enumerate(labels) if str(x).startswith("THM:")]
    root = roots[-1] if roots else n - 1
    has_sorry = any("sorry" in str(x).lower() or "syntheticopaque" in str(x).lower()
                    for x in labels)
    _, comp = connected_components(A + A.T, directed=False)
    root_mask = comp == comp[root]
    return arrs, root, root_mask, has_sorry


def analyse(path: str, seed: int, runs: int, sweeps: int) -> dict | None:
    arrs, root, root_mask, has_sorry = arrays_from_json(path)
    if has_sorry:
        return None
    row = {"N": int(arrs["n"]), "root_component_share": float(root_mask.mean())}
    for j, eps in enumerate((0.10, 0.05, 0.01)):
        b = beliefs(arrs, eps, eps, sweeps=sweeps, n_runs=runs,
                    seed=seed + 104729 * j)
        tag = f"{eps:g}"
        row[f"theorem_{tag}"] = float(b[root])
        row[f"mean_all_{tag}"] = float(b.mean())
        row[f"mean_root_component_{tag}"] = float(b[root_mask].mean())
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/ai_math_ept_orchard"))
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--sweeps", type=int, default=10)
    ap.add_argument("--tag", default="paired_belief_term0")
    args = ap.parse_args()
    root = Path(args.root)
    hp = root / "networks" / "paired_human"
    apath = root / "networks" / "paired_ai"
    suffix = "_term0.json"
    H = {Path(p).name[:-len(suffix)]: p for p in glob.glob(str(hp / f"*{suffix}"))}
    A = {Path(p).name[:-len(suffix)]: p for p in glob.glob(str(apath / f"*{suffix}"))}
    common = sorted(set(H) & set(A))
    outdir = root / "results" / "final_synthesis"
    outdir.mkdir(parents=True, exist_ok=True)
    jsonl = outdir / f"{args.tag}.jsonl"
    completed = set()
    if jsonl.exists():
        with open(jsonl) as f:
            for line in f:
                try: completed.add(json.loads(line)["pair"])
                except Exception: pass
    rows = []
    if jsonl.exists():
        with open(jsonl) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    print(f"common={len(common)} already={len(completed)}", flush=True)
    for i, key in enumerate(common, 1):
        if key in completed:
            continue
        seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
        try:
            h = analyse(H[key], seed, args.runs, args.sweeps)
            # Common seeds reduce avoidable Monte Carlo variation in the paired
            # contrast (trajectories still diverge when graph sizes differ).
            a = analyse(A[key], seed, args.runs, args.sweeps)
            if h is None or a is None:
                continue
            rec = {"pair": key, **{f"h_{k}": v for k, v in h.items()},
                   **{f"a_{k}": v for k, v in a.items()}}
            with open(jsonl, "a") as f:
                f.write(json.dumps(rec) + "\n")
            rows.append(rec)
        except Exception as exc:
            print(f"FAIL {key}: {exc}", flush=True)
        if i % 10 == 0:
            print(f"{i}/{len(common)} retained={len(rows)}", flush=True)
    d = pd.DataFrame(rows).drop_duplicates("pair", keep="last")
    d.to_csv(outdir / f"{args.tag}.csv", index=False)
    summary = {"n_pairs": int(len(d)), "runs": args.runs, "sweeps": args.sweeps,
               "metrics": {}}
    metrics = [c[2:] for c in d.columns if c.startswith("h_") and f"a_{c[2:]}" in d]
    for metric in metrics:
        x, y = d[f"h_{metric}"].astype(float), d[f"a_{metric}"].astype(float)
        diff = y - x
        try: p = float(stats.wilcoxon(diff).pvalue)
        except ValueError: p = float("nan")
        summary["metrics"][metric] = {
            "human_median": float(x.median()), "ai_median": float(y.median()),
            "median_paired_diff": float(diff.median()), "wilcoxon_p": p,
            "prob_ai_greater": float((diff > 0).mean())}
    with open(outdir / f"{args.tag}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
