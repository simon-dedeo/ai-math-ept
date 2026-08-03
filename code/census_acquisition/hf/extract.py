# -*- coding: utf-8 -*-
import os,re,glob,json,random,sys,collections
import pyarrow.parquet as pq

BASE="/home/simon/ai_math_ept/census/hf"
CAP=2000
SAFE=re.compile(r"[^A-Za-z0-9._+-]")
THM=re.compile(r"^\s*(?:private\s+|protected\s+|nonrec\s+|@\[[^\]]*\]\s*)*(?:theorem|lemma|example)\s+([A-Za-z_][A-Za-z0-9_'.!?]*)",re.M)

def safe(s): return SAFE.sub("_",str(s))[:150]

def has_proof(code):
    if code is None: return False
    if "sorry" in code: return False
    if "admit" in code: return False
    if not re.search(r":=\s*(by\b|\n)",code) and ":= by" not in code: return False
    return bool(THM.search(code)) or "theorem" in code

def thmname(code):
    m=THM.search(code or "")
    return m.group(1) if m else None

def mkfile(code):
    code=code.strip("\n")
    if not re.search(r"^\s*import\s",code,re.M):
        code="import Mathlib\n\n"+code
    return code+"\n"

def read_parquets(slug,sub="**"):
    for f in sorted(glob.glob(os.path.join(BASE,slug,"raw",sub,"*.parquet"),recursive=True)):
        if "/.cache/" in f: continue
        for b in pq.ParquetFile(f).iter_batches(batch_size=2000):
            for r in b.to_pylist(): yield f,r

def read_rows(slug):
    d=os.path.join(BASE,slug,"raw")
    got=False
    for f in sorted(glob.glob(d+"/**/*.parquet",recursive=True)):
        if "/.cache/" in f: continue
        got=True
        for b in pq.ParquetFile(f).iter_batches(batch_size=2000):
            for r in b.to_pylist(): yield f,r
    if got: return
    for f in sorted(glob.glob(d+"/**/*.jsonl",recursive=True)):
        if "/.cache/" in f: continue
        got=True
        with open(f,encoding="utf-8") as fh:
            for l in fh:
                l=l.strip()
                if l:
                    try: yield f,json.loads(l)
                    except: pass
    if got: return
    for f in sorted(glob.glob(d+"/**/*.json",recursive=True)):
        if "/.cache/" in f: continue
        try: j=json.load(open(f,encoding="utf-8"))
        except: continue
        if isinstance(j,list):
            for r in j:
                if isinstance(r,dict): yield f,r

def read_jsonl(path):
    with open(path,encoding="utf-8") as fh:
        for l in fh:
            l=l.strip()
            if l:
                try: yield json.loads(l)
                except: pass

def fence(txt):
    if not txt: return None
    ms=re.findall(r"```lean4?\n(.*?)```",txt,re.S)
    if ms:
        for m in reversed(ms):
            if "theorem" in m or "lemma" in m: return m
        return ms[-1]
    i=txt.rfind("```lean4")
    if i<0: i=txt.rfind("```lean")
    if i>=0:
        j=txt.find("\n",i)
        if j>=0: return txt[j+1:]
    return None

# ---------------- handlers: yield dict(bench, prob, sample, code, verified) ----------------
H={}
def handler(name):
    def d(f):
        H[name]=f; return f
    return d

@handler("yidan-kimina")
def _(slug):
    root=os.path.join(BASE,slug,"raw")
    for gen in sorted(glob.glob(root+"/*/*/generation.jsonl")):
        d=os.path.dirname(gen); bench=gen.split("/")[-3]; pas=gen.split("/")[-2]
        vf=os.path.join(d,"verification.jsonl")
        ver={}
        if os.path.exists(vf):
            for v in read_jsonl(vf): ver[v.get("problem_id")]=bool(v.get("success"))
        for r in read_jsonl(gen):
            pid=r.get("problem_id"); ok=ver.get(pid)
            if ok is not True: continue
            yield dict(bench=bench,prob=r.get("origin_problem_id") or pid,
                       sample="%s_g%s"%(pas,r.get("generation_id")),code=r.get("full_code"),verified=True)

