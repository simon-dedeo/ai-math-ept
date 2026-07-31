"""Apples-to-apples: run the SAME belief model on the ETP derivation skeleton
that we run on proof networks and on Mathlib, instead of comparing a belief
curve against a percolation curve."""
import json, os, sys, zipfile
import numpy as np
sys.path.insert(0,"code")
from belief import _beliefs, beta_of_eps
DATA=os.path.expanduser("~/ai_math_ept/projects/equational_theories/data")
z=zipfile.ZipFile(f"{DATA}/2024-11-10-outcomes.json.zip")
d=json.loads(z.read(z.namelist()[0])); n=len(d["equations"])
C={}; M=np.zeros((n,n),dtype=np.int8)
for i,row in enumerate(d["outcomes"]):
    for j,s in enumerate(row): M[i,j]=C.setdefault(s,len(C)+1)
src,dst=np.where(M==C["explicit_proof_true"]); k=src!=dst; src,dst=src[k],dst[k]
# premise -> dependent : an implication A=>B means A supports B
pre_ptr=np.zeros(n+1,np.int64); np.add.at(pre_ptr,dst+1,1); pre_ptr=np.cumsum(pre_ptr)
pre_idx=src[np.argsort(dst,kind="stable")]
dep_ptr=np.zeros(n+1,np.int64); np.add.at(dep_ptr,src+1,1); dep_ptr=np.cumsum(dep_ptr)
dep_idx=dst[np.argsort(src,kind="stable")]
print("ETP skeleton: %d nodes, %d edges"%(n,len(src)))
out={}
for eps in [0.4,0.3,0.2,0.15,0.1,0.07,0.05,0.03,0.02,0.01,0.005]:
    b=_beliefs(pre_ptr,pre_idx,dep_ptr,dep_idx,beta_of_eps(eps),beta_of_eps(eps),0.75,10,10,11)
    out[eps]=float(b.mean()); print("eps=%.3f mean_belief=%.4f"%(eps,b.mean()),flush=True)
json.dump(out,open("results/study4/etp_belief.json","w"),indent=1)
