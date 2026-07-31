"""Refit all extracted networks with the paper convention: discrete Hill MLE at fixed xmin=10."""
import glob, os, json
import numpy as np, pandas as pd
from collections import defaultdict

def hill(deg, xmin=10):
    x = np.asarray(deg); x = x[x >= xmin]
    if len(x) < 10: return np.nan
    return 1.0 + len(x)/np.sum(np.log(x/(xmin-0.5)))

def outdeg_from_edges(path):
    out = defaultdict(int); seen=set()
    for line in open(path):
        p=line.split()
        if len(p)<2: continue
        out[p[0]]+=1; seen.add(p[0]); seen.add(p[1])
    return np.array([out.get(v,0) for v in seen])

rows=[]
for grp,pat in [("coq2022","networks/coq2022_edges/*.edges"),
                ("lean2026","networks/batch1_edges/*.edges")]:
    for p in sorted(glob.glob(pat)):
        nm=os.path.basename(p)[:-6]
        mode = "term" if nm.endswith("_term") else ("decl" if nm.endswith("_decl") else "orig")
        rows.append(dict(group=grp, name=nm, mode=mode, alpha10=hill(outdeg_from_edges(p))))

def outdeg_from_json(path):
    d=json.load(open(path)); out=np.zeros(d["nodes"],dtype=int)
    for a,b in d["edges"]: out[a]+=1
    return out

for grp,d in [("ai_dsv2","networks/dsv2_minif2f_test"),("ai_kimina","networks/kimina_minif2f"),
              ("ai_seed","networks/seed_minif2f"),("human_compfiles","networks/compfiles_human"),
              ("ai_nexus","networks/alphaproof_nexus"),("ai_aristotle","networks/aristotle_imo2025"),
              ("ai_alphaproof","networks/alphaproof_imo2024"),("ai_seed_imo","networks/seed_imo2025")]:
    for p in sorted(glob.glob(f"{d}/*_term.json")):
        try: rows.append(dict(group=grp,name=os.path.basename(p)[:-10],mode="term",alpha10=hill(outdeg_from_json(p))))
        except Exception as e: pass

df=pd.DataFrame(rows); df.to_csv("results/alpha_xmin10.csv",index=False)
t=df[df["mode"].isin(["term","orig"])]
print(t.groupby("group")["alpha10"].agg(["count","mean","std","median"]).round(3).to_string())
from scipy import stats
a=t[t.group=="coq2022"].alpha10.dropna(); b=t[t.group=="lean2026"].alpha10.dropna()
print("\ncoq2022 vs lean2026 (xmin=10):  %.3f vs %.3f   MW p=%.3g" % (a.mean(), b.mean(), stats.mannwhitneyu(a,b).pvalue))
ai=t[t.group.str.startswith("ai_")].alpha10.dropna(); hu=t[t.group=="human_compfiles"].alpha10.dropna()
if len(ai)>5 and len(hu)>5:
    print("AI corpora vs human compfiles: %.3f (n=%d) vs %.3f (n=%d)  MW p=%.3g" % (ai.mean(),len(ai),hu.mean(),len(hu),stats.mannwhitneyu(ai,hu).pvalue))
