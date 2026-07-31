"""How much does alpha depend on xmin, and is the Coq-vs-Lean null robust across
the whole band that reproduces the paper?"""
import glob,os,json
import numpy as np, pandas as pd
from collections import defaultdict
from scipy import stats
ROOT=os.path.expanduser("~/ai_math_ept")
def hill(deg,xmin):
    x=np.asarray(deg); x=x[x>=xmin]
    if len(x)<10: return np.nan
    return 1.0+len(x)/np.sum(np.log(x/(xmin-0.5)))
def outdeg_edges(p):
    o=defaultdict(int); seen=set()
    for line in open(p):
        q=line.split()
        if len(q)<2: continue
        o[q[0]]+=1; seen.add(q[0]); seen.add(q[1])
    return np.array([o.get(v,0) for v in seen])
def outdeg_json(p):
    d=json.load(open(p)); o=np.zeros(d["nodes"],dtype=int)
    for a,b in d["edges"]: o[a]+=1
    return o
coq=[outdeg_edges(p) for p in sorted(glob.glob("networks/coq2022_edges/*.edges"))]
lean=[outdeg_edges(p) for p in sorted(glob.glob("networks/batch1_edges/*_term.edges"))]
hum=[outdeg_json(p) for p in sorted(glob.glob("networks/compfiles_human/*_term.json"))]
ai=[]
for d in ["dsv2_minif2f_test","kimina_minif2f","seed_minif2f","alphaproof_nexus"]:
    ai+=[outdeg_json(p) for p in sorted(glob.glob(f"networks/{d}/*_term.json"))]
print("n: coq=%d lean=%d human=%d ai=%d"%(len(coq),len(lean),len(hum),len(ai)))
print()
print("xmin | coq2022  lean2026   p    | human_cf   AI      p")
for xm in [5,8,9,10,11,12,13,15,20,30,50]:
    a=np.array([hill(d,xm) for d in coq]); a=a[~np.isnan(a)]
    b=np.array([hill(d,xm) for d in lean]); b=b[~np.isnan(b)]
    h=np.array([hill(d,xm) for d in hum]); h=h[~np.isnan(h)]
    i=np.array([hill(d,xm) for d in ai]); i=i[~np.isnan(i)]
    p1=stats.mannwhitneyu(a,b).pvalue if len(a)>5 and len(b)>5 else np.nan
    p2=stats.mannwhitneyu(h,i).pvalue if len(h)>5 and len(i)>5 else np.nan
    print("%4d | %6.3f  %6.3f  %7.3g | %6.3f  %6.3f  %7.3g"%(xm,a.mean(),b.mean(),p1,h.mean(),i.mean(),p2))
