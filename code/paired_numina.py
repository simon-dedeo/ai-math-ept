"""Paired human-vs-AI comparison on IDENTICAL formal statements.

NuminaMath proof artifacts give, per row: one formal_statement, a human formal
proof and a prover formal proof, each with a validation status. Restricting to
rows where BOTH are present and valid gives a within-statement paired design —
the cleanest possible test of whether machine proofs of the SAME theorem differ
structurally from human ones."""
import glob, sys, json
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0,"code")
from census import proof_bodies, proof_metrics, IDENT, STOP

def metrics(src):
    if not isinstance(src,str) or not src.strip(): return None
    tot=dict(n_lines=0,n_tactics=0,n_have=0,n_premise_refs=0); ok=False
    for name,kind,body in proof_bodies(src):
        m=proof_metrics(body)
        if m["n_premise_refs"]<1: continue
        ok=True
        for k in tot: tot[k]+=m[k]
    if not ok: return None
    prem={t for t in IDENT.findall(src) if t not in STOP and not t.isdigit() and ("." in t or t[:1].isupper())}
    tot["n_distinct_premises"]=len(prem)
    tot["vocab_ratio"]=len(prem)/max(tot["n_premise_refs"],1)
    return tot

rows=[]
for f in sorted(glob.glob("census/numinamath-proof-artifacts/data/lite/shards/*.parquet")):
    d=pd.read_parquet(f, columns=["uuid","formal_statement","human_formal_proof","prover_formal_proof",
                                  "human_validation_status","prover_validation_status",
                                  "human_proof_available","prover_proof_available","proof_source"])
    d=d[(d.human_proof_available==True)&(d.prover_proof_available==True)]
    d=d[(d.human_validation_status=="valid")&(d.prover_validation_status=="valid")]
    for r in d.itertuples(index=False):
        h=metrics(r.human_formal_proof); a=metrics(r.prover_formal_proof)
        if h and a:
            rows.append(dict(uuid=r.uuid, **{f"h_{k}":v for k,v in h.items()}, **{f"a_{k}":v for k,v in a.items()}))
p=pd.DataFrame(rows)
p.to_csv("results/paired_numina.csv",index=False)
print("paired statements with BOTH proofs valid: %d"%len(p))
print()
print("%-22s %10s %10s %12s %10s"%("metric","human","AI","Wilcoxon p","AI>human"))
for m in ["n_lines","n_tactics","n_have","n_distinct_premises","vocab_ratio","n_premise_refs"]:
    h=p[f"h_{m}"].astype(float); a=p[f"a_{m}"].astype(float)
    try: pv=stats.wilcoxon(h,a).pvalue
    except Exception: pv=float("nan")
    print("%-22s %10.3f %10.3f %12.3g %9.1f%%"%(m,h.median(),a.median(),pv,100*(a>h).mean()))
print()
# length-controlled: does the vocab gap survive within matched length?
p["hbin"]=pd.cut(p.h_n_lines,[0,5,10,20,40,1000],labels=["1-5","6-10","11-20","21-40","40+"])
print("vocab_ratio by HUMAN proof length (paired within statement):")
for b,g in p.groupby("hbin",observed=True):
    if len(g)<25: continue
    pv=stats.wilcoxon(g.h_vocab_ratio,g.a_vocab_ratio).pvalue
    print("  len %-6s n=%4d  human %.3f  AI %.3f  p=%.2g"%(b,len(g),g.h_vocab_ratio.median(),g.a_vocab_ratio.median(),pv))
