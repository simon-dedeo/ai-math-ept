# -*- coding: utf-8 -*-
import os,sys,glob,json,collections,datetime
sys.path.insert(0,"/home/simon/ai_math_ept/census/scripts")
from meta import META
import pyarrow.parquet as pq
from huggingface_hub import HfApi
BASE="/home/simon/ai_math_ept/census/hf"
OUT="/home/simon/ai_math_ept/census/MANIFEST_hf.tsv"
api=HfApi()
HDR=["slug","repo_id","url","date","n_rows","n_with_proof","proof_field","multiple_proofs_per_theorem",
     "benchmark","model","verified_claim","bytes_downloaded","notes"]

def dirbytes(p):
    t=0
    for r,d,f in os.walk(p):
        if "/.cache/" in r or r.endswith("/.cache"): continue
        if os.sep+".git" in r: continue
        for x in f:
            try: t+=os.path.getsize(os.path.join(r,x))
            except: pass
    return t

def count_rows(slug):
    raw=os.path.join(BASE,slug,"raw")
    if slug.startswith("ai4math-"):
        from extract import AI4M_CFGS
        cfg=AI4M_CFGS.get(slug)
        if cfg:
            n=0
            for f in glob.glob(os.path.join(BASE,"ai4math-lean","raw","data",cfg,"*.parquet")):
                n+=pq.ParquetFile(f).metadata.num_rows
            return n
    n=0
    for f in glob.glob(raw+"/**/*.parquet",recursive=True):
        if "/.cache/" in f: continue
        try: n+=pq.ParquetFile(f).metadata.num_rows
        except: pass
    for f in glob.glob(raw+"/**/*.jsonl",recursive=True):
        if "/.cache/" in f: continue
        n+=sum(1 for _ in open(f,encoding="utf-8",errors="replace"))
    for f in glob.glob(raw+"/**/*.json",recursive=True):
        if "/.cache/" in f: continue
        try:
            j=json.load(open(f,encoding="utf-8"))
            if isinstance(j,list): n+=len(j)
        except: pass
    lf=[x for x in glob.glob(os.path.join(BASE,slug,"**","*.lean"),recursive=True) if "/standalone/" not in x]
    n+=len(lf)
    return n

stats=json.load(open("/home/simon/ai_math_ept/census/extract_stats.json")) if os.path.exists("/home/simon/ai_math_ept/census/extract_stats.json") else {}
rows=[]
for slug in sorted(META):
    repo,pf,multi,bench,model,ver,notes=META[slug]
    rid=repo.split(" ")[0]
    url="https://huggingface.co/datasets/"+rid
    try:
        di=api.dataset_info(rid); date=str(di.last_modified)[:10]
    except Exception:
        date=""
    sd=os.path.join(BASE,slug)
    by=dirbytes(sd) if os.path.isdir(sd) else 0
    if slug.startswith("ai4math-"):
        by=dirbytes(os.path.join(BASE,"ai4math-lean")) if slug=="ai4math-nemotron" else (dirbytes(sd) if os.path.isdir(sd) else 0)
    nr=count_rows(slug) if os.path.isdir(sd) or slug.startswith("ai4math-") else 0
    st=stats.get(slug,{})
    nwp=st.get("n_with_proof",0)
    nf=st.get("n_files",0)
    nt=notes
    if slug=="ai4math-nemotron": nt=(nt+"; " if nt else "")+"bytes_downloaded on this row covers the WHOLE shared charliemeyer2000/ai4math-lean download that all ai4math-* rows read from"
    if st.get("capped"): nt=(nt+"; " if nt else "")+"CAPPED: %d of %d proofs emitted (coverage-stratified random sample, seed 0: round-robin over (benchmark,theorem) groups, named-benchmark groups first)"%(nf,nwp)
    elif nf: nt=(nt+"; " if nt else "")+"%d standalone .lean files emitted"%nf
    rows.append([slug,rid,url,date,nr,nwp,pf,multi,bench,model,ver,by,nt])
with open(OUT,"w",encoding="utf-8") as fh:
    fh.write("\t".join(HDR)+"\n")
    for r in rows: fh.write("\t".join(str(x).replace("\t"," ").replace("\n"," ") for x in r)+"\n")
print("wrote",OUT,len(rows),"rows")
print("total bytes on disk:",dirbytes(BASE))