@handler("yidan-dsproverv2")
def _(slug):
    root=os.path.join(BASE,slug,"raw")
    for vf in sorted(glob.glob(root+"/**/verification*.json",recursive=True)):
        if "/.cache/" in vf: continue
        tag=os.path.relpath(os.path.dirname(vf),root)
        low=tag.lower()
        bench=("putnam" if "putnam" in low else "minif2f" if "minif2f" in low
               else "proofnet" if "proofnet" in low else "fate" if "fate" in low else "other")
        try: j=json.load(open(vf,encoding="utf-8"))
        except: continue
        if not isinstance(j,list): continue
        for r in j:
            cr=r.get("compilation_result") or {}
            if not (isinstance(cr,dict) and cr.get("complete")): continue
            c=r.get("code")
            if not has_proof(c): continue
            yield dict(bench=bench,prob=r.get("origin_problem_id") or r.get("name"),
                       sample="%s_g%s"%(safe(tag)[:36],r.get("generation_id")),code=c,verified=True)

@handler("yidan-goedel")
def _(slug):
    root=os.path.join(BASE,slug,"raw")
    for vf in sorted(glob.glob(root+"/**/code_compilation_repl.json",recursive=True)):
        if "/.cache/" in vf: continue
        tag=os.path.relpath(os.path.dirname(vf),root)
        low=tag.lower()
        bench=("putnam" if "putnam" in low else "proofnet" if "proofnet" in low
               else "mobench" if "mobench" in low else "fate" if "fate" in low else "minif2f")
        try: j=json.load(open(vf,encoding="utf-8"))
        except: continue
        if not isinstance(j,list): continue
        for r in j:
            cr=r.get("compilation_result") or {}
            if not (isinstance(cr,dict) and cr.get("complete")): continue
            c=r.get("code")
            if not has_proof(c): continue
            nm=r.get("name") or ""
            prob=re.sub(r"_g\d+$","",nm)
            yield dict(bench=bench,prob=prob or thmname(c),sample="%s_%s"%(safe(tag)[:36],nm.rsplit("_",1)[-1]),
                       code=c,verified=True)

def _ahyxie(slug):
    for f,r in read_parquets(slug):
        i=r["id"]; base,_,k=i.rpartition("_")
        code=r["code"]
        if not has_proof(code): continue
        # strip prose that precedes the theorem
        m=THM.search(code)
        if not m: continue
        yield dict(bench="minif2f",prob=base,sample="g"+k,code=code,verified=None)
for s in ["ahyxie-minif2f-deepseek","ahyxie-minif2f-kimina","ahyxie-minif2f-goedel","ahyxie-minif2f-kimina72b"]: H[s]=_ahyxie

def _lukebailey(slug):
    for f,r in read_parquets(slug):
        split=os.path.basename(f).split("-")[0]
        code=(r.get("header") or "")+(r.get("theorem") or "")+(r.get("proof") or "")
        if not has_proof(code): continue
        bench=("minif2f" if "minif2f" in split else "proofnet" if "proofnet" in split else "lean_workbook")
        yield dict(bench=bench,prob=r["id"],sample=split,code=code,verified=True)
for s in ["lukebailey-dsprover-sols","lukebailey-dsprover-sols-v0"]: H[s]=_lukebailey

@handler("qwen3-8b-minif2f")
def _(slug):
    for f,r in read_parquets(slug):
        c=r.get("gen_lean_file")
        if not has_proof(c): continue
        yield dict(bench="minif2f_autoformalized",prob=r.get("name"),sample="g%s"%r.get("sample_idx"),code=c,verified=None)

@handler("kevew-minif2f-kimina8b")
def _(slug):
    for f,r in read_parquets(slug):
        if not r.get("success"): continue
        c=r.get("full") or ((r.get("header") or "")+"\n"+(r.get("formal") or "")+"\n"+(r.get("proof") or ""))
        if not has_proof(c): continue
        yield dict(bench="minif2f_autoformalized",prob="kevew_%s"%r.get("id"),sample=None,code=c,verified=True)

def _maoliyuan(slug):
    for f,r in read_parquets(slug):
        c=r.get("full_proof")
        if not has_proof(c): continue
        yield dict(bench="lean_workbook",prob=r.get("theorem_name"),sample=None,code=c,verified=True)
for s in ["maoliyuan-lw-filtered","maoliyuan-lw-standard"]: H[s]=_maoliyuan

@handler("vivacem-goedel-workbook-sft")
def _vgw(slug):
    for f,r in read_parquets(slug):
        c=r.get("full_proof")
        if not has_proof(c): continue
        yield dict(bench="lean_workbook",prob=r.get("problem_id"),sample=None,code=c,verified=True)

@handler("leanabell-v2-coldstart")
def _lv2(slug):
    for f,r in read_rows(slug):
        conv=r.get("conversations")
        txt=json.dumps(conv,ensure_ascii=False) if not isinstance(conv,str) else conv
        txt=txt.replace("\\n","\n")
        c=fence(txt)
        if not c or not has_proof(c): continue
        yield dict(bench="lean_workbook",prob=thmname(c) or "unk",sample=None,code=c,verified=True)

