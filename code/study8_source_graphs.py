"""
study8_source_graphs.py — Cross-project structural comparison from SOURCE ONLY
(no compilation), so that human-authored and AI-authored formalizations of the
same and different projects can be compared on equal terms.

For each corpus we build the *named-citation* graph a human reader sees:
  nodes = declarations (theorem/lemma/def/instance) declared in the corpus
  edge u -> v  iff the body of v mentions the name u
and report: N, edges, modularity Q (Louvain), in-degree tail alpha, share never
cited, Gini of reuse, plus the EPT belief curve on that graph.

Tests:
  N2  modularity is conserved while reuse is not (compare Gauss vs human layers)
  N6  library-level robustness by corpus authorship mix

Corpora: human vs Gauss sphere-packing layers, Gauss strongpnt, pfr, FLT,
equational_theories human vs Generated, plus (if a full mathlib4 history is
available) yearly Mathlib snapshots.

Output: results/study8/source_graphs.csv + .json
"""
import glob, json, os, re, subprocess, sys, time
from collections import defaultdict

import numpy as np
import networkx as nx

ROOT = os.path.expanduser("~/ai_math_ept")
OUT = f"{ROOT}/results/study8"
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, f"{ROOT}/code")
from proofnet import gini, to_arrays, powerlaw_alpha
from census import strip_noncode
from belief import beliefs

t0 = time.time()
DECL = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:private\s+|protected\s+|noncomputable\s+|public\s+)*"
    r"(theorem|lemma|def|abbrev|instance|structure|class)\s+([A-Za-z_][A-Za-z0-9_'.!?]*)",
    re.M)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_'.!?]*")


def parse_corpus(files):
    """Return (decl_order, bodies): declarations in file order + their bodies."""
    decls, bodies = [], {}
    for p in files:
        try:
            src = strip_noncode(open(p, encoding="utf-8", errors="ignore").read())
        except Exception:
            continue
        ms = list(DECL.finditer(src))
        for i, m in enumerate(ms):
            name = m.group(2)
            start = m.end()
            end = ms[i + 1].start() if i + 1 < len(ms) else len(src)
            if name in bodies:      # first definition wins
                continue
            decls.append(name)
            bodies[name] = src[start:end]
    return decls, bodies


def build_graph(decls, bodies):
    S = set(decls)
    G = nx.DiGraph()
    G.add_nodes_from(decls)
    for v, body in bodies.items():
        for tok in set(IDENT.findall(body)):
            if tok in S and tok != v:
                G.add_edge(tok, v)     # premise -> dependent
    return G


def analyze(name, files, extra=None):
    decls, bodies = parse_corpus(files)
    if len(decls) < 30:
        print(f"[skip] {name}: only {len(decls)} decls", flush=True)
        return None
    G = build_graph(decls, bodies)
    indeg = np.array([d for _, d in G.in_degree()])    # premises cited
    reuse = np.array([d for _, d in G.out_degree()])   # how often cited
    row = dict(corpus=name, n_files=len(files), n_decls=G.number_of_nodes(),
               n_edges=G.number_of_edges(),
               mean_premises=float(indeg.mean()),
               mean_reuse=float(reuse.mean()),
               frac_never_cited=float((reuse == 0).mean()),
               reuse_gini=gini(reuse), max_reuse=int(reuse.max()))
    try:
        a, s, xmin, ntail = powerlaw_alpha(reuse)
        row.update(alpha_reuse=round(float(a), 3), alpha_xmin=int(xmin))
    except Exception:
        pass
    U = G.to_undirected(); U.remove_nodes_from(list(nx.isolates(U)))
    if U.number_of_nodes() > 10:
        from networkx.algorithms.community import louvain_communities, modularity
        comms = louvain_communities(U, seed=0)
        row["modularity_Q"] = round(float(modularity(U, comms)), 3)
        row["n_modules"] = len(comms)
    # EPT belief curve
    arrs = to_arrays(G)
    for eps in [0.1, 0.05, 0.01]:
        b = beliefs(arrs, eps, eps, n_runs=8)
        row[f"belief_eps{eps}"] = round(float(b.mean()), 4)
    if extra:
        row.update(extra)
    print(f"[ok] {name}: N={row['n_decls']} E={row['n_edges']} "
          f"Q={row.get('modularity_Q')} alpha={row.get('alpha_reuse')} "
          f"never_cited={row['frac_never_cited']:.3f} "
          f"belief@.01={row['belief_eps0.01']}", flush=True)
    return row


