"""
study4_etp.py — The Equational Theories Project implication graph as a new
kind of mathematical object, analyzed with the Viteri-DeDeo lens.

Questions:
 A. Structure: the certified knowledge = 4694 equations, ~22M ordered pairs
    decided. The *derivation skeleton* is the set of explicitly-proved
    implications (Lean-verified direct proofs); everything else is closure
    (transitivity + duality). What does the skeleton look like (degree
    distributions, SCC/Hasse condensation, modularity, depth) compared to
    classical proof networks (heavy-tailed reuse, alpha ~ 2, modular)?
 B. Epistemic robustness (the EPT question, made literal): if every direct
    certificate independently fails with probability eps, what fraction of
    the derived positive knowledge survives (still has a derivation path)?
    Multiple independent paths => phase-transition-like robustness;
    single fragile chains => Humean decay. Compare the observed redundancy
    with a degree-preserving null and with pure-chain expectation.
 C. Path redundancy census: distribution over implied pairs of
    (# edge-disjoint derivation paths), the graph-theoretic quantity that
    drives EPTs in the belief model.

Outputs to ~/ai_math_ept/results/study4/.
"""
import json, os, sys, zipfile, time
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import breadth_first_order, connected_components

DATA = os.path.expanduser("~/ai_math_ept/projects/equational_theories/data")
OUT = os.path.expanduser("~/ai_math_ept/results/study4")
os.makedirs(OUT, exist_ok=True)

CODES = {}


def load_outcomes(name="2024-11-10-outcomes.json.zip"):
    z = zipfile.ZipFile(os.path.join(DATA, name))
    d = json.loads(z.read(z.namelist()[0]))
    eqs = d["equations"]
    n = len(eqs)
    M = np.zeros((n, n), dtype=np.int8)
    for i, row in enumerate(d["outcomes"]):
        for j, s in enumerate(row):
            c = CODES.setdefault(s, len(CODES) + 1)
            M[i, j] = c
    return eqs, M


