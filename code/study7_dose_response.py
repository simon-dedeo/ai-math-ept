"""
study7_dose_response.py — The automation dose-response law (hypothesis N1),
tested inside a single human library at 300k-declaration scale.

Claim to test: the more a proof delegates to powerful automation, the more it
"repeats rather than reuses" — it cites fewer named premises, and its results
are themselves less reused — reproducing, within human mathematics, the
structural signature we measure in AI-generated proofs.

Data (no Lean runs needed):
  tactic_usage.ndjson  : per declaration, the tactics actually used
  mathlib_edges.csv    : dependency edges (source USES target), is_explicit
  nodes.csv            : kind, module

Automation score per theorem = share of its tactic invocations that are
"closers" (decide/norm_num/omega/aesop/linarith/nlinarith/positivity/
polyrith/field_simp/ring/simp/tauto/bound/...) rather than structural steps
(exact/apply/refine/intro/rw/induction/cases/constructor/...).

Outcomes per theorem:
  premises_explicit : # distinct source-visible premises it cites
  premises_all      : # distinct dependencies after elaboration
  reuse             : # later declarations that cite it
  hidden_share      : 1 - explicit/all  (how much of its support is invisible
                      to a human reader — the "tracking" gap)

Also: belief dynamics on the automation-heavy vs automation-light subgraphs.

Output: results/study7/
"""
import json, os, time
import numpy as np
import pandas as pd

ROOT = os.path.expanduser("~/ai_math_ept")
MG = f"{ROOT}/projects/mathlib_graph"
OUT = f"{ROOT}/results/study7"
os.makedirs(OUT, exist_ok=True)
t0 = time.time()

CLOSERS = {
    "decide", "norm_num", "omega", "aesop", "linarith", "nlinarith", "positivity",
    "polyrith", "field_simp", "ring", "ring_nf", "simp", "simpa", "simp_all",
    "tauto", "bound", "gcongr", "measurability", "continuity", "fun_prop",
    "norm_cast", "push_cast", "trivial", "native_decide", "linear_combination",
    "simp_rw", "dsimp", "norm_fin", "decide!", "abel", "group", "module",
    "assumption", "contradiction", "rfl", "omega!", "finiteness", "arith",
}
STRUCTURAL = {
    "exact", "apply", "refine", "intro", "intros", "rw", "rwa", "induction",
    "cases", "rcases", "obtain", "constructor", "use", "have", "calc",
    "conv", "unfold", "specialize", "subst", "by_cases", "ext", "funext",
    "convert", "exact_mod_cast", "change", "show", "rintro", "let", "set",
    "interval_cases", "rcases", "obtain", "exists", "left", "right", "cases'",
    "injection", "symm", "trans", "nth_rewrite", "conv_lhs", "conv_rhs",
}

print("loading tactic usage...", flush=True)
recs = []
with open(f"{MG}/tactic_usage.ndjson") as f:
    for line in f:
        r = json.loads(line)
        if r.get("kind") != "theorem" or not r.get("is_tactic_proof"):
            continue
        tacs = r.get("tactics") or []
        if not tacs:
            continue
        cl = sum(1 for t in tacs if t in CLOSERS)
        st = sum(1 for t in tacs if t in STRUCTURAL)
        if cl + st == 0:
            continue
        recs.append((r["name"], r.get("module", ""), len(tacs), cl, st,
                     cl / (cl + st)))
T = pd.DataFrame(recs, columns=["name", "module", "n_tactics", "n_closer",
                                "n_struct", "automation"])
print(f"{len(T)} tactic-proved theorems ({time.time()-t0:.0f}s)", flush=True)

print("loading edges...", flush=True)
E = pd.read_csv(f"{MG}/mathlib_edges.csv")
print(f"{len(E)} edges ({time.time()-t0:.0f}s)", flush=True)

prem_all = E.groupby("source").size().rename("premises_all")
prem_exp = E[E["is_explicit"] == True].groupby("source").size().rename("premises_explicit")  # noqa
reuse = E.groupby("target").size().rename("reuse")

T = (T.set_index("name")
       .join(prem_all).join(prem_exp).join(reuse)
       .fillna({"premises_all": 0, "premises_explicit": 0, "reuse": 0}))
T["hidden_share"] = 1 - T["premises_explicit"] / T["premises_all"].clip(lower=1)
T = T[T["premises_all"] > 0]
print(f"{len(T)} theorems joined to graph ({time.time()-t0:.0f}s)", flush=True)