def _slim(slug):
    for f,r in read_parquets(slug):
        if r.get("is_proved") is False: continue
        c=(r.get("theorem") or "")+(r.get("proof") or "")
        if not has_proof(c): continue
        yield dict(bench="lean_workbook",prob=r.get("problem_id"),sample=slug,code=c,verified=bool(r.get("is_proved")))
for s in ["slim205-lw-rl-minif2f","slim205-lw-rl-v13","slim205-lw-rl-v14","slim205-lw-rl-v20","slim205-lw-hard-goals"]: H[s]=_slim

@handler("vivacem-pset10k-kimina17b")
def _(slug):
    for f,r in read_parquets(slug):
        c=r.get("code")
        if not has_proof(c): continue
        yield dict(bench="goedel_pset",prob=r.get("problem_id"),sample=None,code=c,verified=True)

@handler("cartinoe-dsproverv2")
def _(slug):
    i=0
    for f,r in read_parquets(slug):
        c=fence(r.get("messages") if isinstance(r.get("messages"),str) else json.dumps(r.get("messages")))
        i+=1
        if not c or not has_proof(c): continue
        yield dict(bench="lean_workbook",prob=thmname(c) or "row%d"%i,sample=None,code=c,verified=True)

@handler("cartinoe-lean-solution")
def _(slug):
    for p in sorted(glob.glob(os.path.join(BASE,slug,"raw","**","*.lean"),recursive=True)):
        if "checkpoint" in p or "/.cache/" in p: continue
        c=open(p,encoding="utf-8",errors="replace").read()
        if not has_proof(c): continue
        yield dict(bench="lean_workbook",prob=thmname(c) or os.path.basename(p)[:-5],sample=None,code=c,verified=True)

@handler("banach1729-goedel-workbook")
def _(slug):
    for p in sorted(glob.glob(os.path.join(BASE,slug,"**","*.lean"),recursive=True)):
        if "/standalone/" in p: continue
        if "/.cache/" in p: continue
        c=open(p,encoding="utf-8",errors="replace").read()
        if not has_proof(c): continue
        yield dict(bench="lean_workbook",prob=thmname(c) or os.path.basename(p)[:-5],sample=None,code=c,verified=True)

@handler("leanabell-sft")
def _(slug):
    for p in glob.glob(os.path.join(BASE,slug,"raw","*.jsonl")):
        for r in read_jsonl(p):
            head=fence(r.get("prompt"))
            if head is None: continue
            c=head.rstrip("\n")+"\n"+(r.get("output") or "")
            if not has_proof(c): continue
            yield dict(bench="lean_workbook",prob=thmname(c) or "unk",sample=None,code=c,verified=True)

@handler("internlm-lean-workbook")
def _(slug):
    p=os.path.join(BASE,slug,"raw","lean_workbook.json")
    data=json.load(open(p,encoding="utf-8"))
    for r in data:
        pl=r.get("proof") or []
        if isinstance(pl,str): pl=[pl]
        st=(r.get("formal_statement") or "").strip()
        for i,pr in enumerate(pl):
            if not pr: continue
            if re.search(r":=\s*by\s*sorry\s*$",st):
                c=re.sub(r":=\s*by\s*sorry\s*$",":= by\n"+pr.rstrip(),st)
            else:
                c=st+"\n"+pr
            if not has_proof(c): continue
            yield dict(bench="lean_workbook",prob=thmname(c) or r.get("id"),sample="p%d"%i,code=c,verified=True)

@handler("iiis-numinalean-sol")
def _(slug):
    for p in glob.glob(os.path.join(BASE,slug,"raw","*.jsonl")):
        for r in read_jsonl(p):
            if r.get("proof_source")=="human": continue
            c=r.get("formal_proof")
            if not has_proof(c): continue
            yield dict(bench="numinamath_lean",prob=thmname(c) or r.get("uuid"),sample=None,code=c,verified=True)

@handler("iiis-numinalean-artifacts")
def _(slug):
    for f,r in read_parquets(slug):
        if r.get("prover_proof_available") is False: continue
        if r.get("prover_validation_status") not in (None,"valid","ok","success","passed","complete"): continue
        c=r.get("prover_formal_proof")
        if not has_proof(c): continue
        yield dict(bench="numinamath_lean",prob=thmname(c) or r.get("uuid"),sample=None,code=c,verified=True)

