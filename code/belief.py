"""
belief.py — Asymmetric-Ising belief dynamics on proof networks
(Viteri & DeDeo 2022, Eq. 1 and the MH/Glauber heuristic described in
Sec. 1.2 and Appendix Sec. 2).

Spins s in {-1,+1} ("false","true"). For node q:
    weighted alignment field  h_q = b_dep * sum_{u premise of q} s_u
                                  + b_imp * sum_{v dependent of q} s_v
    D_q = s_q * h_q   (weighted agreements minus disagreements)
Update rule (paper's MH): if flipping aligns q with the weighted majority
(D_q < 0) flip deterministically; otherwise flip with
P = exp(-2 D_q) / (1 + exp(-2 D_q)).   (At D=0, P=1/2.)

Error rate <-> coupling:  eps = 1 / (1 + e^{2 beta}),  beta = 0.5*ln((1-eps)/eps).
Initialization: each node true with prob p_prior (default 0.75).
Run length: sweeps * N single-node updates (default 10 sweeps as in paper).
Belief of node = average over R runs of the time-average of (s+1)/2 over the
second half of each run.
"""

from __future__ import annotations
import numpy as np

try:
    from numba import njit, prange
    HAVE_NUMBA = True
except ImportError:  # pragma: no cover
    HAVE_NUMBA = False
    def njit(*a, **k):
        def wrap(f):
            return f
        return wrap if not (len(a) == 1 and callable(a[0])) else a[0]
    prange = range


def beta_of_eps(eps):
    return 0.5 * np.log((1.0 - eps) / eps)


def eps_of_confidence(c):
    return 1.0 - c


