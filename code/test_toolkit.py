"""Sanity tests for the EPT toolkit against the 2022 paper's qualitative results.

1. A linear chain must NOT show an EPT (belief in the theorem decays with
   length, the Humean regime).
2. A tinkering-and-reuse DAG (Krapivsky-Redner style copy model, the paper's
   generative mechanism) MUST show an EPT: near-unity theorem belief at
   eps = 0.01, i.e. far above the (1-eps)^depth chain expectation.
3. The copy-model out-degree should be heavy-tailed (alpha near 2), in-degree
   near-Poisson.
4. Abductive paradox: at fixed deductive confidence 0.9, pushing abductive
   confidence to 0.9999 should LOWER certainty vs abductive 0.99.
"""
import sys, time
import numpy as np
import networkx as nx

sys.path.insert(0, ".")
from proofnet import to_arrays, structural_stats, subnetwork_of
from belief import beliefs, certainty_curve, f2, contour_grid


def chain(n):
    G = nx.DiGraph()
    for i in range(n - 1):
        G.add_edge(i, i + 1)   # premise i -> dependent i+1; theorem = n-1
    return G


def copy_model(n, m=3, p_copy=0.7, seed=0):
    """Tinkering-and-reuse growth: each new claim depends on m prior claims;
    with prob p_copy each dependency is copied from a chosen claim's own
    premise list (reuse), else uniform random. Edges premise -> dependent."""
    rng = np.random.default_rng(seed)
    G = nx.DiGraph()
    G.add_node(0)
    for v in range(1, n):
        deps = set()
        anchor = int(rng.integers(0, v))
        deps.add(anchor)
        anchor_pre = list(G.predecessors(anchor))
        while len(deps) < min(m, v):
            if anchor_pre and rng.random() < p_copy:
                deps.add(int(rng.choice(anchor_pre)))
            else:
                deps.add(int(rng.integers(0, v)))
        for u in deps:
            G.add_edge(u, v)
    return G


def main():
    t0 = time.time()
    # --- 1. chain: no EPT
    Gc = chain(200)
    ac = to_arrays(Gc)
    th = ac["index"][199]
    fc = f2(ac, th, eps=0.05, n_runs=20)
    print(f"[chain n=200]     belief(theorem) at eps=0.05: {fc:.3f}  (expect low/near 0.5)")

    # --- 2. copy model: EPT
    Gt = copy_model(2000, m=3, p_copy=0.7)
    at = to_arrays(Gt)
    # theorem: a recent node with deep ancestry
    th_t = at["index"][1999]
    curve = certainty_curve(at, [0.2, 0.1, 0.05, 0.02, 0.01],
                            theorem_idx=th_t, n_runs=10)
    print("[copy model n=2000] eps -> mean belief, theorem belief:")
    for r in curve:
        print(f"   eps={r['eps']:.3f}  mean={r['mean_belief']:.3f}  "
              f"thm={r['theorem_belief']:.3f}  axioms={r['axiom_belief']:.3f}")

    # --- 3. structure
    st, _ = structural_stats(Gt, "copy_model")
    print("[copy model] structure:", {k: st[k] for k in
          ("nodes", "edges", "mean_in_degree", "max_out_degree",
           "alpha", "alpha_err", "modularity", "n_modules") if k in st})

    # --- 4. abductive paradox
    b_lo = beliefs(at, 1 - 0.9, 1 - 0.99, n_runs=10).mean()
    b_hi = beliefs(at, 1 - 0.9, 1 - 0.9999, n_runs=10).mean()
    print(f"[abductive paradox] dep=0.9: certainty(abd=0.99)={b_lo:.3f} "
          f"vs certainty(abd=0.9999)={b_hi:.3f}  (expect second <= first)")

    print(f"total {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
