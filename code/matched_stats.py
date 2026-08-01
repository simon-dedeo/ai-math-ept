"""
matched_stats.py — corrected statistics for matched-theorem designs.

Fixes two errors found in review of the first implementation:

  BUG 1 (rank scope). The original ranked systems across *all* systems present
  for a problem and only afterwards restricted to the complete block, so a
  system's mean rank could exceed the block width (we reported 8.57 in a
  7-system block). Here the complete block is selected FIRST, on raw values,
  and ranks are computed inside it.

  BUG 2 (variance decomposition). The original reported ss_problem/ss_total and
  ss_system/ss_total from separate one-way groupings. Those are overlapping
  marginal sums of squares in an unbalanced crossed design; they summed to 106%.
  Here we report unique (Type-II-style) contributions from nested OLS fits plus
  the shared part, and a permutation test for the system effect that makes no
  balance assumption.

Everything reports uncertainty: Friedman/Kendall W come with a permutation null,
and variance components come with a cluster bootstrap over problems.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def complete_block(pm, metric, index="problem", columns="system",
                   min_problems=5, max_systems=10):
    """Largest complete (no-missing) problems x systems block, chosen on raw
    values. Returns the raw-value block, NOT ranks."""
    piv = pm.pivot_table(index=index, columns=columns, values=metric,
                         aggfunc="median")
    order = piv.notna().sum().sort_values(ascending=False).index
    best, best_size = None, 0
    # Friedman needs >= 3 systems; require it here so callers get a valid block
    for k in range(3, min(max_systems, len(order)) + 1):
        blk = piv[list(order[:k])].dropna()
        if len(blk) >= min_problems and len(blk) * k > best_size:
            best, best_size = blk, len(blk) * k
    return best


def friedman_block(block, n_perm=2000, seed=0):
    """Friedman + Kendall's W on a complete block, with a permutation null.

    Ranks are computed WITHIN the block (bug 1 fix), so mean ranks are
    guaranteed to lie in [1, k].
    """
    ranks = block.rank(axis=1)            # rank within the block only
    arr = ranks.to_numpy()
    n, k = arr.shape
    fr = stats.friedmanchisquare(*[arr[:, j] for j in range(k)])
    W = fr.statistic / (n * (k - 1))

    # permutation null: shuffle system labels independently within each problem
    rng = np.random.default_rng(seed)
    raw = block.to_numpy()
    null_W = np.empty(n_perm)
    for b in range(n_perm):
        perm = np.apply_along_axis(rng.permutation, 1, raw)
        pr = pd.DataFrame(perm).rank(axis=1).to_numpy()
        st = stats.friedmanchisquare(*[pr[:, j] for j in range(k)]).statistic
        null_W[b] = st / (n * (k - 1))
    p_perm = float((null_W >= W).mean())

    mean_ranks = ranks.mean().sort_values()
    assert mean_ranks.min() >= 1 - 1e-9 and mean_ranks.max() <= k + 1e-9, \
        "mean ranks outside [1, k] — block/rank scope error"
    return dict(n_problems=int(n), n_systems=int(k),
                friedman_chi2=float(fr.statistic), friedman_p=float(fr.pvalue),
                kendall_W=float(W), kendall_W_perm_p=p_perm,
                null_W_mean=float(null_W.mean()),
                null_W_p95=float(np.percentile(null_W, 95)),
                mean_ranks={str(a): float(v) for a, v in mean_ranks.items()})


def _r2(df, y, factors):
    """R^2 of an OLS fit of y on the given categorical factors (dummy coded)."""
    if not factors:
        return 0.0
    X = pd.get_dummies(df[factors].astype(str), drop_first=True).to_numpy(float)
    X = np.column_stack([np.ones(len(df)), X])
    yv = df[y].to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid = yv - X @ beta
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((yv - yv.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


def variance_components(pm, metric, problem="problem", system="system",
                        n_boot=400, seed=0):
    """Unique and shared variance for an unbalanced crossed design.

    Reports R^2 increments (Type-II-style), which — unlike the marginal sums of
    squares used previously — are interpretable and do not exceed 100% in total.
    Uncertainty is a cluster bootstrap resampling PROBLEMS (the clustering unit).
    """
    d = pm.dropna(subset=[metric, problem, system]).copy()
    r2_both = _r2(d, metric, [problem, system])
    r2_prob = _r2(d, metric, [problem])
    r2_sys = _r2(d, metric, [system])
    uniq_sys = r2_both - r2_prob
    uniq_prob = r2_both - r2_sys
    shared = r2_both - uniq_sys - uniq_prob

    rng = np.random.default_rng(seed)
    probs = d[problem].unique()
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(probs, size=len(probs), replace=True)
        b = pd.concat([d[d[problem] == p] for p in pick], ignore_index=True)
        # relabel resampled problems so repeats are distinct clusters
        b["_p"] = b.groupby(problem).cumcount().astype(str) + "_" + b[problem].astype(str)
        try:
            rb = _r2(b, metric, ["_p", system])
            rp = _r2(b, metric, ["_p"])
            rs = _r2(b, metric, [system])
            boots.append((rb - rp, rb - rs))
        except Exception:
            continue
    boots = np.array(boots) if boots else np.zeros((1, 2))
    lo_s, hi_s = np.percentile(boots[:, 0], [2.5, 97.5])
    lo_p, hi_p = np.percentile(boots[:, 1], [2.5, 97.5])

    # permutation test for the system effect: shuffle system labels within problem
    obs = uniq_sys
    null = []
    for _ in range(300):
        b = d.copy()
        b[system] = b.groupby(problem)[system].transform(
            lambda s: rng.permutation(s.to_numpy()))
        null.append(_r2(b, metric, [problem, system]) - r2_prob)
    p_sys = float((np.array(null) >= obs).mean())

    return dict(
        n_cells=int(len(d)), n_problems=int(d[problem].nunique()),
        n_systems=int(d[system].nunique()),
        r2_problem_only=r2_prob, r2_system_only=r2_sys, r2_both=r2_both,
        unique_problem=uniq_prob, unique_problem_ci=[float(lo_p), float(hi_p)],
        unique_system=uniq_sys, unique_system_ci=[float(lo_s), float(hi_s)],
        shared=shared, system_perm_p=p_sys)


def tost_paired(x, y, bound_frac=0.1, n_boot=2000, seed=0):
    """Equivalence test for a paired comparison (two one-sided tests).

    A non-significant Wilcoxon is NOT evidence of equivalence. This asks whether
    the paired difference lies within +/- bound_frac * median(x), and returns a
    cluster-free bootstrap CI on the median difference.
    """
    x = np.asarray(x, float); y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    d = y - x
    bound = bound_frac * float(np.median(x)) if np.median(x) else bound_frac
    rng = np.random.default_rng(seed)
    meds = np.array([np.median(rng.choice(d, len(d), replace=True))
                     for _ in range(n_boot)])
    lo, hi = np.percentile(meds, [2.5, 97.5])
    equivalent = bool(lo > -bound and hi < bound)
    try:
        w_p = float(stats.wilcoxon(x, y).pvalue)
    except Exception:
        w_p = float("nan")
    return dict(n=int(len(d)), median_x=float(np.median(x)),
                median_y=float(np.median(y)),
                median_diff=float(np.median(d)), ci_low=float(lo),
                ci_high=float(hi), equiv_bound=float(bound),
                equivalent_within_bound=equivalent, wilcoxon_p=w_p)


def cluster_bootstrap_paired(df, xcol, ycol, cluster, n_boot=2000, seed=0):
    """Median paired difference with a bootstrap that resamples CLUSTERS, so
    non-independence between pairs from the same source is respected."""
    rng = np.random.default_rng(seed)
    d = df.dropna(subset=[xcol, ycol, cluster])
    groups = [g for _, g in d.groupby(cluster)]
    meds = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(groups), len(groups))
        s = pd.concat([groups[i] for i in pick], ignore_index=True)
        meds.append(float(np.median(s[ycol].to_numpy(float)
                                    - s[xcol].to_numpy(float))))
    meds = np.array(meds)
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return dict(n_pairs=int(len(d)), n_clusters=int(d[cluster].nunique()),
                median_diff=float(np.median(d[ycol] - d[xcol])),
                ci_low=float(lo), ci_high=float(hi))
