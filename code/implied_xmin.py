"""For each network: (a) the KS-optimal xmin that CSN would select, (b) the xmin
that exactly reproduces the published alpha. If (b) clusters tightly -> fixed
convention; if (b) tracks (a) -> dynamic CSN selection with a different impl."""
import glob, json, os, re, warnings
import numpy as np, pandas as pd, powerlaw
warnings.filterwarnings("ignore")
ROOT=os.path.expanduser("~/ai_math_ept")
ref=pd.read_csv(f"{ROOT}/code/reference_2022.csv"); ref=ref[ref.group=="coq2022"]
by_nodes=dict(zip(ref.nodes.astype(int), zip(ref.name, ref.alpha)))

def pick(d):
    fs={}
    for p in glob.glob(f"{d}/d*.txt"):
        m=re.match(r"d(\d+)\.txt$",os.path.basename(p))
        if m: fs[int(m.group(1))]=p
    ch=None
    for k in sorted(fs):
        try: g=json.load(open(fs[k]))
        except Exception: continue
        ch=g
        if len(g)>10000: break
    return ch

def outdeg(g):
    o={k:0 for k in g}
    for k,ch in g.items():
        for c in ch: o[c]=o.get(c,0)+1
    return np.array(list(o.values()))

def hill(x,xmin):
    x=x[x>=xmin]
    if len(x)<10: return np.nan
    return 1.0+len(x)/np.sum(np.log(x/(xmin-0.5)))

rows=[]
for d in sorted(glob.glob(f"{ROOT}/original_data/ManipulateProofTrees/ProofDAGs/*/")):
    g=pick(d)
    if not g: continue
    n=len(set(list(g.keys())+[c for v in g.values() for c in v]))
    if n not in by_nodes: continue
    nm,pub=by_nodes[n]
    od=outdeg(g)
    f=powerlaw.Fit(od[od>0],discrete=True,verbose=False)
    # implied xmin: scan for the xmin whose Hill alpha is closest to published
    cands=range(2,200)
    vals=[(abs((hill(od,x) or 9)-pub), x, hill(od,x)) for x in cands]
    vals=[v for v in vals if not np.isnan(v[2])]
    best=min(vals)
    rows.append(dict(name=nm,N=n,alpha_pub=pub,ks_xmin=int(f.xmin),
                     ks_alpha=round(float(f.alpha),3),
                     implied_xmin=best[1],implied_alpha=round(best[2],3),
                     err=round(best[0],4)))
df=pd.DataFrame(rows); df.to_csv(f"{ROOT}/results/implied_xmin.csv",index=False)
print(df.sort_values("N",ascending=False).to_string(index=False))
print()
print("KS-optimal xmin: median %.0f  IQR %.0f-%.0f  range %d-%d" % (
  df.ks_xmin.median(), df.ks_xmin.quantile(.25), df.ks_xmin.quantile(.75), df.ks_xmin.min(), df.ks_xmin.max()))
print("IMPLIED   xmin: median %.0f  IQR %.0f-%.0f  range %d-%d" % (
  df.implied_xmin.median(), df.implied_xmin.quantile(.25), df.implied_xmin.quantile(.75), df.implied_xmin.min(), df.implied_xmin.max()))
print("corr(implied_xmin, ks_xmin) =", round(df[["implied_xmin","ks_xmin"]].corr().iloc[0,1],3))
print("frac implied_xmin in [8,12]:", round((df.implied_xmin.between(8,12)).mean(),3))