# ---- dose-response: bin by automation score
T["bin"] = pd.cut(T["automation"], [-0.001, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0],
                  labels=["0-10%", "10-25%", "25-50%", "50-75%", "75-90%", "90-100%"])
tab = T.groupby("bin", observed=True).agg(
    n=("reuse", "size"),
    automation=("automation", "mean"),
    premises_explicit=("premises_explicit", "median"),
    premises_all=("premises_all", "median"),
    hidden_share=("hidden_share", "mean"),
    reuse_mean=("reuse", "mean"),
    reuse_median=("reuse", "median"),
    frac_never_reused=("reuse", lambda x: (x == 0).mean()),
    n_tactics=("n_tactics", "median"),
).round(3)
print("\n=== dose-response: automation share -> structure ===")
print(tab.to_string())
tab.to_csv(f"{OUT}/dose_response.csv")

from scipy import stats
res = {}
for y in ["premises_explicit", "reuse", "hidden_share"]:
    rho, p = stats.spearmanr(T["automation"], T[y])
    res[f"spearman_automation_vs_{y}"] = dict(rho=float(rho), p=float(p))
    print(f"spearman(automation, {y}) = {rho:.4f}  p={p:.3g}")

# size control: partial out proof size (n_tactics)
T["logsize"] = np.log1p(T["n_tactics"])
for y in ["premises_explicit", "reuse"]:
    import numpy.linalg as la
    X = np.column_stack([np.ones(len(T)), T["automation"], T["logsize"]])
    yv = np.log1p(T[y].to_numpy(dtype=float))
    beta, *_ = la.lstsq(X, yv, rcond=None)
    res[f"ols_log1p_{y}"] = dict(intercept=float(beta[0]),
                                 beta_automation=float(beta[1]),
                                 beta_logsize=float(beta[2]))
    print(f"OLS log1p({y}) ~ automation + log(size): "
          f"beta_automation={beta[1]:.4f} (size-controlled)")

# ---- EPT on automation-heavy vs automation-light subgraphs
import sys
sys.path.insert(0, f"{ROOT}/code")
from belief import _beliefs, beta_of_eps

names = pd.unique(pd.concat([E["source"], E["target"]]))
idx = {nm: i for i, nm in enumerate(names)}
N = len(names)
auto = T["automation"].to_dict()


def sub_belief(mask_names, tag):
    keep = set(mask_names)
    sub = E[E["source"].isin(keep) & E["target"].isin(keep)]
    if len(sub) < 1000:
        return None
    ln = pd.unique(pd.concat([sub["source"], sub["target"]]))
    li = {nm: i for i, nm in enumerate(ln)}
    s = sub["source"].map(li).to_numpy(np.int64)
    d = sub["target"].map(li).to_numpy(np.int64)
    n_ = len(ln)
    pre_ptr = np.zeros(n_ + 1, np.int64); np.add.at(pre_ptr, s + 1, 1)
    pre_ptr = np.cumsum(pre_ptr); pre_idx = d[np.argsort(s, kind="stable")]
    dep_ptr = np.zeros(n_ + 1, np.int64); np.add.at(dep_ptr, d + 1, 1)
    dep_ptr = np.cumsum(dep_ptr); dep_idx = s[np.argsort(d, kind="stable")]
    out = {}
    for eps in [0.1, 0.05, 0.01]:
        b = _beliefs(pre_ptr, pre_idx, dep_ptr, dep_idx,
                     beta_of_eps(eps), beta_of_eps(eps), 0.75, 10, 3, 7)
        out[eps] = float(b.mean())
    print(f"[{tag}] n={n_} edges={len(sub)} belief: " +
          ", ".join(f"eps={k}:{v:.4f}" for k, v in out.items()), flush=True)
    return dict(n_nodes=int(n_), n_edges=int(len(sub)), belief=out)


hi = T[T["automation"] >= 0.75].index.tolist()
lo = T[T["automation"] <= 0.10].index.tolist()
res["subgraph_automation_high"] = sub_belief(hi, "automation>=75%")
res["subgraph_automation_low"] = sub_belief(lo, "automation<=10%")

json.dump(res, open(f"{OUT}/dose_response.json", "w"), indent=1)
T.reset_index().to_csv(f"{OUT}/theorems.csv.gz", index=False, compression="gzip")
print(f"done {time.time()-t0:.0f}s", flush=True)