@njit(cache=True)
def _run_chain(pre_ptr, pre_idx, dep_ptr, dep_idx, b_dep, b_imp,
               p_prior, sweeps, seed):
    n = pre_ptr.shape[0] - 1
    np.random.seed(seed)
    s = np.empty(n, dtype=np.int8)
    for i in range(n):
        s[i] = 1 if np.random.random() < p_prior else -1
    total = sweeps * n
    half = total // 2
    acc = np.zeros(n, dtype=np.float64)
    cnt = 0
    for step in range(total):
        q = np.random.randint(0, n)
        h = 0.0
        for k in range(pre_ptr[q], pre_ptr[q + 1]):
            h += b_dep * s[pre_idx[k]]
        for k in range(dep_ptr[q], dep_ptr[q + 1]):
            h += b_imp * s[dep_idx[k]]
        D = s[q] * h
        if D < 0.0:
            s[q] = -s[q]
        else:
            p = np.exp(-2.0 * D) / (1.0 + np.exp(-2.0 * D))
            if np.random.random() < p:
                s[q] = -s[q]
        if step >= half:
            # accumulate every node's state each remaining step is O(n);
            # instead accumulate the flipped node lazily is complex — sample
            # states every n/4 steps for the time average.
            if (step - half) % max(1, n // 4) == 0:
                for i in range(n):
                    acc[i] += 0.5 * (s[i] + 1.0)
                cnt += 1
    if cnt == 0:
        for i in range(n):
            acc[i] = 0.5 * (s[i] + 1.0)
        cnt = 1
    return acc / cnt


@njit(parallel=True, cache=True)
def _beliefs(pre_ptr, pre_idx, dep_ptr, dep_idx, b_dep, b_imp,
             p_prior, sweeps, n_runs, seed0):
    n = pre_ptr.shape[0] - 1
    out = np.zeros(n, dtype=np.float64)
    for r in prange(n_runs):
        acc = _run_chain(pre_ptr, pre_idx, dep_ptr, dep_idx,
                         b_dep, b_imp, p_prior, sweeps, seed0 + 7919 * r)
        out += acc
    return out / n_runs


def beliefs(arrs, eps_dep, eps_imp=None, p_prior=0.75, sweeps=10,
            n_runs=20, seed=1234):
    """Per-node degree of belief. arrs from proofnet.to_arrays."""
    if eps_imp is None:
        eps_imp = eps_dep
    b_dep = beta_of_eps(eps_dep)
    b_imp = beta_of_eps(eps_imp)
    return _beliefs(arrs["pre_ptr"], arrs["pre_idx"],
                    arrs["dep_ptr"], arrs["dep_idx"],
                    b_dep, b_imp, p_prior, sweeps, n_runs, seed)


def certainty_curve(arrs, eps_grid, theorem_idx=None, p_prior=0.75,
                    sweeps=10, n_runs=20, seed=1234):
    """Fig-4a-style curves: mean belief (all nodes / theorem / axioms)
    as a function of one-step inference error rate (symmetric couplings)."""
    n = arrs["n"]
    in_deg = np.diff(arrs["pre_ptr"])
    axioms = np.where(in_deg == 0)[0]
    rows = []
    for eps in eps_grid:
        b = beliefs(arrs, eps, eps, p_prior, sweeps, n_runs, seed)
        rows.append(dict(
            eps=float(eps),
            mean_belief=float(b.mean()),
            axiom_belief=float(b[axioms].mean()) if len(axioms) else float("nan"),
            theorem_belief=float(b[theorem_idx]) if theorem_idx is not None else float("nan"),
        ))
    return rows


def f2(arrs, theorem_idx, eps=1e-2, **kw):
    """Average degree of belief in the final theorem at one-step error 1e-2."""
    b = beliefs(arrs, eps, eps, **kw)
    return float(b[theorem_idx])


def contour_grid(arrs, conf_grid, p_prior=0.75, sweeps=10, n_runs=10,
                 seed=99, target="all", theorem_idx=None):
    """Fig-5-style grid: mean belief as function of (deductive confidence,
    abductive confidence). conf_grid: 1D array of confidences (e.g.
    np.linspace in logit space from 0.75 to 0.9999)."""
    Z = np.zeros((len(conf_grid), len(conf_grid)))
    for i, c_imp in enumerate(conf_grid):       # rows: abductive
        for j, c_dep in enumerate(conf_grid):   # cols: deductive
            b = beliefs(arrs, 1 - c_dep, 1 - c_imp, p_prior, sweeps,
                        n_runs, seed + 31 * i + j)
            if target == "theorem" and theorem_idx is not None:
                Z[i, j] = b[theorem_idx]
            else:
                Z[i, j] = b.mean()
    return Z


# ------------------------------------------------------------------ firewalls

def firewall_dL1(arrs, modules, index=None, n_random=200, seed=5,
                 p_prior=0.5, sweeps=20, n_runs=8):
    """Delta-L1 (Eq. 2 of the appendix): per-node log-likelihood penalty for
    flipping an entire module vs. an equal number of random nodes, at beta=1,
    starting from the (frozen) state reached from a 0.5 prior.

    modules: list of sets of node names (or indices if index is None).
    Energy: E = -sum_{edges (u,v)} s_u s_v  (beta=1 both directions).
    dE(flip set S) = 2 * sum_{edges with exactly one endpoint in S} s_u s_v.
    Returns list of per-module dL1 values (positive => firewall: module flips
    are cheaper... sign convention: positive = within-module flip penalized
    LESS than random, matching paper's 'preference for within-module flips').
    """
    rng = np.random.default_rng(seed)
    # frozen state from 0.5 prior at beta = 1  (eps = 1/(1+e^2) ~ 0.119)
    eps_b1 = 1.0 / (1.0 + np.e ** 2)
    b = beliefs(arrs, eps_b1, eps_b1, p_prior=p_prior, sweeps=sweeps,
                n_runs=n_runs, seed=seed)
    s = np.where(b >= 0.5, 1, -1).astype(np.int8)

    n = arrs["n"]
    pre_ptr, pre_idx = arrs["pre_ptr"], arrs["pre_idx"]
    # flat edge arrays (u -> v), vectorized dE
    v_arr = np.repeat(np.arange(n), np.diff(pre_ptr))
    u_arr = pre_idx
    edge_ss = (s[u_arr] * s[v_arr]).astype(np.float64)

    def dE(flip_mask):
        cross = flip_mask[u_arr] != flip_mask[v_arr]
        return float(2.0 * edge_ss[cross].sum())

    out = []
    for M in modules:
        if index is not None:
            ids = [index[x] for x in M if x in index]
        else:
            ids = list(M)
        if not ids:
            continue
        mask = np.zeros(n, dtype=np.bool_)
        mask[ids] = True
        dE_mod = dE(mask)
        rand_vals = []
        for _ in range(n_random):
            mask_r = np.zeros(n, dtype=np.bool_)
            mask_r[rng.choice(n, size=len(ids), replace=False)] = True
            rand_vals.append(dE(mask_r))
        # positive dL1 <=> random flips cost more energy than module flips
        out.append(dict(size=len(ids),
                        dL1=float((np.mean(rand_vals) - dE_mod) / len(ids))))
    return out
