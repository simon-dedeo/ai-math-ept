"""
study6_etp_provenance.py — Who builds the load-bearing mathematics?

Hypothesis H8/N: in a hybrid human+machine project, machines resolve the head of
the difficulty distribution but the HUMAN-authored results become the
load-bearing hubs of the derivation structure.

ETP gives a complete, pre-registered test bed: 10,657 direct implications, each
attributable to a method (human-written file vs. a specific automated pipeline)
via full_entries.json's `filename`.

We measure, for each direct implication edge:
  * load  = how many of a large random sample of DERIVED (implicit_true) pairs
            have a shortest derivation path through that edge  (sampled edge
            betweenness on the skeleton)
  * reach = |ancestors| x |descendants| capacity of the edge (structural
            upper bound on what it could ever support)
and compare distributions across method classes.

Output: results/study6/etp_provenance.json + .csv
"""
import json, os, re, time, zipfile
from collections import Counter, defaultdict

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import breadth_first_order, dijkstra

ROOT = os.path.expanduser("~/ai_math_ept")
DATA = f"{ROOT}/projects/equational_theories/data"
OUT = f"{ROOT}/results/study6"
os.makedirs(OUT, exist_ok=True)
t0 = time.time()


def method_of(filename):
    """Classify provenance from the file the Lean theorem lives in."""
    f = filename.replace("./", "")
    if "/Generated/" in f:
        m = re.search(r"/Generated/([^/]+)/", f)
        return ("machine", m.group(1) if m else "GeneratedOther")
    return ("human", os.path.basename(f).replace(".lean", ""))


print("loading outcomes...", flush=True)
z = zipfile.ZipFile(f"{DATA}/2024-11-10-outcomes.json.zip")
d = json.loads(z.read(z.namelist()[0]))
eqs = d["equations"]
eq_idx = {e: i for i, e in enumerate(eqs)}
n = len(eqs)
CODES = {}
M = np.zeros((n, n), dtype=np.int8)
for i, row in enumerate(d["outcomes"]):
    for j, s in enumerate(row):
        M[i, j] = CODES.setdefault(s, len(CODES) + 1)
d = None
exp_true, imp_true = CODES["explicit_proof_true"], CODES["implicit_proof_true"]
print(f"outcomes loaded ({time.time()-t0:.0f}s)", flush=True)

# ---- skeleton
src, dst = np.where(M == exp_true)
keep = src != dst
src, dst = src[keep], dst[keep]
A = sp.csr_matrix((np.ones(len(src), np.int8), (src, dst)), shape=(n, n))
A.sum_duplicates(); A.sort_indices(); A.data = np.minimum(A.data, 1).astype(np.int8)
print(f"skeleton {A.nnz} edges", flush=True)

# ---- provenance for each edge
entries = json.load(open(f"{ROOT}/projects/equational_theories/full_entries.json"))
edge_method = {}
prov_counter = Counter()
for e in entries:
    v = e.get("variant", {})
    imp = v.get("implication")
    if not imp or not e.get("proven"):
        continue
    a, b = eq_idx.get(imp.get("lhs")), eq_idx.get(imp.get("rhs"))
    if a is None or b is None or a == b:
        continue
    cls, sub = method_of(e.get("filename", ""))
    edge_method[(a, b)] = (cls, sub)
    prov_counter[(cls, sub)] += 1
print("provenance labels for", len(edge_method), "implications", flush=True)
print(json.dumps({f"{c}/{s}": v for (c, s), v in prov_counter.most_common()},
                 indent=1), flush=True)

# ---- sampled edge betweenness over derived pairs
rng = np.random.default_rng(0)
ti, tj = np.where(M == imp_true)
keep = ti != tj
ti, tj = ti[keep], tj[keep]
NS = 300   # source nodes sampled
NT = 40    # targets per source
srcs = rng.choice(np.unique(ti), size=min(NS, len(np.unique(ti))), replace=False)
load = Counter()
n_paths = 0
for k, s in enumerate(srcs):
    dist, pred = dijkstra(A, directed=True, indices=int(s), unweighted=True,
                          return_predecessors=True)
    tg = tj[ti == s]
    if len(tg) == 0:
        continue
    tg = rng.choice(tg, size=min(NT, len(tg)), replace=False)
    for t in tg:
        cur = int(t)
        if not np.isfinite(dist[cur]):
            continue
        n_paths += 1
        while pred[cur] >= 0:
            p = int(pred[cur])
            load[(p, cur)] += 1
            cur = p
    if k % 50 == 0:
        print(f"  {k}/{len(srcs)} sources ({time.time()-t0:.0f}s)", flush=True)
print(f"traced {n_paths} derivation paths ({time.time()-t0:.0f}s)", flush=True)

# ---- structural capacity per edge (ancestors x descendants), sampled edges
def n_reach(A, s, rev=False):
    Am = A.T.tocsr() if rev else A
    return len(breadth_first_order(Am, s, directed=True,
                                   return_predecessors=False))

rows = []
all_edges = list(zip(src.tolist(), dst.tolist()))
sample_edges = [all_edges[i] for i in
                rng.choice(len(all_edges), size=min(3000, len(all_edges)),
                           replace=False)]
anc_cache, desc_cache = {}, {}
for (a, b) in sample_edges:
    cls, sub = edge_method.get((a, b), ("unknown", "unknown"))
    if a not in anc_cache:
        anc_cache[a] = n_reach(A, a, rev=True)
    if b not in desc_cache:
        desc_cache[b] = n_reach(A, b, rev=False)
    rows.append(dict(src=a, dst=b, cls=cls, sub=sub,
                     load=load.get((a, b), 0),
                     capacity=anc_cache[a] * desc_cache[b]))
print(f"capacity computed for {len(rows)} edges ({time.time()-t0:.0f}s)", flush=True)

import pandas as pd
df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/edge_provenance.csv", index=False)

summ = df.groupby("cls").agg(
    n=("load", "size"), load_mean=("load", "mean"),
    load_median=("load", "median"), load_p90=("load", lambda x: x.quantile(.9)),
    frac_zero_load=("load", lambda x: (x == 0).mean()),
    capacity_mean=("capacity", "mean")).round(3)
print("\n=== load by provenance class ===")
print(summ.to_string())

summ2 = df.groupby(["cls", "sub"]).agg(
    n=("load", "size"), load_mean=("load", "mean"),
    frac_zero_load=("load", lambda x: (x == 0).mean())).round(3)
summ2 = summ2[summ2["n"] >= 20].sort_values("load_mean", ascending=False)
print("\n=== load by specific method (n>=20) ===")
print(summ2.to_string())

from scipy import stats
h = df[df.cls == "human"]["load"]
m = df[df.cls == "machine"]["load"]
res = dict(
    n_human=int(len(h)), n_machine=int(len(m)),
    load_human_mean=float(h.mean()), load_machine_mean=float(m.mean()),
    load_human_median=float(h.median()), load_machine_median=float(m.median()),
    mannwhitney_p=float(stats.mannwhitneyu(h, m).pvalue) if len(h) and len(m) else None,
    ratio=float(h.mean() / m.mean()) if len(m) and m.mean() else None,
    provenance_counts={f"{c}/{s}": v for (c, s), v in prov_counter.most_common()},
    n_paths_traced=n_paths,
)
print("\n=== headline ===")
print(json.dumps(res, indent=1))
json.dump(res, open(f"{OUT}/etp_provenance.json", "w"), indent=1)
print(f"done {time.time()-t0:.0f}s", flush=True)
