"""
study4b_vampire.py — natural redundancy & difficulty census of the ETP space.

The 2025-08-11 Vampire dump records, for every one of the 22,028,942 ordered
pairs, the outcome of a fixed ATP attempt: {"value": code, "time": seconds,
"method_id": ...}. Cross-tabulating against the outcomes matrix tells us:
  1. What fraction of the 8.16M TRUE implications a single 5s Vampire call
     proves DIRECTLY (the redundancy that was available but not recorded in
     the 10,657-edge skeleton).
  2. The distribution of solve times over the whole space (difficulty census).
  3. The "hard tail": true implications Vampire cannot prove at this budget.
Also recompute percolation robustness using the FULL Vampire-provable direct
edge set instead of the skeleton: how robust WOULD the corpus be if the
available redundancy had been kept?
"""
import gzip, json, os, time, zipfile
import numpy as np
import scipy.sparse as sp

DATA = os.path.expanduser("~/ai_math_ept/projects/equational_theories/data")
OUT = os.path.expanduser("~/ai_math_ept/results/study4")

t0 = time.time()
print("loading outcomes...", flush=True)
z = zipfile.ZipFile(os.path.join(DATA, "2024-11-10-outcomes.json.zip"))
d = json.loads(z.read(z.namelist()[0]))
n = len(d["equations"])
CODES = {}
M = np.zeros((n, n), dtype=np.int8)
for i, row in enumerate(d["outcomes"]):
    for j, s in enumerate(row):
        c = CODES.setdefault(s, len(CODES) + 1)
        M[i, j] = c
d = None
print(f"outcomes loaded ({time.time()-t0:.0f}s)", flush=True)

print("loading vampire dump...", flush=True)
with gzip.open(os.path.join(DATA, "2025-08-11-vampire.json.gz")) as f:
    vd = json.load(f)
vals = vd["values"]
print(f"vampire loaded: {len(vals)} entries ({time.time()-t0:.0f}s)", flush=True)

# value-code census and cross-tab vs outcome class
from collections import Counter, defaultdict
code_census = Counter()
cross = defaultdict(Counter)
times_true_proved = []
times_unproved = []
src_list, dst_list = [], []
inv = {v: k for k, v in CODES.items()}

exp_true = CODES.get("explicit_proof_true")
imp_true = CODES.get("implicit_proof_true")

k = 0
for key, rec in vals.items():
    i_s, j_s = key.split("_")
    i, j = int(i_s) - 1, int(j_s) - 1   # equation ids are 1-based
    v = rec["value"]
    code_census[v] += 1
    oc = M[i, j]
    cross[inv.get(oc, "?")][v] += 1
    if oc in (exp_true, imp_true):
        if v == 1:   # assume 1 = proved (checked below via census)
            times_true_proved.append(rec["time"])
            if i != j:
                src_list.append(i)
                dst_list.append(j)
        else:
            times_unproved.append(rec["time"])
    k += 1
    if k % 4000000 == 0:
        print(f"  {k/1e6:.0f}M processed ({time.time()-t0:.0f}s)", flush=True)

print("value code census:", dict(code_census), flush=True)
print("cross-tab (outcome class -> vampire code):", flush=True)
for oc, c in cross.items():
    print("  ", oc, dict(c), flush=True)

res = {
    "value_code_census": {str(k_): int(v_) for k_, v_ in code_census.items()},
    "cross_tab": {oc: {str(k_): int(v_) for k_, v_ in c.items()}
                  for oc, c in cross.items()},
}

tp = np.array(times_true_proved)
if len(tp):
    res["vampire_direct_true"] = int(len(tp))
    res["time_quantiles_proved"] = {q: float(np.percentile(tp, q))
                                    for q in (50, 90, 99, 99.9)}
print(json.dumps({k_: v_ for k_, v_ in res.items()
                  if k_ != "cross_tab"}, indent=1), flush=True)

# --- percolation with the FULL vampire-provable direct edge set
if src_list:
    A = sp.csr_matrix((np.ones(len(src_list), dtype=np.int8),
                       (src_list, dst_list)), shape=(n, n))
    A.sum_duplicates(); A.sort_indices()
    A.data = np.minimum(A.data, 1).astype(np.int8)
    print(f"vampire-provable direct graph: {A.nnz} edges "
          f"(vs 10657 skeleton)", flush=True)

    from scipy.sparse.csgraph import breadth_first_order
    rng = np.random.default_rng(0)
    ti, tj = np.where(M == imp_true)
    mask = ti != tj
    ti, tj = ti[mask], tj[mask]
    samp = rng.choice(len(ti), size=20000, replace=False)
    si, sj = ti[samp], tj[samp]

    def reach_frac(Acsr, drop):
        A2 = Acsr.copy()
        if drop > 0:
            keep = rng.random(len(A2.data)) >= drop
            A2.data = (A2.data * keep).astype(A2.data.dtype)
            A2.eliminate_zeros()
        order = np.argsort(si)
        s_i, s_j = si[order], sj[order]
        ok = 0
        cache_src, reachable = -1, None
        for a, b in zip(s_i, s_j):
            if a != cache_src:
                nodes = breadth_first_order(A2, a, directed=True,
                                            return_predecessors=False)
                reachable = np.zeros(n, dtype=bool)
                reachable[nodes] = True
                cache_src = a
            ok += bool(reachable[b])
        return ok / len(s_i)

    base = reach_frac(A, 0.0)
    print(f"baseline derivability via vampire-full graph: {base:.4f}", flush=True)
    perc = []
    for eps in [0.01, 0.03, 0.1, 0.2, 0.3, 0.5]:
        v = [reach_frac(A, eps) for _ in range(5)]
        perc.append(dict(eps=eps, mean=float(np.mean(v)), sd=float(np.std(v))))
        print(f"eps={eps}: survive={np.mean(v):.4f}±{np.std(v):.4f}", flush=True)
    res["vampire_full_percolation"] = perc
    res["vampire_full_edges"] = int(A.nnz)
    res["vampire_full_baseline"] = base

    # edge-disjoint redundancy on the full available graph (sampled)
    import networkx as nx
    G = nx.from_scipy_sparse_array(A, create_using=nx.DiGraph)
    red = []
    s2 = rng.choice(len(si), size=400, replace=False)
    for a, b in zip(si[s2], sj[s2]):
        try:
            red.append(nx.edge_connectivity(G, int(a), int(b)))
        except Exception:
            pass
    if red:
        red = np.array(red)
        res["vampire_full_disjoint_paths"] = dict(
            mean=float(red.mean()), median=float(np.median(red)),
            p90=float(np.percentile(red, 90)), max=int(red.max()),
            frac_ge2=float((red >= 2).mean()),
            frac_ge5=float((red >= 5).mean()))
        print("available redundancy:", res["vampire_full_disjoint_paths"],
              flush=True)

with open(os.path.join(OUT, "etp_vampire_stats.json"), "w") as f:
    json.dump(res, f, indent=1)
print(f"done in {time.time()-t0:.0f}s", flush=True)
