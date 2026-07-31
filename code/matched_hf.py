"""Large-n replication of the matched-theorem experiment (Study 11) using the
HF cross-system corpus: same benchmark problem, many prover systems.
Excludes unverified raw-generation datasets by default."""
import glob, json, os, sys
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0,"code")
from census import proof_bodies, proof_metrics, IDENT, STOP

UNVERIFIED = {"ahyxie","Yuxuan13"}   # raw generations, no verification field
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

rows=[]
for rec in sorted(glob.glob("census/hf/*/records.jsonl")):
    slug=rec.split("/")[2]
    if any(u.lower() in slug.lower() for u in UNVERIFIED): continue
    d=os.path.dirname(rec)
    for line in open(rec):
        try: r=json.loads(line)
        except Exception: continue
        if not r.get("prob"): continue
        if r.get("verified") is False: continue
        f=os.path.join(d,r["file"]) if not os.path.isabs(r["file"]) else r["file"]
        if not os.path.exists(f):
            f=os.path.join(d,"standalone",os.path.basename(r["file"]))
            if not os.path.exists(f): continue
        try: src=open(f,encoding="utf-8",errors="ignore").read()
        except Exception: continue
        m=metrics(src)
        if m: rows.append(dict(system=slug, bench=r.get("bench",""), prob=r["prob"], **m))
p=pd.DataFrame(rows)
p.to_csv("results/matched_hf_records.csv.gz",index=False,compression="gzip")
print("records: %d  systems: %d  problems: %d"%(len(p),p.system.nunique(),p.prob.nunique()))
pm=p.groupby(["prob","system"]).median(numeric_only=True).reset_index()
cnt=pm.groupby("prob")["system"].nunique()
keep=cnt[cnt>=3].index; pm=pm[pm.prob.isin(keep)]
print("matched: %d problems with >=3 systems, %d cells"%(pm.prob.nunique(),len(pm)))
print()
for metric in ["vocab_ratio","n_lines","n_have","n_distinct_premises"]:
    piv=pm.pivot(index="prob",columns="system",values=metric)
    ranks=piv.rank(axis=1)
    # largest complete block: greedily keep systems with most coverage
    order=ranks.notna().sum().sort_values(ascending=False).index
    best=None;bestsz=0
    for k in range(3,min(9,len(order))+1):
        blk=ranks[list(order[:k])].dropna()
        if len(blk)>=5 and len(blk)*k>bestsz: best,bestsz=blk,len(blk)*k
    if best is None: print("[%s] no block"%metric); continue
    a=best.to_numpy(); n,k=a.shape
    fr=stats.friedmanchisquare(*[a[:,j] for j in range(k)])
    print("[%-20s] block %d problems x %d systems  Friedman p=%.3g  Kendall W=%.3f"%(metric,n,k,fr.pvalue,fr.statistic/(n*(k-1))))
print()
sub=pm.dropna(subset=["vocab_ratio"]); g=sub.vocab_ratio.mean()
sst=((sub.vocab_ratio-g)**2).sum()
ssp=sum(len(x)*(x.vocab_ratio.mean()-g)**2 for _,x in sub.groupby("prob"))
ssm=sum(len(x)*(x.vocab_ratio.mean()-g)**2 for _,x in sub.groupby("system"))
print("variance decomposition (vocab_ratio, n=%d cells): between-PROBLEM %.1f%%  between-SYSTEM %.1f%%"%(len(sub),100*ssp/sst,100*ssm/sst))
for met in ["n_lines","n_have"]:
    s2=pm.dropna(subset=[met]); g2=s2[met].mean(); t2=((s2[met]-g2)**2).sum()
    p2=sum(len(x)*(x[met].mean()-g2)**2 for _,x in s2.groupby("prob"))
    m2=sum(len(x)*(x[met].mean()-g2)**2 for _,x in s2.groupby("system"))
    print("  %-10s between-PROBLEM %.1f%%  between-SYSTEM %.1f%%"%(met,100*p2/t2,100*m2/t2))
