"""
proofnet.py — Proof dependency networks: construction and structural statistics.

Conventions (matching Viteri & DeDeo 2022, Cognition 225:105120):
  * Directed edge (u, v) means "v uses u": u is a premise/dependency of v.
  * out-degree(u) = number of claims that use u  (heavy-tailed, power law alpha ~ 2)
  * in-degree(v)  = number of premises v cites   (Poisson)
  * "axioms"  = nodes with in-degree 0
  * "theorem" = designated root node (the target claim), typically out-degree 0
"""

from __future__ import annotations
import json
import math
from collections import deque

import numpy as np
import networkx as nx


# ---------------------------------------------------------------- construction

def load_edgelist(path, delimiter=None):
    """Load 'premise dependent' pairs, one per line, into a DiGraph."""
    G = nx.DiGraph()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(delimiter)
            if len(parts) >= 2:
                G.add_edge(parts[0], parts[1])
    return G


def subnetwork_of(G, theorem, max_nodes=10_000):
    """Dependency network of a single theorem: all ancestors (premises,
    recursively), truncated by BFS depth as in the 2022 paper — stop at the
    first depth expansion that would exceed max_nodes (that expansion is
    included, matching 'truncated to the first depth expansion that produces
    more than 10,000 nodes')."""
    seen = {theorem}
    frontier = [theorem]
    while frontier and len(seen) <= max_nodes:
        nxt = set()
        for v in frontier:
            for u in G.predecessors(v):
                if u not in seen:
                    nxt.add(u)
        seen |= nxt
        frontier = list(nxt)
    return G.subgraph(seen).copy()


# ---------------------------------------------------------------- statistics

def powerlaw_alpha(degrees, xmin=None):
    """CSN (Clauset-Shalizi-Newman) discrete power-law fit of the tail.
    Returns (alpha, sigma, xmin, ntail). Uses the `powerlaw` package."""
    import powerlaw  # heavy import, keep local
    degrees = np.asarray([d for d in degrees if d > 0])
    if len(degrees) < 10:
        return (float("nan"),) * 2 + (xmin or 1, len(degrees))
    fit = powerlaw.Fit(degrees, discrete=True, xmin=xmin, verbose=False)
    return fit.alpha, fit.sigma, fit.xmin, int((degrees >= fit.xmin).sum())


def girvan_newman_modules(G, max_nodes_exact=800):
    """Community structure on the undirected projection.
    Girvan–Newman (as in the paper) for small graphs; Louvain otherwise."""
    U = G.to_undirected()
    U.remove_nodes_from(list(nx.isolates(U)))
    if U.number_of_nodes() == 0:
        return []
    if U.number_of_nodes() <= max_nodes_exact:
        from networkx.algorithms.community import girvan_newman
        from networkx.algorithms.community.quality import modularity
        best, best_q = None, -1
        gen = girvan_newman(U)
        for _ in range(30):  # scan first 30 splits, keep best modularity
            try:
                comms = next(gen)
            except StopIteration:
                break
            q = modularity(U, comms)
            if q > best_q:
                best, best_q = [set(c) for c in comms], q
        return best or [set(U.nodes())]
    else:
        from networkx.algorithms.community import louvain_communities
        return [set(c) for c in louvain_communities(U, seed=0)]


def structural_stats(G, name="", fit_powerlaw=True):
    """The Table-1-style summary for one proof network."""
    n, m = G.number_of_nodes(), G.number_of_edges()
    out_deg = np.array([d for _, d in G.out_degree()])
    in_deg = np.array([d for _, d in G.in_degree()])
    stats = {
        "name": name,
        "nodes": n,
        "edges": m,
        "mean_in_degree": float(in_deg.mean()) if n else 0.0,
        "max_out_degree": int(out_deg.max()) if n else 0,
        "frac_axioms": float((in_deg == 0).mean()) if n else 0.0,
        "out_gini": gini(out_deg),
        "depth": dag_depth(G),
    }
    if fit_powerlaw and n >= 50:
        alpha, sigma, xmin, ntail = powerlaw_alpha(out_deg)
        stats.update(alpha=round(float(alpha), 3), alpha_err=round(float(sigma), 3),
                     xmin=int(xmin), ntail=ntail)
    comms = girvan_newman_modules(G)
    if comms:
        U = G.to_undirected()
        U.remove_nodes_from(list(nx.isolates(U)))
        from networkx.algorithms.community.quality import modularity
        try:
            stats["modularity"] = round(float(modularity(U, comms)), 3)
        except Exception:
            stats["modularity"] = None
        stats["n_modules"] = len(comms)
    return stats, comms


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    if len(x) == 0 or x.sum() == 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(x) / (n * x.sum()))


def dag_depth(G):
    """Longest path length (levels of the DAG); robust to small cycles."""
    try:
        order = list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        G = nx.DiGraph((u, v) for u, v in G.edges() if u != v)
        try:
            order = list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            return -1
    depth = {v: 0 for v in order}
    for v in order:
        for w in G.successors(v):
            depth[w] = max(depth[w], depth[v] + 1)
    return max(depth.values()) if depth else 0


def to_arrays(G):
    """Index the graph for the numba simulator. Returns dict with CSR-style
    arrays: for each node, its premises (in-neighbors) and dependents
    (out-neighbors)."""
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)
    pre_ptr = np.zeros(n + 1, dtype=np.int64)
    dep_ptr = np.zeros(n + 1, dtype=np.int64)
    for v in nodes:
        pre_ptr[idx[v] + 1] = G.in_degree(v)
        dep_ptr[idx[v] + 1] = G.out_degree(v)
    pre_ptr, dep_ptr = np.cumsum(pre_ptr), np.cumsum(dep_ptr)
    pre_idx = np.empty(pre_ptr[-1], dtype=np.int64)
    dep_idx = np.empty(dep_ptr[-1], dtype=np.int64)
    pc, dc = pre_ptr[:-1].copy(), dep_ptr[:-1].copy()
    for u, v in G.edges():
        iu, iv = idx[u], idx[v]
        pre_idx[pc[iv]] = iu; pc[iv] += 1
        dep_idx[dc[iu]] = iv; dc[iu] += 1
    return dict(nodes=nodes, index=idx, n=n,
                pre_ptr=pre_ptr, pre_idx=pre_idx,
                dep_ptr=dep_ptr, dep_idx=dep_idx)
