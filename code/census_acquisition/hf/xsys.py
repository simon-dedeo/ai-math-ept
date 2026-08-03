# -*- coding: utf-8 -*-
import os,glob,json,re,collections
BASE="/home/simon/ai_math_ept/census/hf"
# slug -> prover system label (distinct model/system families)
SYS={
"yidan-kimina":"Kimina-Prover","yidan-dsproverv2":"DeepSeek-Prover-V2","yidan-goedel":"Goedel-Prover-V2",
"ahyxie-minif2f-kimina":"Kimina-Prover","ahyxie-minif2f-kimina72b":"Kimina-Prover-72B",
"ahyxie-minif2f-goedel":"Goedel-Prover","ahyxie-minif2f-deepseek":"DeepSeek-Prover(ahyxie)",
"lukebailey-dsprover-sols":"DeepSeek-Prover-V2(LukeBailey)","lukebailey-dsprover-sols-v0":"DeepSeek-Prover-V2(LukeBailey)",
"qwen3-8b-minif2f":"Qwen3-8B","kevew-minif2f-kimina8b":"Kimina-Prover-8B",
"maoliyuan-lw-filtered":"DeepSeek-Prover-V1.5(maoliyuan)","maoliyuan-lw-standard":"DeepSeek-Prover-V1.5(maoliyuan)",
"slim205-lw-rl-minif2f":"Slim205-RL","slim205-lw-rl-v13":"Slim205-RL","slim205-lw-rl-v14":"Slim205-RL",
"slim205-lw-rl-v20":"Slim205-RL","slim205-lw-hard-goals":"Slim205-RL",
"vivacem-pset10k-kimina17b":"Kimina-Distill-1.7B","vivacem-goedel-workbook-sft":"Goedel-Prover-V1",
"cartinoe-dsproverv2":"DeepSeek-Prover-V2(Cartinoe)","cartinoe-lean-solution":"DeepSeek-Prover-V2(Cartinoe)",
"banach1729-goedel-workbook":"DeepSeek-Prover-V1.5(Lean4.27 recompiled)","leanabell-sft":"Leanabell-Prover",
"internlm-lean-workbook":"InternLM-StepProver","iiis-numinalean-sol":"IIIS-NuminaLEAN-prover",
"iiis-numinalean-artifacts":"IIIS-NuminaLEAN-prover",
"ai4math-nemotron":"NVIDIA-Nemotron","ai4math-deepseek-prover":"DeepSeek-Prover-V1",
"ai4math-goedel-pset":"Goedel-Prover(Pset)","ai4math-compfiles":"Compfiles-mixed",
"ai4math-formalmath":"FormalMATH-mixed","ai4math-hf-lean-workbook":"DeepSeek-Prover-V1.5(Goedel release)",
"ai4math-putnam2025":"Putnam2025-mixed","ai4math-lean-proofs":"ai4math-lean_proofs-mixed",
"ai4math-numinamath":"NuminaMath-LEAN-mixed",
"stp-lean":"STP","stp-lean-0320":"STP","stp-lean-sft":"STP-SFT","stp-lean-sft-eval":"STP-SFT",
"agenticcommons-formalmath":"AgenticCommons-community","rootacess-lean-sft":"rootacess-unspecified",
"epfl-sft-classic-numina":"EPFL-prover","juppy44-numinalean-hints":"Qwen3.5-9B",
"desaxce-numinalean":"NuminaMath-LEAN-filtered","yuxuan-lw-responses":"Yuxuan-LLM",
"yuxuan-lw-gptoss":"GPT-OSS","vincentoh-rrma-traces":"claude-opus-agent",
}
MINIF2F=re.compile(r"^(mathd_|amc12|amc10|aime_|imo_|induction_|numbertheory_|algebra_|unknown_|mathd)|^(imo|aime|amc)\d")
def norm(bench,prob):
    if prob is None: return None
    p=str(prob).strip()
    if "|" in p: p=p.split("|")[-1]
    b=str(bench).lower()
    pl=p.lower()
    if pl.startswith("putnam_") or "putnam" in b:
        m=re.search(r"putnam_?(\d{4})_?([ab]\d+)",pl)
        if m: return "putnam:"+m.group(1)+"_"+m.group(2)
        m=re.match(r"^([ab]\d+)_proof$",pl)
        if m: return "putnam:2025_"+m.group(1)
        return "putnam:"+pl
    if pl.startswith("exercise_") or "proofnet" in b:
        return "proofnet:"+pl
    if "minif2f" in b or MINIF2F.match(pl):
        return "minif2f:"+pl
    if pl.startswith("lean_workbook"):
        return "lean_workbook:"+pl
    if pl.startswith("goedel-pset"):
        return "goedel_pset:"+pl
    if b in ("compfiles","mobench","matholympiadbench"):
        return "olympiad:"+pl
    return None

by_prob=collections.defaultdict(lambda: collections.Counter())
slug_of=collections.defaultdict(set)
for rf in sorted(glob.glob(BASE+"/*/records.jsonl")):
    slug=rf.split("/")[-2]
    sysname=SYS.get(slug,slug)
    for l in open(rf,encoding="utf-8"):
        d=json.loads(l)
        k=norm(d.get("bench"),d.get("prob"))
        if not k: continue
        by_prob[k][sysname]+=1
        slug_of[k].add(slug)

fam=collections.Counter()
for k,c in by_prob.items(): fam[k.split(":")[0]]+=1
print("=== distinct normalised problems by benchmark family (in emitted standalone files) ===")
for k,v in fam.most_common(): print("  %-14s %d"%(k,v))

print("\n=== problems with proofs from >=3 DISTINCT systems ===")
ge3=[(k,c) for k,c in by_prob.items() if len(c)>=3]
ge3.sort(key=lambda x:(-len(x[1]),x[0]))
famc=collections.Counter(k.split(":")[0] for k,_ in ge3)
print("total:",len(ge3),"  by family:",dict(famc))
byn=collections.Counter(len(c) for _,c in by_prob.items())
print("distribution of #systems per problem:",dict(sorted(byn.items())))
print("\n--- all >=3-system problems (problem | #systems | systems:count) ---")
for k,c in ge3:
    print("%-42s %d  %s"%(k,len(c),", ".join("%s:%d"%(s,n) for s,n in c.most_common())))
json.dump({k:dict(v) for k,v in by_prob.items()},open("/home/simon/ai_math_ept/census/crosssystem_index.json","w"),indent=0)
