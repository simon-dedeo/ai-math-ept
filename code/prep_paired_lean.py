"""Write matched human/AI proofs of the SAME statement to standalone .lean files
so Tier-2 (elaborated proof-term network) extraction can run on both sides."""
import glob, os, re, sys
import pandas as pd
OUT_H="census/paired_numina/human"; OUT_A="census/paired_numina/ai"
os.makedirs(OUT_H,exist_ok=True); os.makedirs(OUT_A,exist_ok=True)
N=500
rows=[]
for f in sorted(glob.glob("census/numinamath-proof-artifacts/data/lite/shards/*.parquet")):
    d=pd.read_parquet(f,columns=["uuid","human_formal_proof","prover_formal_proof",
        "human_validation_status","prover_validation_status","human_proof_available","prover_proof_available"])
    d=d[(d.human_proof_available==True)&(d.prover_proof_available==True)]
    d=d[(d.human_validation_status=="valid")&(d.prover_validation_status=="valid")]
    rows.append(d)
    if sum(len(x) for x in rows)>4000: break
d=pd.concat(rows).drop_duplicates("uuid")
# prefer pairs whose proofs are non-trivial but not enormous
def nlines(s): return len(str(s).split(chr(10)))
d["hl"]=d.human_formal_proof.map(nlines); d["al"]=d.prover_formal_proof.map(nlines)
d=d[(d.hl>=8)&(d.hl<=200)&(d.al>=8)&(d.al<=200)]
d=d.sample(n=min(N,len(d)),random_state=0)
def thmname(src):
    m=re.findall(r"^\s*theorem\s+([A-Za-z_][A-Za-z0-9_\x27.]*)",str(src),re.M)
    return m[-1] if m else None
k=0
for r in d.itertuples(index=False):
    hn,an=thmname(r.human_formal_proof),thmname(r.prover_formal_proof)
    if not hn or not an: continue
    sid=str(r.uuid)[:8]
    open(f"{OUT_H}/pair_{sid}.lean","w").write(str(r.human_formal_proof))
    open(f"{OUT_A}/pair_{sid}.lean","w").write(str(r.prover_formal_proof))
    k+=1
print("wrote %d matched pairs"%k)
