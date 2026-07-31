"""
repro_xmin.py — Is the alpha discrepancy just an x_min convention?

For every x_min from 1..25 we refit all 47 matched networks with an explicit
discrete MLE (no library, so nothing can fail silently) and ask which x_min, if
any, reproduces the published Table 1 alphas — in LEVEL (mean absolute
difference) and in RANKING (correlation across theorems).

Estimators:
  hill_disc : discrete MLE, alpha = 1 + n / sum(ln(x/(xmin-0.5)))     [CSN eq 3.7]
  hill_cont : continuous MLE, alpha = 1 + n / sum(ln(x/xmin))
  mle_exact : numerical MLE of the discrete power law using the Hurwitz zeta
"""
import glob, json, os, re, sys, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import zeta
warnings.filterwarnings("ignore")

ROOT = os.path.expanduser("~/ai_math_ept")
ref = pd.read_csv(f"{ROOT}/code/reference_2022.csv")
ref = ref[ref.group == "coq2022"]
by_nodes = dict(zip(ref.nodes.astype(int), zip(ref.name, ref.alpha)))


def pick_depth(d):
    files = {}
    for p in glob.glob(f"{d}/d*.txt"):
        m = re.match(r"d(\d+)\.txt$", os.path.basename(p))
        if m:
            files[int(m.group(1))] = p
    chosen = None
    for k in sorted(files):
        try:
            g = json.load(open(files[k]))
        except Exception:
            continue
        chosen = g
        if len(g) > 10000:
            break
    return chosen


def out_degrees(g):
    out = {k: 0 for k in g}
    for k, ch in g.items():
        for c in ch:
            out[c] = out.get(c, 0) + 1
    return np.array(list(out.values()))


def hill_disc(x, xmin):
    x = x[x >= xmin]
    if len(x) < 10:
        return np.nan
    return 1.0 + len(x) / np.sum(np.log(x / (xmin - 0.5)))


def hill_cont(x, xmin):
    x = x[x >= xmin]
    if len(x) < 10:
        return np.nan
    return 1.0 + len(x) / np.sum(np.log(x / xmin))


def mle_exact(x, xmin):
    x = x[x >= xmin].astype(float)
    if len(x) < 10:
        return np.nan
    s = np.sum(np.log(x))
    n = len(x)

    def nll(a):
        if a <= 1.01:
            return 1e12
        return n * np.log(zeta(a, xmin)) + a * s

    r = minimize_scalar(nll, bounds=(1.02, 6.0), method="bounded")
    return float(r.x)


rows = []
for d in sorted(glob.glob(f"{ROOT}/original_data/ManipulateProofTrees/ProofDAGs/*/")):
    g = pick_depth(d)
    if not g:
        continue
    n = len(set(list(g.keys()) + [c for v in g.values() for c in v]))
    if n not in by_nodes:
        continue
    pub_name, pub_alpha = by_nodes[n]
    od = out_degrees(g)
    rows.append(dict(name=pub_name, nodes=n, alpha_pub=pub_alpha,
                     deg=od))

print(f"matched {len(rows)} networks\n")
print("  xmin |  hill_disc: corr  mean|d|  mean |  mle_exact: corr  mean|d|  mean"
      "  | n_tail")
print("  " + "-" * 82)
best = []
for xmin in range(1, 26):
    hd = np.array([hill_disc(r["deg"], xmin) for r in rows])
    me = np.array([mle_exact(r["deg"], xmin) for r in rows])
    pub = np.array([r["alpha_pub"] for r in rows])
    tail = np.mean([np.sum(r["deg"] >= xmin) for r in rows])
    ok = ~np.isnan(hd) & ~np.isnan(pub)
    ok2 = ~np.isnan(me) & ~np.isnan(pub)
    if ok.sum() < 10:
        continue
    c1 = np.corrcoef(hd[ok], pub[ok])[0, 1]
    d1 = np.mean(np.abs(hd[ok] - pub[ok]))
    c2 = np.corrcoef(me[ok2], pub[ok2])[0, 1] if ok2.sum() > 10 else np.nan
    d2 = np.mean(np.abs(me[ok2] - pub[ok2])) if ok2.sum() > 10 else np.nan
    print(f"  {xmin:4d} |      {c1:7.3f}  {d1:7.3f}  {hd[ok].mean():5.2f} |"
          f"       {c2:7.3f}  {d2:7.3f}  {me[ok2].mean():5.2f}  | {tail:7.0f}")
    best.append((d1, xmin, "hill_disc", c1))
    if not np.isnan(d2):
        best.append((d2, xmin, "mle_exact", c2))

best.sort()
print(f"\npublished mean alpha = {np.mean([r['alpha_pub'] for r in rows]):.3f}")
print("closest in LEVEL:", best[:3])
bycorr = sorted(best, key=lambda t: -t[3])
print("closest in RANK :", bycorr[:3])

# Save the per-theorem table at the best-level xmin for inspection
d_, xm_, est_, c_ = best[0]
f = hill_disc if est_ == "hill_disc" else mle_exact
tab = pd.DataFrame([dict(name=r["name"], nodes=r["nodes"],
                         alpha_pub=r["alpha_pub"],
                         alpha_fit=round(float(f(r["deg"], xm_)), 3))
                    for r in rows])
tab["diff"] = (tab.alpha_fit - tab.alpha_pub).round(3)
tab.to_csv(f"{ROOT}/results/repro_xmin_best.csv", index=False)
print(f"\nbest-level fit ({est_}, xmin={xm_}): per-theorem table ->"
      f" results/repro_xmin_best.csv")
print(tab.sort_values("nodes", ascending=False).head(15).to_string(index=False))