def _stp(slug):
    for f,r in read_parquets(slug):
        head=fence(r.get("prompt"))
        if head is None: continue
        c=head.rstrip("\n")+(r.get("target") or "")
        if not has_proof(c): continue
        yield dict(bench="lean_workbook_stp",prob=thmname(c) or "unk",sample=slug,code=c,verified=True)
for s in ["stp-lean","stp-lean-0320","stp-lean-sft","stp-lean-sft-eval"]: H[s]=_stp

AI4M_CFGS={"ai4math-nemotron":"nemotron_proofs","ai4math-deepseek-prover":"deepseek_prover",
 "ai4math-goedel-pset":"goedel_pset","ai4math-compfiles":"compfiles","ai4math-formalmath":"formalmath",
 "ai4math-hf-lean-workbook":"hf_lean_workbook","ai4math-putnam2025":"putnam2025","ai4math-lean-proofs":"lean_proofs",
 "ai4math-numinamath":"numinamath_lean","ai4math-formal-conjectures":"formal_conjectures"}
def _ai4m(slug):
    cfg=AI4M_CFGS[slug]
    root=os.path.join(BASE,"ai4math-lean","raw","data",cfg)
    for f in sorted(glob.glob(os.path.join(root,"*.parquet"))):
        for b in pq.ParquetFile(f).iter_batches(batch_size=2000):
            for r in b.to_pylist():
                if not r.get("has_proof"): continue
                if r.get("v4210_has_sorry"): continue
                c=r.get("lean4_code")
                if not has_proof(c): continue
                pid=r.get("id") or thmname(c)
                if isinstance(pid,str) and pid.startswith(cfg+"_"): pid=pid[len(cfg)+1:]
                yield dict(bench=cfg,prob=pid,sample=None,code=c,verified=bool(r.get("v4210_is_valid")) or None)
for _s in AI4M_CFGS: H[_s]=_ai4m

@handler("agenticcommons-formalmath")
def _(slug):
    for f,r in read_rows(slug):
        pf=r.get("lean4_proof") or ""
        st=r.get("lean4_statement") or ""
        c=pf if THM.search(pf) else (st.rstrip()+"\n"+pf)
        if not has_proof(c): continue
        yield dict(bench="agentic_commons",prob=thmname(c) or safe(r.get("submission_marker")),sample=None,
                   code=c,verified=bool(r.get("verification_level")))

@handler("rootacess-lean-sft")
def _(slug):
    for f,r in read_parquets(slug):
        c=r.get("lean_proof")
        if not has_proof(c): continue
        yield dict(bench="lean_sft",prob=thmname(c) or "unk",sample=None,code=c,verified=None)

@handler("vivacem-lw-mixnl")
def _(slug):
    for f,r in read_rows(slug):
        pl=r.get("proof")
        if isinstance(pl,str): pl=[pl]
        st=(r.get("formal_statement") or "").strip()
        for i,pr in enumerate(pl or []):
            if not pr: continue
            c=pr if THM.search(pr) else (st+"\n"+pr)
            if not has_proof(c): continue
            yield dict(bench="lean_workbook",prob=thmname(c) or "unk",sample="p%d"%i,code=c,verified=True)

@handler("epfl-sft-classic-numina")
def _(slug):
    for f,r in read_parquets(slug):
        if r.get("valid") is False: continue
        c=r.get("lean_code")
        if not has_proof(c): continue
        yield dict(bench="numinamath_lean",prob=thmname(c) or r.get("uuid"),sample=None,code=c,verified=bool(r.get("valid")))

def _numinaproof(slug):
    for f,r in read_parquets(slug):
        c=r.get("formal_proof")
        if not has_proof(c): continue
        yield dict(bench="numinamath_lean",prob=thmname(c) or r.get("uuid"),sample=None,code=c,verified=True)
for s in ["juppy44-numinalean-hints","desaxce-numinalean"]: H[s]=_numinaproof

@handler("algoveri-lean")
def _(slug):
    for f,r in read_rows(slug):
        c=r.get("lean_code")
        if not has_proof(c): continue
        yield dict(bench="algoveri",prob=r.get("task_id") or thmname(c),sample=None,code=c,verified=None)
    for pth in sorted(glob.glob(os.path.join(BASE,slug,"raw","*.lean"))):
        c=open(pth,encoding="utf-8",errors="replace").read()
        if not has_proof(c): continue
        yield dict(bench="algoveri",prob=os.path.basename(pth)[:-5],sample=None,code=c,verified=None)

