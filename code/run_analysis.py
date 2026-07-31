"""
run_analysis.py — batch analysis of proof networks (Table-1 style + EPT).

Input: a directory of *.edges files (lines: "premise<TAB>dependent"), or a
JSON manifest [{name, path, theorem (optional node id), group}].
Output: results.csv (one row per network) + per-network certainty curves in
curves/ + optional firewall stats.

Usage:
  python run_analysis.py NETDIR OUTDIR [--group NAME] [--sweeps 10]
        [--runs 20] [--firewall] [--curve]
"""
import argparse, csv, glob, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from proofnet import load_edgelist, to_arrays, structural_stats
from belief import certainty_curve, beliefs, firewall_dL1

EPS_GRID = [0.4, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03, 0.02, 0.01, 0.005]


def theorem_node(G, hint=None):
    """The designated final claim: the hinted node if present, else the
    out-degree-0 node with the largest ancestry."""
    if hint and hint in G:
        return hint
    import networkx as nx
    sinks = [v for v in G.nodes() if G.out_degree(v) == 0]
    if not sinks:
        return max(G.nodes(), key=lambda v: G.in_degree(v))
    if len(sinks) == 1:
        return sinks[0]
    best, size = sinks[0], -1
    for v in sinks:
        k = len(nx.ancestors(G, v))
        if k > size:
            best, size = v, k
    return best


def analyze_one(name, path, group, args, thm_hint=None):
    G = load_edgelist(path, delimiter="\t")
    if G.number_of_nodes() == 0:
        G = load_edgelist(path)  # whitespace fallback
    if G.number_of_nodes() < 3:
        return None
    stats, comms = structural_stats(G, name)
    stats["group"] = group
    arrs = to_arrays(G)
    thm = theorem_node(G, thm_hint)
    ti = arrs["index"][thm]
    stats["theorem"] = str(thm)

    # f2: belief in theorem at eps = 1e-2
    b = beliefs(arrs, 1e-2, 1e-2, sweeps=args.sweeps, n_runs=args.runs)
    stats["f2"] = round(float(b[ti]), 4)
    stats["mean_belief_e2"] = round(float(b.mean()), 4)

    if args.curve:
        rows = certainty_curve(arrs, EPS_GRID, theorem_idx=ti,
                               sweeps=args.sweeps, n_runs=args.runs)
        os.makedirs(os.path.join(args.outdir, "curves"), exist_ok=True)
        with open(os.path.join(args.outdir, "curves", f"{name}.json"), "w") as f:
            json.dump(rows, f)
        # locate transition: first eps (descending) where thm belief > 0.95
        eps_c = None
        for r in sorted(rows, key=lambda r: -r["eps"]):
            if r["theorem_belief"] >= 0.95:
                eps_c = r["eps"]
                break
        stats["eps_crit"] = eps_c

    if args.firewall and comms and len(comms) > 1:
        fw = firewall_dL1(arrs, [set(c) for c in comms], index=arrs["index"],
                          n_random=100)
        if fw:
            stats["dL1_mean"] = round(float(np.mean([x["dL1"] for x in fw])), 2)
            stats["dL1_min"] = round(float(min(x["dL1"] for x in fw)), 2)
    return stats


def _work(job, args):
    name, path, group, thm = job
    try:
        return name, analyze_one(name, path, group, args, thm), None
    except Exception as e:
        return name, None, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netdir")
    ap.add_argument("outdir")
    ap.add_argument("--group", default=None)
    ap.add_argument("--sweeps", type=int, default=10)
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--firewall", action="store_true")
    ap.add_argument("--curve", action="store_true")
    ap.add_argument("--parallel", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    manifest = os.path.join(args.netdir, "manifest.json")
    jobs = []
    if os.path.exists(manifest):
        for item in json.load(open(manifest)):
            jobs.append((item["name"], os.path.join(args.netdir, item["path"]),
                         item.get("group", args.group or "default"),
                         item.get("theorem")))
    else:
        for p in sorted(glob.glob(os.path.join(args.netdir, "*.edges"))):
            jobs.append((os.path.splitext(os.path.basename(p))[0], p,
                         args.group or "default", None))

    out_rows = []

    if args.parallel > 1:
        import multiprocessing as mp
        from functools import partial
        with mp.get_context("fork").Pool(args.parallel) as pool:
            it = pool.imap_unordered(partial(_work, args=args), jobs)
            for name, row, err in it:
                if row:
                    out_rows.append(row)
                    print(f"[ok] {name}: N={row['nodes']} E={row['edges']} "
                          f"f2={row['f2']} alpha={row.get('alpha')} "
                          f"Q={row.get('modularity')}", flush=True)
                else:
                    print(f"[fail] {name}: {err}", flush=True)
    else:
        for job in jobs:
            name, row, err = _work(job, args)
            if row:
                out_rows.append(row)
                print(f"[ok] {name}: N={row['nodes']} E={row['edges']} "
                      f"f2={row['f2']} alpha={row.get('alpha')} "
                      f"Q={row.get('modularity')}", flush=True)
            else:
                print(f"[fail] {name}: {err}", flush=True)

    if out_rows:
        keys = sorted({k for r in out_rows for k in r})
        with open(os.path.join(args.outdir, "results.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(out_rows)
        print(f"wrote {len(out_rows)} rows to {args.outdir}/results.csv")


if __name__ == "__main__":
    main()