def lean_files(root, exclude=()):
    out = []
    for p in glob.glob(f"{root}/**/*.lean", recursive=True):
        if any(x in p for x in exclude) or "/.lake/" in p:
            continue
        out.append(p)
    return sorted(out)


rows = []

# ---- sphere packing: human layer (repo before Gauss) vs Gauss layer
sp_human = f"{ROOT}/projects/Sphere-Packing-Lean"
sp_gauss = f"{ROOT}/corpora/mathinc-sphere-packing"
if os.path.isdir(sp_human):
    # human snapshot: repo state before 2026-02-15
    try:
        rev = subprocess.run(
            ["git", "-C", sp_human, "rev-list", "-1", "--before=2026-02-15", "HEAD"],
            capture_output=True, text=True, timeout=60).stdout.strip()
        wt = f"/tmp/sp_human_snapshot"
        if rev and not os.path.isdir(wt):
            subprocess.run(["git", "-C", sp_human, "worktree", "add", "--detach",
                            wt, rev], capture_output=True, timeout=300)
        if os.path.isdir(wt):
            rows.append(analyze("sphere_packing_HUMAN(pre-Feb2026)",
                                lean_files(wt), {"authorship": "human"}))
    except Exception as e:
        print("human snapshot failed:", e, flush=True)
if os.path.isdir(sp_gauss):
    rows.append(analyze("sphere_packing_GAUSS(math-inc)",
                        lean_files(sp_gauss), {"authorship": "AI"}))

# ---- Gauss strongpnt
p = f"{ROOT}/corpora/mathinc-strongpnt"
if os.path.isdir(p):
    rows.append(analyze("strongPNT_GAUSS", lean_files(p), {"authorship": "AI"}))

# ---- human-led projects
for nm, path in [("pfr_HUMAN", f"{ROOT}/projects/pfr"),
                 ("FLT_HUMAN", f"{ROOT}/projects/FLT"),
                 ("PNT+_HUMAN", f"{ROOT}/projects/PrimeNumberTheoremAnd")]:
    if os.path.isdir(path):
        rows.append(analyze(nm, lean_files(path), {"authorship": "human"}))

# ---- equational theories: human-written vs machine-generated files
et = f"{ROOT}/projects/equational_theories/equational_theories"
if os.path.isdir(et):
    gen = [p for p in lean_files(et) if "/Generated/" in p]
    hum = [p for p in lean_files(et) if "/Generated/" not in p]
    if hum:
        rows.append(analyze("ETP_human_files", hum, {"authorship": "human"}))
    if gen:
        rows.append(analyze("ETP_generated_files", gen, {"authorship": "machine"}))

# ---- AI competition-proof corpora (each file = one proof; graph is sparse but
#      informative about cross-proof lemma sharing)
for nm, path in [("compfiles_HUMAN", f"{ROOT}/corpora/human-compfiles"),
                 ("seed_prover_AI", f"{ROOT}/corpora/seed-prover"),
                 ("aristotle_AI", f"{ROOT}/corpora/harmonic-aristotle-imo2025"),
                 ("alphaproof_nexus_AI", f"{ROOT}/corpora/alphaproof-nexus")]:
    if os.path.isdir(path):
        fs = lean_files(path)
        if fs:
            rows.append(analyze(nm, fs,
                                {"authorship": "human" if "HUMAN" in nm else "AI"}))

rows = [r for r in rows if r]
import pandas as pd
df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/source_graphs.csv", index=False)
print("\n=== summary ===")
cols = [c for c in ["corpus", "authorship", "n_decls", "n_edges", "modularity_Q",
                    "alpha_reuse", "frac_never_cited", "reuse_gini",
                    "belief_eps0.01"] if c in df.columns]
print(df[cols].to_string(index=False))

if "authorship" in df.columns:
    print("\n=== by authorship ===")
    print(df.groupby("authorship")[[c for c in
          ["modularity_Q", "alpha_reuse", "frac_never_cited", "reuse_gini",
           "belief_eps0.01"] if c in df.columns]].mean().round(3).to_string())
print(f"done {time.time()-t0:.0f}s", flush=True)