def _traces(slug):
    for f,r in read_rows(slug):
        if float(r.get("reward") or 0)<1.0: continue
        msgs=r.get("messages")
        parts=[]
        if isinstance(msgs,str):
            try: msgs=json.loads(msgs)
            except: msgs=[{"content":msgs}]
        for m in (msgs or []):
            v=m.get("content") if isinstance(m,dict) else str(m)
            if isinstance(v,str): parts.append(v)
        txt="\n".join(parts)
        c=fence(txt)
        if not c:
            mm=list(re.finditer(r"(theorem [\s\S]{20,6000}?)(?:\n\n|$)",txt))
            c=mm[-1].group(1) if mm else None
        if not c or not has_proof(c): continue
        yield dict(bench=r.get("source") or "agent_traces",prob=thmname(c) or safe(r.get("session_id")),
                   sample=safe(r.get("session_id"))[:12],code=c,verified=True)
for s in ["vincentoh-erdos-opus","vincentoh-rrma-traces"]: H[s]=_traces

@handler("slim205-math-kimina15b")
def _(slug):
    for f,r in read_rows(slug):
        c=r.get("proof") or fence(r.get("llm_output"))
        if not has_proof(c): continue
        yield dict(bench="math",prob=thmname(c) or "unk",sample=None,code=c,verified=True)

def _yuxuan(slug):
    for f,r in read_parquets(slug):
        resp=r.get("model_responses")
        if isinstance(resp,str): resp=[resp]
        for i,t in enumerate(resp or []):
            c=fence(t)
            if not c or not has_proof(c): continue
            yield dict(bench="lean_workbook",prob=r.get("id"),sample="g%d"%i,code=c,verified=None)
for s in ["yuxuan-lw-responses","yuxuan-lw-gptoss"]: H[s]=_yuxuan

# ---------------- driver ----------------
def run(slug):
    os.makedirs(os.path.join(BASE,slug),exist_ok=True)
    out=os.path.join(BASE,slug,"standalone"); os.makedirs(out,exist_ok=True)
    for old in glob.glob(out+"/*.lean"): os.remove(old)
    recs=[]
    n_seen=0
    for rec in H[slug](slug):
        n_seen+=1
        if not rec.get("code"): continue
        recs.append(rec)
    total=len(recs)
    rng=random.Random(0)
    capped=False
    if total>CAP:
        # coverage-stratified sample: round-robin across (bench,prob) groups so that as many
        # distinct theorems as possible are represented; named benchmarks get priority tier 0.
        BENCH0=("minif2f","proofnet","putnam","proverbench","mobench","compfiles","matholympiad")
        groups=collections.OrderedDict()
        for r in recs:
            groups.setdefault((r["bench"],r["prob"]),[]).append(r)
        def tier(k):
            b=str(k[0]).lower()
            return 0 if any(x in b for x in BENCH0) else 1
        keys=sorted(groups)
        rng.shuffle(keys)
        keys.sort(key=tier)
        for k in keys: rng.shuffle(groups[k])
        picked=[];depth=0
        while len(picked)<CAP:
            added=False
            for k in keys:
                if len(groups[k])>depth:
                    picked.append(groups[k][depth]); added=True
                    if len(picked)>=CAP: break
            if not added: break
            depth+=1
        recs=picked; capped=True
    idx=[]
    used=collections.Counter()
    for rec in recs:
        base=safe(rec["prob"] or "unk")
        if rec.get("sample"): base=base+"__"+safe(rec["sample"])
        used[base]+=1
        if used[base]>1: base="%s__d%d"%(base,used[base])
        fn="%s__%s.lean"%(slug,base)
        with open(os.path.join(out,fn),"w",encoding="utf-8") as fh: fh.write(mkfile(rec["code"]))
        idx.append(dict(file=fn,bench=rec["bench"],prob=rec["prob"],sample=rec.get("sample"),verified=rec.get("verified")))
    with open(os.path.join(BASE,slug,"records.jsonl"),"w",encoding="utf-8") as fh:
        for r in idx: fh.write(json.dumps(r,ensure_ascii=False)+"\n")
    print(json.dumps(dict(slug=slug,n_yield=n_seen,n_with_proof=total,n_files=len(idx),capped=capped)),flush=True)

if __name__=="__main__":
    todo=sys.argv[1:] or sorted(H)
    for s in todo:
        if not (os.path.isdir(os.path.join(BASE,s,"raw")) or s in AI4M_CFGS):
            print(json.dumps(dict(slug=s,skip="not downloaded"))); continue
        try: run(s)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(json.dumps(dict(slug=s,error=str(e)[:200])))
