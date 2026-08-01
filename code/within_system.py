"""The missing control: how much do proofs of the SAME theorem by the SAME
system differ? Between-system differences are only meaningful relative to this
within-system noise floor.

InternLM Lean-Workbook ships a LIST of alternative proofs per theorem, all from
one stepwise system -> a direct estimate of within-system variability."""
import json, sys, os
import numpy as np, pandas as pd
sys.path.insert(0,"code")
from census import proof_bodies, proof_metrics, IDENT, STOP

def metrics(src):
    tot=dict(n_lines=0,n_tactics=0,n_have=0,n_premise_refs=0); ok=False
    for name,kind,body in proof_bodies(src):
        m=proof_metrics(body)
        if m["n_premise_refs"]<1: continue
        ok=True
        for k in tot: tot[k]+=m[k]
    if not ok: return None
    prem={t for t in IDENT.findall(src) if t not in STOP and not t.isdigit() and ("." in t or t[:1].isupper())}
    tot["n_distinct_premises"]=len(prem); tot["vocab_ratio"]=len(prem)/max(tot["n_premise_refs"],1)
    return tot

d=json.load(open("census/internlm-lean-workbook/lean_workbook.json"))
print("entries:",len(d))
rows=[]; nth=0
for e in d:
    proofs=e.get("proof") or []
    if not isinstance(proofs,list) or len(proofs)<3: continue
    stmt=e.get("formal_statement") or e.get("statement") or ""
    tid=e.get("problem_id") or e.get("id") or str(nth)
    nth+=1
    for i,pr in enumerate(proofs[:12]):
        m=metrics(str(stmt)+chr(10)+str(pr))
        if m: rows.append(dict(theorem=tid, sample=i, **m))
    if nth>=3000: break
p=pd.DataFrame(rows)
print("theorems with >=3 proofs used: %d, proof samples: %d"%(p.theorem.nunique(),len(p)))
p.to_csv("results/within_system.csv.gz",index=False,compression="gzip")
print()
print("%-22s %10s %10s %10s"%("metric","within-thm SD","between-thm SD","ratio W/B"))
for m in ["n_lines","n_have","n_distinct_premises","vocab_ratio"]:
    g=p.groupby("theorem")[m]
    within=g.std().mean()
    between=g.mean().std()
    print("%-22s %10.3f %14.3f %10.3f"%(m,within,between,within/max(between,1e-9)))
print()
# variance decomposition, same form as the between-system analyses
for m in ["vocab_ratio","n_lines"]:
    gm=p[m].mean(); sst=((p[m]-gm)**2).sum()
    ssb=sum(len(x)*(x[m].mean()-gm)**2 for _,x in p.groupby("theorem"))
    print("%-14s between-THEOREM %.1f%%   within-theorem (same system) %.1f%%"%(m,100*ssb/sst,100*(1-ssb/sst)))