def duals():
    p = os.path.join(DATA, "duals.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p))
    return d


def reach_frac(A_csr, targets_i, targets_j, rng=None, drop=0.0):
    """Fraction of (i,j) target pairs with a path i->j in A (optionally with
    each edge dropped independently with prob `drop`)."""
    A = A_csr
    if drop > 0:
        A = A_csr.copy()
        keep = rng.random(len(A.data)) >= drop
        A.data = (A.data * keep).astype(A.data.dtype)
        A.eliminate_zeros()
    n = A.shape[0]
    # group targets by source
    order = np.argsort(targets_i)
    ti, tj = targets_i[order], targets_j[order]
    ok = 0
    idx = 0
    reach_cache_src = -1
    reachable = None
    while idx < len(ti):
        src = ti[idx]
        if src != reach_cache_src:
            nodes = breadth_first_order(A, src, directed=True,
                                        return_predecessors=False)
            reachable = np.zeros(n, dtype=bool)
            reachable[nodes] = True
            reach_cache_src = src
        if reachable[tj[idx]]:
            ok += 1
        idx += 1
    return ok / max(len(ti), 1)


def main():
    t0 = time.time()
    print("loading outcomes...", flush=True)
    eqs, M = load_outcomes()
    n = len(eqs)
    inv = {v: k for k, v in CODES.items()}
    counts = {inv[c]: int((M == c).sum()) for c in inv}
    print(json.dumps(counts, indent=1), flush=True)

    exp_true = None
    imp_true = None
    for s, c in CODES.items():
        if s == "explicit_proof_true":
            exp_true = c
        if s == "implicit_proof_true":
            imp_true = c

    # ---------------- A. skeleton structure
    src, dst = np.where(M == exp_true)
    mask = src != dst
    src, dst = src[mask], dst[mask]
    A = sp.csr_matrix((np.ones(len(src), dtype=np.int8), (src, dst)),
                      shape=(n, n))
    A.sum_duplicates()
    A.sort_indices()
    A.data = np.minimum(A.data, 1).astype(np.int8)
    print(f"skeleton: {n} equations, {A.nnz} direct proved implications",
          flush=True)

    out_deg = np.asarray(A.sum(1)).ravel()
    in_deg = np.asarray(A.sum(0)).ravel()
    ncc, labels = connected_components(A, directed=True, connection="strong")
    from collections import Counter
    scc_sizes = Counter(labels.tolist())
    top_scc = scc_sizes.most_common(5)

    stats = dict(
        n_equations=n, n_direct=int(A.nnz),
        out_deg_mean=float(out_deg.mean()), out_deg_max=int(out_deg.max()),
        in_deg_mean=float(in_deg.mean()), in_deg_max=int(in_deg.max()),
        n_scc=int(ncc), top_scc_sizes=[int(c) for _, c in top_scc],
        outcome_counts=counts,
    )

    try:
        import powerlaw
        fit_o = powerlaw.Fit(out_deg[out_deg > 0], discrete=True, verbose=False)
        fit_i = powerlaw.Fit(in_deg[in_deg > 0], discrete=True, verbose=False)
        stats["alpha_out"] = round(float(fit_o.alpha), 3)
        stats["alpha_out_xmin"] = int(fit_o.xmin)
        stats["alpha_in"] = round(float(fit_i.alpha), 3)
        stats["alpha_in_xmin"] = int(fit_i.xmin)
    except Exception as e:
        print("powerlaw fit failed:", e)

    # ---------------- B. percolation of derivability
    # target pairs: a sample of implicit_true pairs
    rng = np.random.default_rng(0)
    ti, tj = np.where(M == imp_true)
    mask = ti != tj
    ti, tj = ti[mask], tj[mask]
    print(f"implicit_true pairs: {len(ti)}", flush=True)
    samp = rng.choice(len(ti), size=min(20000, len(ti)), replace=False)
    si, sj = ti[samp], tj[samp]

    base = reach_frac(A, si, sj)
    print(f"baseline derivability of sampled implicit pairs via skeleton: "
          f"{base:.4f} ({time.time()-t0:.0f}s)", flush=True)

    perc = []
    for eps in [0.001, 0.003, 0.01, 0.03, 0.1, 0.2, 0.3, 0.5]:
        vals = []
        for trial in range(10):
            vals.append(reach_frac(A, si, sj, rng=rng, drop=eps))
        perc.append(dict(eps=eps, mean=float(np.mean(vals)),
                         sd=float(np.std(vals))))
        print(f"eps={eps}: survive={np.mean(vals):.4f}±{np.std(vals):.4f}",
              flush=True)
    stats["percolation"] = perc
    stats["baseline_derivable"] = base

    # chain-length expectation: shortest path lengths for the sample
    from scipy.sparse.csgraph import dijkstra
    # sample 2000 pairs for path stats
    s2 = rng.choice(len(si), size=min(2000, len(si)), replace=False)
    uniq_src = np.unique(si[s2])
    spl = {}
    D = dijkstra(A, directed=True, indices=uniq_src, unweighted=True,
                 limit=30)
    for k, u in enumerate(uniq_src):
        spl[u] = D[k]
    lens = [spl[a][b] for a, b in zip(si[s2], sj[s2]) if np.isfinite(spl[a][b])]
    stats["chain_len_mean"] = float(np.mean(lens)) if lens else None
    stats["chain_len_max"] = float(np.max(lens)) if lens else None

    # ---------------- C. edge-disjoint path redundancy (sampled)
    import networkx as nx
    G = nx.from_scipy_sparse_array(A, create_using=nx.DiGraph)
    red = []
    for a, b in zip(si[s2][:400], sj[s2][:400]):
        try:
            k = nx.edge_connectivity(G, int(a), int(b))
            red.append(k)
        except Exception:
            pass
    if red:
        red = np.array(red)
        stats["edge_disjoint_paths"] = dict(
            mean=float(red.mean()), median=float(np.median(red)),
            p90=float(np.percentile(red, 90)), max=int(red.max()),
            frac_ge2=float((red >= 2).mean()),
            frac_ge5=float((red >= 5).mean()))
        print("edge-disjoint paths:", stats["edge_disjoint_paths"], flush=True)

    with open(os.path.join(OUT, "etp_stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(f"done in {time.time()-t0:.0f}s -> {OUT}/etp_stats.json", flush=True)


if __name__ == "__main__":
    main()
