"""
repro_validate.py — Is the heavy-tailed-reuse claim real, and is alpha a
discriminating statistic?

Three checks on the paper's own 49 ProofDAGs:

 (1) MODEL COMPARISON. For each network's out-degree, compare a power law
     against exponential, lognormal and stretched-exponential alternatives
     (Clauset-Shalizi-Newman likelihood ratios). If the power law is not
     favoured, "alpha ~ 2" is a fitted number without a fitted model.

 (2) DISCRIMINATION. Fit the same estimator to (a) the out-degree, which the
     paper says is heavy-tailed, and (b) the in-degree, which the paper says is
     Poisson, and (c) a size- and density-matched random DAG. If the estimator
     returns ~2.2 for all three, alpha is uninformative and the clustering of
     published values near 2 tells us about the estimator, not about proofs.

 (3) The claim that actually matters for the EPT: heavy-tailed reuse should
     produce MANY INDEPENDENT PATHS between claims. Measure that directly
     (sampled edge-disjoint path counts) on real vs. random-DAG controls, which
     is estimator-free.
"""
import glob, json, os, re, sys, warnings
import numpy as np
import pandas as pd
import networkx as nx
warnings.filterwarnings("ignore")

ROOT = os.path.expanduser("~/ai_math_ept")
import powerlaw

rng = np.random.default_rng(0)


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


def to_graph(g):
    G = nx.DiGraph()
    for k, ch in g.items():
        G.add_node(k)
        for c in ch:
            G.add_edge(c, k)      # premise -> dependent
    return G


def random_dag_like(G, seed=0):
    """same N and E, edges placed uniformly at random respecting a random
    topological order (so it is a DAG, but with no reuse structure)."""
    r = np.random.default_rng(seed)
    n, m = G.number_of_nodes(), G.number_of_edges()
    order = np.arange(n)
    H = nx.DiGraph()
    H.add_nodes_from(range(n))
    added = 0
    guard = 0
    while added < m and guard < 50 * m:
        guard += 1
        a, b = r.integers(0, n, 2)
        if a == b:
            continue
        u, v = (a, b) if a < b else (b, a)     # respect order => acyclic
        if not H.has_edge(u, v):
            H.add_edge(u, v)
            added += 1
    return H


def compare_models(deg):
    d = np.asarray([x for x in deg if x > 0])
    if len(d) < 50:
        return {}
    f = powerlaw.Fit(d, discrete=True, verbose=False)
    out = {"alpha": float(f.alpha), "xmin": int(f.xmin),
           "n_tail": int((d >= f.xmin).sum())}
    for alt in ["exponential", "lognormal", "stretched_exponential"]:
        try:
            R, p = f.distribution_compare("power_law", alt,
                                          normalized_ratio=True)
            out[f"LR_vs_{alt}"] = round(float(R), 2)
            out[f"p_vs_{alt}"] = round(float(p), 4)
        except Exception:
            pass
    return out


def disjoint_paths(G, n_pairs=120, seed=0):
    r = np.random.default_rng(seed)
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    vals = []
    tries = 0
    while len(vals) < n_pairs and tries < n_pairs * 40:
        tries += 1
        a, b = r.choice(len(nodes), 2, replace=False)
        u, v = nodes[a], nodes[b]
        if not nx.has_path(G, u, v):
            continue
        try:
            vals.append(nx.edge_connectivity(G, u, v))
        except Exception:
            pass
    return np.array(vals) if vals else np.array([0])


rows = []
dirs = sorted(glob.glob(f"{ROOT}/original_data/ManipulateProofTrees/ProofDAGs/*/"))
for d in dirs:
    g = pick_depth(d)
    if not g:
        continue
    G = to_graph(g)
    if G.number_of_nodes() < 200:
        continue
    name = os.path.basename(d.rstrip("/"))
    outd = np.array([k for _, k in G.out_degree()])
    ind = np.array([k for _, k in G.in_degree()])
    row = {"name": name, "N": G.number_of_nodes(), "E": G.number_of_edges()}
    row.update({f"out_{k}": v for k, v in compare_models(outd).items()})
    row.update({f"in_{k}": v for k, v in compare_models(ind).items()})
    H = random_dag_like(G, seed=1)
    rnd = np.array([k for _, k in H.out_degree()])
    row.update({f"rnd_{k}": v for k, v in compare_models(rnd).items()})
    # estimator-free structural claim
    dp_real = disjoint_paths(G)
    dp_rnd = disjoint_paths(H)
    row["dp_real_mean"] = float(dp_real.mean())
    row["dp_real_frac_ge2"] = float((dp_real >= 2).mean())
    row["dp_rnd_mean"] = float(dp_rnd.mean())
    row["dp_rnd_frac_ge2"] = float((dp_rnd >= 2).mean())
    rows.append(row)
    print(f"[{len(rows)}] {name}: N={row['N']} "
          f"alpha_out={row.get('out_alpha', float('nan')):.2f} "
          f"alpha_in={row.get('in_alpha', float('nan')):.2f} "
          f"alpha_rnd={row.get('rnd_alpha', float('nan')):.2f} "
          f"dp_real={row['dp_real_mean']:.2f} dp_rnd={row['dp_rnd_mean']:.2f}",
          flush=True)

df = pd.DataFrame(rows)
df.to_csv(f"{ROOT}/results/repro_validate.csv", index=False)

print("\n================ (1) MODEL COMPARISON: is it a power law? ============")
for alt in ["exponential", "lognormal", "stretched_exponential"]:
    c = f"out_LR_vs_{alt}"
    p = f"out_p_vs_{alt}"
    if c in df:
        fav = ((df[c] > 0) & (df[p] < 0.05)).sum()
        against = ((df[c] < 0) & (df[p] < 0.05)).sum()
        incon = (df[p] >= 0.05).sum()
        print(f"  power law vs {alt:24s}: favoured {fav}, rejected {against}, "
              f"inconclusive {incon}  (of {df[c].notna().sum()})")

print("\n================ (2) DISCRIMINATION: alpha on out / in / random =====")
for c, lab in [("out_alpha", "out-degree (claimed heavy-tailed)"),
               ("in_alpha", "in-degree (claimed Poisson)"),
               ("rnd_alpha", "random DAG, matched N & E")]:
    if c in df:
        print(f"  {lab:38s} alpha = {df[c].mean():.3f} +- {df[c].std():.3f}")
for c, lab in [("out_xmin", "out-degree"), ("rnd_xmin", "random DAG")]:
    if c in df:
        print(f"  median xmin ({lab}): {df[c].median():.0f}, "
              f"median tail n: {df[c.replace('xmin','n_tail')].median():.0f}")

print("\n================ (3) INDEPENDENT PATHS (estimator-free) =============")
print(f"  real proof DAGs : mean edge-disjoint paths "
      f"{df.dp_real_mean.mean():.2f}, frac>=2 {df.dp_real_frac_ge2.mean():.3f}")
print(f"  random DAG match: mean edge-disjoint paths "
      f"{df.dp_rnd_mean.mean():.2f}, frac>=2 {df.dp_rnd_frac_ge2.mean():.3f}")
from scipy import stats
print("  Wilcoxon real vs random (frac>=2): p =",
      stats.wilcoxon(df.dp_real_frac_ge2, df.dp_rnd_frac_ge2).pvalue)
print(f"\nwrote {ROOT}/results/repro_validate.csv")
