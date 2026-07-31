"""
study9_matched_pairs.py — The cleanest AI-vs-human contrast available: the SAME
competition problem, proved by different agents, with the full EPT belief model
run on each proof network.

Sources of matched pairs:
  * miniF2F problems proved by DeepSeek-Prover-V2, Kimina, and Seed-Prover
    (three independent AI systems, same statements) -> AI-vs-AI variability,
    which calibrates how much of any human-AI gap is just noise
  * IMO problems appearing in both compfiles (human) and the AI IMO corpora
    (AlphaProof 2024, Seed/Aristotle 2025)
  * AlphaProof raw agent output vs the human-polished version of the same proof
    (the tightest possible control: identical theorem, identical prover, one
    pass of human editing)

Outputs results/study9/matched_pairs.csv and a summary of paired differences.
"""
import glob, json, os, re, sys, time
from collections import defaultdict

import numpy as np
import pandas as pd
import networkx as nx

ROOT = os.path.expanduser("~/ai_math_ept")
OUT = f"{ROOT}/results/study9"
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, f"{ROOT}/code")
from proofnet import structural_stats, to_arrays, dag_depth
from belief import beliefs
import proofnet
_orig = proofnet.girvan_newman_modules
proofnet.girvan_newman_modules = lambda G, max_nodes_exact=0: _orig(G, max_nodes_exact=0)

t0 = time.time()
GROUPS = {
    "human_compfiles": f"{ROOT}/networks/compfiles_human",
    "dsv2": f"{ROOT}/networks/dsv2_minif2f_test",
    "dsv2_valid": f"{ROOT}/networks/dsv2_minif2f_valid",
    "kimina": f"{ROOT}/networks/kimina_minif2f",
    "seed": f"{ROOT}/networks/seed_minif2f",
    "seed_imo25": f"{ROOT}/networks/seed_imo2025",
    "alphaproof": f"{ROOT}/networks/alphaproof_imo2024",
    "aristotle": f"{ROOT}/networks/aristotle_imo2025",
}


def canon(stem):
    s = stem.lower()
    s = re.sub(r"_(raw|polished|x)$", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    # imo2024p1 / imo_2024_p1 / Imo2024P1 -> imo2024p1
    return s


def full_stats(path_term0):
    base = path_term0[: -len("_term0.json")]
    d0 = json.load(open(path_term0))
    G0 = nx.DiGraph(); G0.add_nodes_from(range(d0["nodes"])); G0.add_edges_from(d0["edges"])
    row = dict(t0_nodes=d0["nodes"], t0_visits=d0.get("visits", 0),
               t0_dedup=round(d0.get("visits", 0) / max(d0["nodes"], 1), 3),
               t0_depth=dag_depth(G0),
               t0_consts=sum(1 for l in d0["labels"] if l.startswith("C:")))
    tp = base + "_term.json"
    if os.path.exists(tp):
        d = json.load(open(tp))
        G = nx.DiGraph(); G.add_nodes_from(range(d["nodes"])); G.add_edges_from(d["edges"])
        st, _ = structural_stats(G)
        row.update(t_nodes=st["nodes"], t_edges=st["edges"],
                   t_alpha=st.get("alpha"), t_Q=st.get("modularity"),
                   t_depth=st["depth"], t_gini=st["out_gini"])
        arrs = to_arrays(G)
        thm = None
        for i, l in enumerate(d["labels"]):
            if l.startswith("THM:"):
                thm = arrs["index"][i]; break
        for eps in [0.1, 0.05, 0.01]:
            b = beliefs(arrs, eps, eps, n_runs=10)
            row[f"belief_eps{eps}"] = round(float(b.mean()), 4)
            if thm is not None:
                row[f"f2_eps{eps}"] = round(float(b[thm]), 4)
    return row


rows = []
for g, d in GROUPS.items():
    if not os.path.isdir(d):
        continue
    for p in sorted(glob.glob(f"{d}/*_term0.json")):
        stem = os.path.basename(p)[: -len("_term0.json")]
        try:
            r = dict(group=g, stem=stem, pid=canon(stem),
                     variant=("raw" if stem.endswith("_raw") else
                              "polished" if stem.endswith("_polished") else "-"))
            r.update(full_stats(p))
            rows.append(r)
        except Exception as e:
            print(f"[fail] {g}/{stem}: {e}", flush=True)
    print(f"[{g}] {sum(1 for r in rows if r['group']==g)} proofs "
          f"({time.time()-t0:.0f}s)", flush=True)

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/matched_pairs.csv", index=False)
print(f"\n{len(df)} proof networks analyzed")

METRICS = [c for c in ["t0_nodes", "t0_dedup", "t0_depth", "t0_consts",
                       "t_alpha", "t_Q", "t_gini", "belief_eps0.01",
                       "f2_eps0.01", "f2_eps0.05"] if c in df.columns]

print("\n=== group medians ===")
print(df.groupby("group")[METRICS].median().round(3).to_string())

# ---- paired comparisons on shared problem ids
from scipy import stats
pairs_out = []
groups = sorted(df["group"].unique())
for i, a in enumerate(groups):
    for b in groups[i + 1:]:
        A = df[df.group == a].drop_duplicates("pid").set_index("pid")
        B = df[df.group == b].drop_duplicates("pid").set_index("pid")
        common = A.index.intersection(B.index)
        if len(common) < 5:
            continue
        rec = dict(group_a=a, group_b=b, n_pairs=int(len(common)))
        for m in METRICS:
            if m not in A or m not in B:
                continue
            x, y = A.loc[common, m].astype(float), B.loc[common, m].astype(float)
            ok = x.notna() & y.notna()
            if ok.sum() < 5:
                continue
            try:
                p = stats.wilcoxon(x[ok], y[ok]).pvalue
            except Exception:
                p = np.nan
            rec[f"{m}_a"] = round(float(x[ok].median()), 3)
            rec[f"{m}_b"] = round(float(y[ok].median()), 3)
            rec[f"{m}_p"] = float(p)
        pairs_out.append(rec)
        print(f"\n--- {a} vs {b}  (n={len(common)} shared problems)")
        for m in METRICS:
            if f"{m}_p" in rec:
                print(f"    {m:15s} {rec[f'{m}_a']:>9} vs {rec[f'{m}_b']:>9}  "
                      f"p={rec[f'{m}_p']:.3g}")

json.dump(pairs_out, open(f"{OUT}/paired_tests.json", "w"), indent=1)

# ---- AlphaProof raw vs polished (same prover, one human edit pass)
ap = df[df.group == "alphaproof"]
if len(ap) and (ap["variant"] != "-").any():
    r = ap[ap.variant == "raw"].set_index("pid")
    q = ap[ap.variant == "polished"].set_index("pid")
    common = r.index.intersection(q.index)
    if len(common):
        print(f"\n=== AlphaProof raw vs human-polished (n={len(common)}) ===")
        comp = pd.DataFrame({
            "raw": r.loc[common, METRICS].median(),
            "polished": q.loc[common, METRICS].median()}).round(3)
        print(comp.to_string())
        comp.to_csv(f"{OUT}/alphaproof_raw_vs_polished.csv")

print(f"done {time.time()-t0:.0f}s", flush=True)
