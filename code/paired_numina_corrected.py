"""Corrected paired human-vs-AI analysis, addressing review points:

  * "same length" was claimed from a NON-SIGNIFICANT Wilcoxon. Non-significance
    is not equivalence. We now run a TOST-style equivalence test with bootstrap
    CIs on the median paired difference.
  * Pairs may not be independent (shared problem source). We add a cluster
    bootstrap over `source`.
  * The premise metric is regex-derived. We report it alongside a strictly
    narrower variant (dotted identifiers only, comments and strings stripped)
    so the reader can see how sensitive the result is to the heuristic.
"""
import glob, os, re, sys, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from census import proof_bodies, proof_metrics, IDENT, STOP
from matched_stats import tost_paired, cluster_bootstrap_paired

ROOT = os.path.expanduser("~/ai_math_ept")
CMT = re.compile(r"--[^\n]*|/-.*?-/", re.S)
STR = re.compile(r'"[^"\n]*"')

def strip(src):
    return STR.sub(" ", CMT.sub(" ", src))

def measure(src):
    """Two premise counts: the original heuristic, and a strict variant that
    strips comments/strings and counts ONLY dotted identifiers (which are
    unambiguously library references, not local hypotheses or binders)."""
    if not isinstance(src, str) or not src.strip(): return None
    clean = strip(src)
    tot = dict(n_lines=0, n_tactics=0, n_have=0, n_premise_refs=0); ok = False
    for name, kind, body in proof_bodies(clean):
        m = proof_metrics(body)
        if m["n_premise_refs"] < 1: continue
        ok = True
        for k in tot: tot[k] += m[k]
    if not ok: return None
    toks = [t for t in IDENT.findall(clean) if t not in STOP and not t.isdigit()]
    loose = {t for t in toks if ("." in t or t[:1].isupper())}
    strict = {t for t in toks if "." in t and not t.startswith(".")}
    tot["premises_loose"] = len(loose)
    tot["premises_strict"] = len(strict)
    return tot

rows = []
for f in sorted(glob.glob(f"{ROOT}/census/numinamath-proof-artifacts/data/lite/shards/*.parquet")):
    cols = ["uuid","source","human_formal_proof","prover_formal_proof",
            "human_validation_status","prover_validation_status",
            "human_proof_available","prover_proof_available"]
    d = pd.read_parquet(f, columns=cols)
    d = d[(d.human_proof_available == True) & (d.prover_proof_available == True)]
    d = d[(d.human_validation_status == "valid") & (d.prover_validation_status == "valid")]
    for r in d.itertuples(index=False):
        h, a = measure(r.human_formal_proof), measure(r.prover_formal_proof)
        if h and a:
            rows.append(dict(uuid=r.uuid, source=str(r.source),
                             **{f"h_{k}": v for k, v in h.items()},
                             **{f"a_{k}": v for k, v in a.items()}))
p = pd.DataFrame(rows)
p.to_csv(f"{ROOT}/results/paired_numina_corrected.csv", index=False)
print(f"pairs: {len(p)}   distinct sources (clusters): {p.source.nunique()}")
print(f"source sizes: {p.source.value_counts().head(5).to_dict()}\n")

out = {}
print(f"{'metric':20s} {'human':>9s} {'AI':>9s} {'med diff':>9s} "
      f"{'95% CI':>18s} {'equiv?':>7s} {'Wilcoxon p':>11s}")
for m in ["n_lines","n_tactics","n_have","premises_loose","premises_strict"]:
    hc, ac = f"h_{m}", f"a_{m}"
    if hc not in p: continue
    t = tost_paired(p[hc], p[ac], bound_frac=0.10)
    out[m] = t
    print(f"{m:20s} {t['median_x']:9.2f} {t['median_y']:9.2f} "
          f"{t['median_diff']:9.2f} [{t['ci_low']:7.2f},{t['ci_high']:7.2f}] "
          f"{str(t['equivalent_within_bound']):>7s} {t['wilcoxon_p']:11.3g}")

print("\ncluster bootstrap over `source` (respects non-independence):")
for m in ["n_lines","premises_loose","premises_strict"]:
    cb = cluster_bootstrap_paired(p, f"h_{m}", f"a_{m}", "source")
    out[m + "_cluster"] = cb
    print(f"  {m:18s} median diff {cb['median_diff']:7.2f} "
          f"CI [{cb['ci_low']:7.2f},{cb['ci_high']:7.2f}]  "
          f"({cb['n_clusters']} clusters)")
json.dump(out, open(f"{ROOT}/results/paired_numina_corrected.json","w"), indent=1)
