"""
compare_corpora.py — Study 2: compare proof-network statistics across corpora
(AI provers vs human) with per-theorem matching where problem IDs align.

Inputs: list of "group=dir" pairs; each dir holds <stem>_{term0,term,decl}.json
from ExtractNetwork/extract_corpus.

Per proof (fast, no simulation):
  term0: nodes, edges, visits (tree size), dedup = visits/nodes,
         depth, n_consts (distinct C: labels), per-branch stats
  term:  N, E, alpha (CSN fit), modularity Q, levels, truncated
  decl:  N (filtered), premises = distinct named lemmas at level 1

EPT simulation (f2 + eps_crit) run only when --simulate, on term networks.

Output: OUT/proofs.csv (one row per proof x group) + OUT/matched.csv
(inner join across groups on normalized problem id).
"""
import argparse, glob, json, os, re, sys
from collections import defaultdict

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proofnet import structural_stats, dag_depth, to_arrays, gini
from belief import beliefs


def norm_id(stem):
    """imo_1964_p2 / Imo1964P2 / imo1964_p2 -> imo_1964_p2"""
    s = stem.lower()
    s = re.sub(r"_x$", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    m = re.match(r"^(imo|usamo|putnam|aime|amc|balticway|usa|induction|mathd|"
                 r"numbertheory|algebra)(\d*)", s)
    return s


def load_json_graph(path):
    d = json.load(open(path))
    G = nx.DiGraph()
    G.add_nodes_from(range(d["nodes"]))
    G.add_edges_from(d["edges"])
    return d, G


def term0_stats(path):
    d, G = load_json_graph(path)
    labels = d["labels"]
    consts = [l[2:] for l in labels if l.startswith("C:")]
    n = d["nodes"]
    row = dict(
        t0_nodes=n, t0_edges=len(d["edges"]),
        t0_visits=d.get("visits", 0),
        t0_dedup=round(d.get("visits", 0) / max(n, 1), 3),
        t0_depth=dag_depth(G),
        t0_consts=len(consts),
        t0_consts_per_node=round(len(consts) / max(n, 1), 4),
    )
    return row


def term_stats(path, simulate=False, runs=10):
    d, G = load_json_graph(path)
    import proofnet
    st, _ = proofnet.structural_stats(G, fit_powerlaw=True)
    row = dict(t_nodes=st["nodes"], t_edges=st["edges"],
               t_alpha=st.get("alpha"), t_alpha_err=st.get("alpha_err"),
               t_Q=st.get("modularity"), t_nmod=st.get("n_modules"),
               t_depth=st["depth"], t_gini=st["out_gini"],
               t_levels=d.get("levels"), t_trunc=d.get("truncated"))
    if simulate and st["nodes"] >= 100:
        arrs = to_arrays(G)
        thm = None
        for i, l in enumerate(d["labels"]):
            if l.startswith("THM:"):
                thm = arrs["index"][i]
                break
        b = beliefs(arrs, 1e-2, 1e-2, n_runs=runs)
        row["t_f2"] = round(float(b[thm]), 4) if thm is not None else None
        row["t_meanbelief"] = round(float(b.mean()), 4)
    return row


def decl_stats(path):
    d, _ = load_json_graph(path)
    labels = d["labels"]
    # level-1 premises: distinct constants directly cited by the root (node 0)
    direct = set()
    for a, b in d["edges"]:
        if b == 0:
            direct.add(labels[a])
    filt = re.compile(r"(\._|^_|\.match_|\.proof_|\.eq_def$|\.eq_\d+$)")
    named = [x for x in direct if not filt.search(x)]
    return dict(d_nodes=d["nodes"], d_premises=len(named),
                d_levels=d.get("levels"))


def _one(task):
    gname, t0, simulate = task
    stem = os.path.basename(t0)[: -len("_term0.json")]
    row = dict(group=gname, stem=stem, pid=norm_id(stem))
    try:
        row.update(term0_stats(t0))
        tp = t0.replace("_term0.json", "_term.json")
        if os.path.exists(tp):
            row.update(term_stats(tp, simulate=simulate))
        dp = t0.replace("_term0.json", "_decl.json")
        if os.path.exists(dp):
            row.update(decl_stats(dp))
        return row
    except Exception as e:
        print(f"[fail] {gname}/{stem}: {e}", flush=True)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("groups", nargs="+", help="group=dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--parallel", type=int, default=1)
    args = ap.parse_args()
    # batch scale: always use Louvain, never exact Girvan-Newman
    import proofnet
    proofnet.structural_stats.__defaults__  # noqa
    _orig = proofnet.girvan_newman_modules
    proofnet.girvan_newman_modules = (
        lambda G, max_nodes_exact=0: _orig(G, max_nodes_exact=0))
    os.makedirs(args.out, exist_ok=True)

    tasks = []
    for g in args.groups:
        gname, gdir = g.split("=", 1)
        for t0 in sorted(glob.glob(os.path.join(gdir, "*_term0.json"))):
            tasks.append((gname, t0, args.simulate))
    print(f"{len(tasks)} proofs to analyze", flush=True)
    if args.parallel > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(args.parallel) as pool:
            rows = [r for r in pool.imap_unordered(_one, tasks, chunksize=4) if r]
    else:
        rows = [r for r in map(_one, tasks) if r]
    print(f"{len(rows)} analyzed OK", flush=True)

    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(args.out, "proofs.csv"), index=False)

    # group summary
    num = df.select_dtypes(include=[np.number]).columns
    summ = df.groupby("group")[list(num)].agg(["median", "mean", "count"])
    summ.to_csv(os.path.join(args.out, "summary.csv"))
    print(summ.round(3).to_string())

    # matched pairs across groups
    groups = df["group"].unique()
    if len(groups) > 1:
        piv = df.pivot_table(index="pid", columns="group", values="t0_nodes",
                             aggfunc="count")
        matched_ids = piv.dropna().index
        m = df[df["pid"].isin(matched_ids)]
        m.to_csv(os.path.join(args.out, "matched.csv"), index=False)
        print(f"\nmatched problem ids across all {len(groups)} groups: "
              f"{len(matched_ids)}")


if __name__ == "__main__":
    main()
