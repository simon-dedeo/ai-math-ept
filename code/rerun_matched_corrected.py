"""Re-run the matched-system statistics with the corrected implementation
(code/matched_stats.py). Supersedes the numbers in report §5f and §5f-bis."""
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matched_stats import complete_block, friedman_block, variance_components

ROOT = os.path.expanduser("~/ai_math_ept")
OUT = f"{ROOT}/results/matched_corrected"; os.makedirs(OUT, exist_ok=True)
METRICS = ["vocab_ratio", "n_lines", "n_have", "n_distinct_premises"]
res = {}

SOURCES = {
  "lean_eval": (f"{ROOT}/results/matched_leaneval/records.csv", "problem", "model"),
  "hf_census": (f"{ROOT}/results/matched_hf_records.csv.gz", "prob", "system"),
}
for tag, (path, pcol, scol) in SOURCES.items():
    if not os.path.exists(path):
        print(f"[skip] {tag}: {path} missing"); continue
    df = pd.read_csv(path)
    pm = df.groupby([pcol, scol]).median(numeric_only=True).reset_index()
    pm = pm.rename(columns={pcol: "problem", scol: "system"})
    print(f"\n######## {tag}: {pm.problem.nunique()} problems, "
          f"{pm.system.nunique()} systems, {len(pm)} cells")
    res[tag] = {}
    for m in METRICS:
        if m not in pm.columns: continue
        blk = complete_block(pm, m)
        if blk is None:
            print(f"  [{m}] no complete block"); continue
        fb = friedman_block(blk, n_perm=1000)
        vc = variance_components(pm, m, n_boot=300)
        res[tag][m] = dict(friedman=fb, variance=vc)
        print(f"  [{m:20s}] block {fb['n_problems']}x{fb['n_systems']}  "
              f"W={fb['kendall_W']:.3f} (perm p={fb['kendall_W_perm_p']:.3f}, "
              f"null W={fb['null_W_mean']:.3f})  "
              f"| unique_system={vc['unique_system']:.3f} "
              f"CI[{vc['unique_system_ci'][0]:.3f},{vc['unique_system_ci'][1]:.3f}] "
              f"perm p={vc['system_perm_p']:.3f} | unique_problem={vc['unique_problem']:.3f} "
              f"| shared={vc['shared']:.3f}")
        mr = fb["mean_ranks"]
        assert max(mr.values()) <= fb["n_systems"] + 1e-9
json.dump(res, open(f"{OUT}/matched_corrected.json", "w"), indent=1)
print(f"\nwrote {OUT}/matched_corrected.json")
