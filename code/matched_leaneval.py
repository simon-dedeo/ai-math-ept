"""
matched_leaneval.py — THE matched-theorem experiment.

The lean-eval submission store gives us the one design that separates *system*
from *problem*: the same research-level theorem proved by many different AI
systems. Everything else in this project is observational, and confounded by
which problems a system chose to attack.

Design: restrict to problems solved by >= K distinct models. Within each
problem, rank the models by a structural metric. If system identity (or its
architecture) governs proof structure, a model's rank should be consistent
across problems; if problem difficulty governs it, ranks should be noise.

Tests:
  * Friedman test over the models x problems rank matrix (non-parametric
    repeated measures) — is there ANY consistent between-model difference once
    the theorem is held fixed?
  * Kendall's W (coefficient of concordance) — how strong is that consistency?
  * Per-model mean rank, with a permutation null.
  * Within-problem paired contrasts for the metrics that matter.
"""
import glob, os, re, sys
import numpy as np
import pandas as pd
from scipy import stats

ROOT = os.path.expanduser("~/ai_math_ept")
CEN = f"{ROOT}/census/lean_eval"
OUT = f"{ROOT}/results/matched_leaneval"
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, f"{ROOT}/code")
from census import proof_bodies, proof_metrics

MIN_MODELS = 4
SMOKE = {"two_plus_two", "def_hole_example", "instance_hole_example",
         "list_append_singleton_length", "ci_regenerate_main_check"}

idx = pd.read_csv(f"{CEN}/INDEX.tsv", sep="\t")
idx = idx[idx.status == "proof"]
idx = idx[~idx.problem_id.isin(SMOKE)]
print(f"{len(idx)} proof records, {idx.problem_id.nunique()} problems, "
      f"{idx.model.nunique()} models")

# --- measure every proof file, grouping by (problem, model, record) parsed
# from the filename: <problem>__<model_slug>__<idx>[__<extra>].lean
# (INDEX.saved_path only resolves for ~1/3 of records, so we go by filename.)
from census import IDENT, STOP
NAME = re.compile(r"^(?P<prob>.+?)__(?P<model>.+?)__(?P<idx>\d+)(?:__(?P<extra>.*))?\.lean$")
groups = {}
for f in sorted(glob.glob(os.path.join(CEN, "proofs", "*.lean"))):
    m = NAME.match(os.path.basename(f))
    if not m:
        continue
    key = (m.group("prob"), m.group("model"), m.group("idx"))
    groups.setdefault(key, []).append(f)
print(f"{len(groups)} records parsed from {sum(len(v) for v in groups.values())} files")

# model slug -> the human-readable label from INDEX (slugs replace spaces etc.)
slug2model = {}
for r in idx.itertuples(index=False):
    mm = NAME.match(str(r.saved_path))
    if mm:
        slug2model[mm.group("model")] = r.model

rows = []
for (prob, mslug, ridx), files in groups.items():
    if prob in SMOKE:
        continue
    tot = dict(n_lines=0, n_tactics=0, n_have=0, n_premise_refs=0)
    prem = set()
    ok = False
    for f in files:
        try:
            src = open(f, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for name, kind, body in proof_bodies(src):
            mtr = proof_metrics(body)
            if mtr["n_premise_refs"] < 1:
                continue
            ok = True
            for k in tot:
                tot[k] += mtr[k]
        prem |= {t for t in IDENT.findall(src)
                 if t not in STOP and not t.isdigit()
                 and ("." in t or t[:1].isupper())}
    if not ok:
        continue
    rows.append(dict(problem=prob, model=slug2model.get(mslug, mslug),
                     model_slug=mslug, record=ridx,
                     n_lines=tot["n_lines"], n_tactics=tot["n_tactics"],
                     n_have=tot["n_have"], n_premise_refs=tot["n_premise_refs"],
                     n_distinct_premises=len(prem),
                     vocab_ratio=len(prem) / max(tot["n_premise_refs"], 1),
                     n_files=len(files)))

df = pd.DataFrame(rows)
df.to_csv(f"{OUT}/records.csv", index=False)
print(f"measured {len(df)} records")

# one row per (problem, model): median across that model's submissions
pm = df.groupby(["problem", "model"]).median(numeric_only=True).reset_index()
counts = pm.groupby("problem")["model"].nunique()
keep = counts[counts >= MIN_MODELS].index
pm = pm[pm.problem.isin(keep)]
print(f"\nmatched set: {pm.problem.nunique()} problems with >= {MIN_MODELS} "
      f"models, {pm.model.nunique()} models, {len(pm)} (problem,model) cells")

results = {}
for metric in ["vocab_ratio", "n_lines", "n_have", "n_distinct_premises"]:
    piv = pm.pivot(index="problem", columns="model", values=metric)
    # rank within each problem (1 = lowest); average ranks handle ties
    ranks = piv.rank(axis=1)
    # models present in enough problems for a repeated-measures test
    good = ranks.columns[ranks.notna().sum() >= 4]
    sub = ranks[good].dropna(how="any")
    if sub.shape[0] < 3 or sub.shape[1] < 3:
        # fall back: use the largest complete block
        sub = ranks[good]
        best, bestsz = None, 0
        for k in range(sub.shape[1], 2, -1):
            for cols in [sub.columns[:k]]:
                blk = sub[list(cols)].dropna()
                if blk.shape[0] >= 3 and blk.shape[0] * k > bestsz:
                    best, bestsz = blk, blk.shape[0] * k
        sub = best if best is not None else None
    if sub is None or sub.shape[0] < 3:
        print(f"\n[{metric}] not enough complete blocks for a repeated-measures test")
        continue
    arr = sub.to_numpy()
    n, k = arr.shape
    fr = stats.friedmanchisquare(*[arr[:, j] for j in range(k)])
    # Kendall's W
    W = fr.statistic / (n * (k - 1))
    print(f"\n[{metric}] complete block: {n} problems x {k} models")
    print(f"  Friedman chi2={fr.statistic:.2f}  p={fr.pvalue:.4g}   Kendall W={W:.3f}")
    mean_rank = sub.mean().sort_values()
    print("  mean rank by model (1 = lowest value):")
    for m_, v in mean_rank.items():
        print(f"    {v:5.2f}  {m_}")
    results[metric] = dict(n_problems=int(n), n_models=int(k),
                           friedman_p=float(fr.pvalue), kendall_W=float(W),
                           mean_ranks={str(a): float(b) for a, b in mean_rank.items()})

import json
json.dump(results, open(f"{OUT}/matched_tests.json", "w"), indent=1)

# --- how much variance is problem vs model?
print("\n=== variance decomposition (vocab_ratio) ===")
sub = pm.dropna(subset=["vocab_ratio"])
grand = sub.vocab_ratio.mean()
ss_tot = ((sub.vocab_ratio - grand) ** 2).sum()
ss_prob = sum(len(g) * (g.vocab_ratio.mean() - grand) ** 2
              for _, g in sub.groupby("problem"))
ss_model = sum(len(g) * (g.vocab_ratio.mean() - grand) ** 2
               for _, g in sub.groupby("model"))
print(f"  between-PROBLEM variance explained: {ss_prob/ss_tot:6.1%}")
print(f"  between-MODEL   variance explained: {ss_model/ss_tot:6.1%}")
print(f"  (n = {len(sub)} problem-model cells)")
json.dump(dict(ss_problem_frac=float(ss_prob/ss_tot),
               ss_model_frac=float(ss_model/ss_tot), n_cells=int(len(sub))),
          open(f"{OUT}/variance_decomposition.json", "w"), indent=1)
print(f"\nwrote -> {OUT}")
