"""
study5_mathlib.py — Belief dynamics on ALL of Mathlib as one proof network.

Data: MathNetwork/MathlibGraph (Feb 2026): 633,364 declarations,
mathlib_edges.csv rows (source, target, is_explicit, is_simplifier) where
SOURCE USES TARGET. Our convention: premise = target -> dependent = source.

Two layers:
  full     — all dependency edges (includes compiler-synthesized, ~70%)
  explicit — only edges visible in the source text (is_explicit=True):
             the network a human reader of Mathlib actually sees.

Measure at each one-step error rate eps: mean belief over all nodes, over
theorem-kind nodes, and belief in famous target theorems. This asks: does
the *entire library* (the largest body of interconnected formal mathematics
ever built) sit above the epistemic phase transition?
"""
import os, sys, time, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/ai_math_ept/code"))
from belief import _beliefs, beta_of_eps

MG = os.path.expanduser("~/ai_math_ept/projects/mathlib_graph")
OUT = os.path.expanduser("~/ai_math_ept/results/study5")
os.makedirs(OUT, exist_ok=True)

FAMOUS = [
    "Nat.exists_infinite_primes", "irrational_sqrt_two",
    "fermatLastTheoremThree", "Real.tendsto_sum_pi_div_four",
    "ZMod.wilsons_lemma", "Matrix.aeval_self_charpoly",
    "Function.Embedding.schroeder_bernstein",
]

t0 = time.time()
print("loading edges...", flush=True)
E = pd.read_csv(os.path.join(MG, "mathlib_edges.csv"))
print(f"{len(E)} edges ({time.time()-t0:.0f}s)", flush=True)

names = pd.unique(pd.concat([E["source"], E["target"]]))
idx = {n: i for i, n in enumerate(names)}
n = len(names)
print(f"{n} nodes", flush=True)

nodes = pd.read_csv(os.path.join(MG, "nodes.csv"))
kind = {r.name_: r.kind for r in nodes.itertuples(index=False)} if False else {}
kindmap = dict(zip(nodes["name"], nodes["kind"]))
is_thm = np.zeros(n, dtype=bool)
for nm, i in idx.items():
    if kindmap.get(nm) == "theorem":
        is_thm[i] = True
print(f"theorem nodes: {is_thm.sum()}", flush=True)

res = {}
for layer in ["explicit", "full"]:
    sub = E[E["is_explicit"] == True] if layer == "explicit" else E  # noqa
    src = sub["source"].map(idx).to_numpy(dtype=np.int64)   # dependent
    dst = sub["target"].map(idx).to_numpy(dtype=np.int64)   # premise
    m = len(src)
    # premise -> dependent: premises of node v are dst where src==v
    order = np.argsort(src, kind="stable")
    pre_idx = dst[order]
    pre_ptr = np.zeros(n + 1, dtype=np.int64)
    np.add.at(pre_ptr, src + 1, 1)
    pre_ptr = np.cumsum(pre_ptr)
    order2 = np.argsort(dst, kind="stable")
    dep_idx = src[order2]
    dep_ptr = np.zeros(n + 1, dtype=np.int64)
    np.add.at(dep_ptr, dst + 1, 1)
    dep_ptr = np.cumsum(dep_ptr)
    print(f"[{layer}] {m} edges, built CSR ({time.time()-t0:.0f}s)", flush=True)

    rows = []
    for eps in [0.3, 0.2, 0.1, 0.05, 0.02, 0.01]:
        b = _beliefs(pre_ptr, pre_idx, dep_ptr, dep_idx,
                     beta_of_eps(eps), beta_of_eps(eps),
                     0.75, 10, 5, 1234)
        row = dict(eps=eps,
                   mean=float(b.mean()),
                   mean_theorems=float(b[is_thm].mean()),
                   famous={f: float(b[idx[f]]) for f in FAMOUS if f in idx})
        rows.append(row)
        print(f"[{layer}] eps={eps}: mean={row['mean']:.4f} "
              f"thm={row['mean_theorems']:.4f} ({time.time()-t0:.0f}s)",
              flush=True)
    res[layer] = rows

with open(os.path.join(OUT, "mathlib_ept.json"), "w") as f:
    json.dump(res, f, indent=1)
print(f"done {time.time()-t0:.0f}s", flush=True)
