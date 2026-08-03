#!/usr/bin/env python
"""Emit standalone one-theorem-per-file proof files into <slug>/standalone/.
Cap 2000 files per corpus, random.Random(0) sample. Adds `import Mathlib` header if absent."""
import json, os, re, sys, glob, random, shutil
import pandas as pd

BASE = os.path.expanduser("~/ai_math_ept/census")
CAP = 2000
HDR = "import Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\nopen BigOperators Real Nat Topology Rat\n\n"

def fence(txt):
    m = re.findall(r"```(?:lean4?|isabelle)?\n(.*?)```", txt, re.S)
    return m

def write(slug, items, ext=".lean", add_header=True):
    out = os.path.join(BASE, slug, "standalone")
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out, exist_ok=True)
    rng = random.Random(0)
    total = len(items)
    if total > CAP:
        items = rng.sample(items, CAP)
    n = 0
    for i, (name, body) in enumerate(items):
        if not body or not body.strip(): continue
        b = body
        if add_header and ext == ".lean" and "import Mathlib" not in b:
            b = HDR + b
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))[:80]
        with open(os.path.join(out, f"{i:05d}_{safe}{ext}"), "w") as f:
            f.write(b.rstrip() + "\n")
        n += 1
    print(f"{slug}: wrote {n} files (population {total}, cap {CAP})")
    return n, total

# ---------- STP ----------
def stp():
    rows = []
    for f in sorted(glob.glob(f"{BASE}/stp-lean-0320/data/*.parquet")):
        d = pd.read_parquet(f, columns=["prompt", "target", "tag"])
        d = d[d["tag"].astype(str).str.contains("statement")]
        rows.append(d)
    d = pd.concat(rows)
    items = []
    for i, r in enumerate(d.itertuples()):
        cs = fence(r.prompt + "```")
        stmt = cs[0] if cs else None
        if not stmt: continue
        items.append((f"stp_{i}", stmt.rstrip("\n") + "\n" + r.target))
    return write("stp-lean-0320", items)

# ---------- InternLM Lean Workbook ----------
def internlm():
    d = json.load(open(f"{BASE}/internlm-lean-workbook/lean_workbook.json"))
    items = []
    for x in d:
        pf = x.get("proof") or []
        if not pf: continue
        st = x["formal_statement"]
        st = re.sub(r"\bsorry\s*$", "", st.strip())
        body = "\n".join("  " + l for l in pf[0].strip().split("\n"))
        nm = re.search(r"theorem\s+([A-Za-z0-9_\x27]+)", st)
        items.append((nm.group(1) if nm else "thm", st.rstrip() + "\n" + body))
    return write("internlm-lean-workbook", items)

# ---------- Leanabell SFT ----------
def leanabell_sft():
    items = []
    with open(f"{BASE}/leanabell-sft/traindata_sft_without_cot.jsonl") as f:
        for i, l in enumerate(f):
            r = json.loads(l)
            cs = fence(r["prompt"] + "```")
            if not cs: continue
            body = r["output"].replace("```", "").rstrip()
            nm = re.search(r"theorem\s+([A-Za-z0-9_\x27]+)", cs[0])
            items.append((nm.group(1) if nm else f"thm{i}", cs[0].rstrip("\n") + "\n" + body))
    return write("leanabell-sft", items)

# ---------- Leanabell V2 coldstart ----------
def leanabell_v2():
    items = []
    with open(f"{BASE}/leanabell-v2-coldstart/coldstart_data.json") as f:
        for i, l in enumerate(f):
            conv = json.loads(l)["conversations"]
            asst = [c["value"] for c in conv if c["from"] != "user"]
            if not asst: continue
            cs = fence(asst[-1])
            if not cs: continue
            code = cs[-1]
            if "sorry" in code: continue
            nm = re.search(r"theorem\s+([A-Za-z0-9_\x27]+)", code)
            items.append((nm.group(1) if nm else f"thm{i}", code))
    return write("leanabell-v2-coldstart", items)

# ---------- DeepSeek-Prover-V1.5-RL runs ----------
def dsp(slug):
    d = pd.concat([pd.read_parquet(f) for f in glob.glob(f"{BASE}/{slug}/data/*.parquet")])
    d = d[d["status"] == "success"]
    items = [(r.problem_name, r.formal_statement.rstrip("\n") + "\n" + r.proof_code)
             for r in d.itertuples()]
    return write(slug, items)

# ---------- SubgoalXL / Isabelle ----------
def isabelle():
    items = []
    with open(f"{BASE}/subgoalxl-isabelle-v4/formal_proof_v4_iter3.jsonl") as f:
        for i, l in enumerate(f):
            r = json.loads(l)
            m = re.search(r"### Input\n(.*?)\n### Output", r["prompt"], re.S)
            if not m: continue
            items.append((f"isa{i}", m.group(1).strip() + "\n" + r["completion"].strip()))
    return write("subgoalxl-isabelle-v4", items, ext=".thy", add_header=False)

# ---------- LeanAgent2603 (already standalone) ----------
def leanagent():
    src = glob.glob(f"{BASE}/leanagent2603/proofs/*/*.lean")
    out = f"{BASE}/leanagent2603/standalone"
    shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    rng = random.Random(0); tot = len(src)
    if tot > CAP: src = rng.sample(src, CAP)
    for p in src:
        shutil.copy(p, os.path.join(out, os.path.basename(p)))
    print(f"leanagent2603: wrote {len(src)} files (population {tot}, cap {CAP})")
    return len(src), tot

if __name__ == "__main__":
    which = sys.argv[1:] or ["stp","internlm","leanabell_sft","leanabell_v2","dsp","isabelle","leanagent"]
    res = {}
    for w in which:
        try:
            if w == "dsp":
                for s in ["dsp15rl-minif2f-sampling","dsp15rl-proofnet-sampling","dsp15rl-minif2f-rmaxts"]:
                    res[s] = dsp(s)
            else:
                res[w] = globals()[w]()
        except Exception as e:
            print("ERR", w, type(e).__name__, e)
    json.dump({k:list(v) for k,v in res.items()}, open(f"{BASE}/_logs/extract_counts.json","w"), indent=1)
