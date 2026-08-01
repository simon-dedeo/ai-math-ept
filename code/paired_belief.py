"""Does the premise deficit change the epistemic phase transition?

For statements where BOTH the human and the AI proof elaborated successfully, we
now have two proof-term networks of the SAME theorem. Run the 2022 belief model
on each and compare paired: structure (alpha, Q, depth) and epistemics (f2, and
the certainty curve).
"""
import glob, json, os, sys
import numpy as np, pandas as pd, networkx as nx
from scipy import stats
sys.path.insert(0, "code")
from proofnet import structural_stats, to_arrays, dag_depth
from belief import beliefs
import proofnet
_o = proofnet.girvan_newman_modules
proofnet.girvan_newman_modules = lambda G, max_nodes_exact=0: _o(G, max_nodes_exact=0)

def load(p):
    d = json.load(open(p))
    G = nx.DiGraph(); G.add_nodes_from(range(d["nodes"])); G.add_edges_from(d["edges"])
    return d, G

def analyse(p):
    d, G = load(p)
    if G.number_of_nodes() < 50: return None
    st, _ = structural_stats(G)
    arrs = to_arrays(G)
    thm = None
    for i, l in enumerate(d["labels"]):
        if l.startswith("THM:"): thm = arrs["index"][i]; break
    row = dict(N=st["nodes"], E=st["edges"], alpha=st.get("alpha"),
               Q=st.get("modularity"), depth=st["depth"], gini=st["out_gini"],
               consts=sum(1 for l in d["labels"] if l.startswith("C:")))
    for eps in (0.1, 0.05, 0.01):
        b = beliefs(arrs, eps, eps, n_runs=12)
        row[f"mean_{eps}"] = float(b.mean())
        if thm is not None: row[f"f2_{eps}"] = float(b[thm])
    return row

H = {os.path.basename(p)[:-len("_term.json")]: p
     for p in glob.glob("networks/paired_human/*_term.json")}
A = {os.path.basename(p)[:-len("_term.json")]: p
     for p in glob.glob("networks/paired_ai/*_term.json")}
common = sorted(set(H) & set(A))
print(f"matched proof-term pairs available: {len(common)}", flush=True)
rows = []
for i, k in enumerate(common):
    try:
        h, a = analyse(H[k]), analyse(A[k])
        if h and a:
            rows.append({"pair": k, **{f"h_{x}": v for x, v in h.items()},
                         **{f"a_{x}": v for x, v in a.items()}})
    except Exception as e:
        pass
    if (i+1) % 25 == 0: print(f"  {i+1}/{len(common)}", flush=True)
p = pd.DataFrame(rows)
p.to_csv("results/paired_belief.csv", index=False)
print(f"\nanalysed {len(p)} pairs\n")
print(f"{'metric':12s} {'human':>10s} {'AI':>10s} {'Wilcoxon p':>12s}")
for m in ["N", "E", "consts", "alpha", "Q", "depth", "gini",
          "f2_0.01", "mean_0.01", "f2_0.05", "mean_0.05", "f2_0.1"]:
    hc, ac = f"h_{m}", f"a_{m}"
    if hc not in p or ac not in p: continue
    x, y = p[hc].astype(float), p[ac].astype(float)
    ok = x.notna() & y.notna()
    if ok.sum() < 8: continue
    try: pv = stats.wilcoxon(x[ok], y[ok]).pvalue
    except Exception: pv = float("nan")
    print(f"{m:12s} {x[ok].median():10.4f} {y[ok].median():10.4f} {pv:12.3g}")
