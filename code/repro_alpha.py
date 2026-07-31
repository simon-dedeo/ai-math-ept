"""
repro_alpha.py — Can the published Table 1 alpha values be reproduced?

We have the paper's own 49 ProofDAGs and 47 of them match a published row by
exact node count. The remaining question is purely one of estimator convention:
which way of fitting the out-degree tail reproduces the published numbers?

We sweep the plausible conventions and report, for each, the correlation with
and mean absolute deviation from the published alphas.
"""
import glob, json, os, re, sys, warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

ROOT = os.path.expanduser("~/ai_math_ept")
sys.path.insert(0, f"{ROOT}/code")
import powerlaw

ref = pd.read_csv(f"{ROOT}/code/reference_2022.csv")
ref = ref[ref.group == "coq2022"].copy()
by_nodes = dict(zip(ref.nodes.astype(int), zip(ref.name, ref.alpha)))


def load_graph_degrees(path):
    g = json.load(open(path))
    # key -> children (children are the constituent premises of key)
    out_deg = {k: 0 for k in g}          # how many nodes use k
    in_deg = {k: len(v) for k, v in g.items()}
    for k, ch in g.items():
        for c in ch:
            if c in out_deg:
                out_deg[c] += 1
            else:
                out_deg[c] = 1
                in_deg.setdefault(c, 0)
    return (np.array(list(out_deg.values())), np.array(list(in_deg.values())),
            len(out_deg))


def pick_depth(d):
    """paper rule: first depth expansion exceeding 10,000 nodes, else deepest"""
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
        chosen = files[k]
        if len(g) > 10000:
            break
    return chosen


def fit(deg, mode):
    d = deg[deg > 0]
    if len(d) < 10:
        return np.nan
    if mode == "csn_auto":
        return powerlaw.Fit(d, discrete=True, verbose=False).alpha
    if mode.startswith("xmin"):
        xm = int(mode[4:])
        return powerlaw.Fit(d, discrete=True, xmin=xm, verbose=False).alpha
    if mode == "csn_cont":
        return powerlaw.Fit(d, discrete=False, verbose=False).alpha
    if mode == "loglog":          # naive log-log regression on the pdf
        vals, cnts = np.unique(d, return_counts=True)
        p = cnts / cnts.sum()
        m = vals >= 1
        A = np.vstack([np.log(vals[m]), np.ones(m.sum())]).T
        slope, _ = np.linalg.lstsq(A, np.log(p[m]), rcond=None)[0]
        return -slope
    if mode == "ccdf":            # Hill on the ccdf tail xmin=1
        return 1 + len(d) / np.sum(np.log(d / (np.min(d) - 0.5)))
    raise ValueError(mode)


MODES = ["csn_auto", "xmin1", "xmin2", "xmin3", "xmin5", "csn_cont",
         "loglog", "ccdf"]
rows = []
for d in sorted(glob.glob(f"{ROOT}/original_data/ManipulateProofTrees/ProofDAGs/*/")):
    p = pick_depth(d)
    if not p:
        continue
    outd, ind, n = load_graph_degrees(p)
    if n not in by_nodes:
        continue
    pub_name, pub_alpha = by_nodes[n]
    r = dict(dir=os.path.basename(d.rstrip("/")), published=pub_name,
             nodes=n, alpha_pub=pub_alpha)
    for m in MODES:
        try:
            r[f"out_{m}"] = round(float(fit(outd, m)), 3)
        except Exception:
            r[f"out_{m}"] = np.nan
    try:
        r["in_csn_auto"] = round(float(fit(ind, "csn_auto")), 3)
    except Exception:
        r["in_csn_auto"] = np.nan
    rows.append(r)

df = pd.DataFrame(rows)
print(f"matched {len(df)} networks to published rows\n")
print("convention           corr(pub)   mean|diff|   mean alpha   published mean")
best = None
for m in MODES + ["in_csn_auto"]:
    col = f"out_{m}" if m != "in_csn_auto" else m
    if col not in df:
        continue
    ok = df[col].notna() & df["alpha_pub"].notna()
    if ok.sum() < 10:
        continue
    r = np.corrcoef(df.loc[ok, col], df.loc[ok, "alpha_pub"])[0, 1]
    md = np.mean(np.abs(df.loc[ok, col] - df.loc[ok, "alpha_pub"]))
    print(f"{col:20s} {r:8.3f}   {md:9.3f}   {df.loc[ok,col].mean():10.3f}   "
          f"{df.loc[ok,'alpha_pub'].mean():.3f}")
    if best is None or (r > best[1]):
        best = (col, r, md)
print(f"\nbest by correlation: {best}")
df.to_csv(f"{ROOT}/results/repro_alpha.csv", index=False)
print(f"\nwrote {ROOT}/results/repro_alpha.csv")
print(df[["published", "nodes", "alpha_pub", "out_csn_auto", "out_xmin1",
          "out_xmin2", "out_loglog"]].head(20).to_string(index=False))
