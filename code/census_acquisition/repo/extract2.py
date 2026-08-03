#!/usr/bin/env python
"""Second-round standalone extraction for repo-based and non-Lean corpora."""
import glob, json, os, random, re, shutil, sys

BASE = os.path.expanduser("~/ai_math_ept/census")
CAP = 2000
HDR = "import Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\nopen BigOperators Real Nat Topology Rat\n\n"
SAFE = re.compile(r"[^A-Za-z0-9_.-]")
counts = {}


def emit(slug, items, ext=".lean", header=True, sub=""):
    out = os.path.join(BASE, slug, "standalone", sub) if sub else os.path.join(BASE, slug, "standalone")
    if not sub:
        shutil.rmtree(os.path.join(BASE, slug, "standalone"), ignore_errors=True)
    os.makedirs(out, exist_ok=True)
    rng = random.Random(0)
    total = len(items)
    if total > CAP:
        items = rng.sample(items, CAP)
    n = 0
    for i, (name, body) in enumerate(items):
        if not body or not body.strip():
            continue
        b = body
        if header and ext == ".lean" and "import Mathlib" not in b:
            b = HDR + b
        open(os.path.join(out, "%05d_%s%s" % (i, SAFE.sub("_", str(name))[:80], ext)), "w").write(b.rstrip() + "\n")
        n += 1
    print("%s%s: wrote %d files (population %d, cap %d)" % (slug, "/" + sub if sub else "", n, total, CAP))
    counts.setdefault(slug, [0, 0])
    counts[slug][0] += n
    counts[slug][1] += total
    return n, total


def copyfiles(slug, files, sub=""):
    items = []
    for p in files:
        try:
            items.append((os.path.basename(p)[:-5], open(p, encoding="utf8", errors="replace").read()))
        except Exception:
            pass
    return emit(slug, items, sub=sub)


# --- MCB: 6 provers x 488 miniF2F x 128 attempts (attempt_1 per theorem per model) ---
def mcb():
    slug = "mcb-minif2f-6provers"
    shutil.rmtree(os.path.join(BASE, slug, "standalone"), ignore_errors=True)
    for f in sorted(glob.glob(BASE + "/" + slug + "/output/lean_code/*.json")):
        model = os.path.basename(f)[:-5]
        d = json.load(open(f))
        d = d.get(model, d)
        items = []
        for thm, atts in d.items():
            if isinstance(atts, dict):
                k = "attempt_1" if "attempt_1" in atts else sorted(atts)[0]
                items.append((thm, atts[k]))
        emit(slug, items, sub=model)


# --- repo corpora that are already one-theorem-per-file .lean ---
def repos():
    copyfiles("agenticsnz-unsorry", glob.glob(BASE + "/agenticsnz-unsorry/packages/*/library/**/*.lean", recursive=True)
              or glob.glob(BASE + "/agenticsnz-unsorry/**/library/**/*.lean", recursive=True))
    copyfiles("aristotle-putnam25", glob.glob(BASE + "/aristotle-putnam25/aristotle_outputs/**/*.lean", recursive=True))
    copyfiles("plby-lean-proofs", glob.glob(BASE + "/plby-lean-proofs/**/*.lean", recursive=True))
    copyfiles("apollo-dspv2-o3", glob.glob(BASE + "/apollo-dspv2-o3/final_proofs/**/*.lean", recursive=True))
    copyfiles("aleph-prover-proofs", glob.glob(BASE + "/aleph-prover-proofs/LI/*.lean"))
    copyfiles("axiomprover-fc", glob.glob(BASE + "/axiomprover-fc/*/solution.lean"))
    copyfiles("archon-firstproof", glob.glob(BASE + "/archon-firstproof/FirstProof/**/*.lean", recursive=True))
    copyfiles("jayyhk-erdos-lean", glob.glob(BASE + "/jayyhk-erdos-lean/**/*.lean", recursive=True))
    copyfiles("lean-eval-submissions", glob.glob(BASE + "/lean-eval-submissions/proofs/*/*.lean"))
    copyfiles("theoremllama", glob.glob(BASE + "/theoremllama/**/*.lean", recursive=True))


# --- TheoremLlama json ---
def theoremllama():
    p = BASE + "/theoremllama/eval_dataset/MiniF2F_valid_partial_withProof_commented.json"
    if not os.path.exists(p):
        print("theoremllama: file missing")
        return
    d = json.load(open(p))
    rows = d if isinstance(d, list) else list(d.values())
    items = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        body = r.get("Proof") or r.get("proof") or r.get("Lean4_code") or r.get("lean4_code") or r.get("formal_proof") or ""
        st = r.get("Statement") or r.get("formal_statement") or ""
        txt = body if "theorem" in body else (st + "\n" + body)
        items.append((r.get("Name") or r.get("name") or ("thm%d" % i), txt))
    emit("theoremllama", items)


# --- Pythagoras SFT ---
def pythagoras():
    d = json.load(open(BASE + "/pythagoras-sft/pythagoras_sft_partial_dataset.json"))
    rows = d if isinstance(d, list) else list(d.values())
    items = []
    for i, r in enumerate(rows):
        st = r.get("Formal Statement", "")
        pf = r.get("Formal Proof", "")
        txt = pf if "theorem" in pf else (st.rstrip() + "\n" + pf)
        items.append((r.get("Source", "p") + str(i), txt))
    emit("pythagoras-sft", items)


# --- MathArena arxivlean outputs ---
def matharena():
    import pandas as pd
    d = pd.concat([pd.read_parquet(f) for f in glob.glob(BASE + "/matharena-arxivlean-outputs/data/*.parquet")])
    if "correct" in d:
        d = d[d["correct"].astype(str).isin(["True", "true", "1"])]
    items = []
    for r in d.itertuples():
        a = getattr(r, "answer", "") or ""
        blocks = re.findall(r"```(?:lean4?)?\n(.*?)```", str(a), re.S)
        code = blocks[-1] if blocks else str(a)
        if "theorem" not in code and "lemma" not in code:
            continue
        items.append(("%s__%s" % (r.problem_idx, str(r.model_name)), code))
    emit("matharena-arxivlean-outputs", items)


# --- Lean-STaR (stepwise: emit thought+tactic records, not whole proofs) ---
def leanstar():
    for slug, fn in [("lean-star-base", "STaR-generated-train-1.json"),
                     ("lean-star-plus", "STaR-generated-train.json")]:
        p = BASE + "/" + slug + "/" + fn
        d = json.load(open(p))
        rows = d if isinstance(d, list) else list(d.values())
        items = [("step%d" % i, "/- INPUT\n%s\n-/\n-- OUTPUT: %s" % (r.get("input", ""), r.get("output", "")))
                 for i, r in enumerate(rows) if isinstance(r, dict)]
        emit(slug, items, header=False)


# --- Draft-Sketch-Prove Isabelle ---
def dsp():
    import tarfile
    tgz = BASE + "/dsp-isabelle/results/human_100_proofs.jsonl.tar.gz"
    dst = BASE + "/dsp-isabelle/results/_extracted"
    os.makedirs(dst, exist_ok=True)
    with tarfile.open(tgz) as t:
        t.extractall(dst)
    items = []
    for f in glob.glob(dst + "/**/*.jsonl", recursive=True):
        for i, l in enumerate(open(f)):
            r = json.loads(l)
            items.append((r.get("problem_name", "p%d" % i), r.get("proof", "")))
    emit("dsp-isabelle", items, ext=".thy", header=False)


# --- set.mm GPT-f: pair AI proof with the preserved human *OLD proof ---
def setmm():
    s = open(BASE + "/setmm-gptf/set.mm", encoding="utf8", errors="replace").read()
    ai = [m.start() for m in re.finditer(r"Proof shortened by OpenAI", s)]
    out = BASE + "/setmm-gptf/standalone"
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    n = 0
    for pos in ai:
        chunk = s[max(0, pos - 4000): pos + 4000]
        m = re.search(r"\n\s*([A-Za-z0-9_.\-]+)\s+\$p\s", s[pos:pos + 6000])
        nm = m.group(1) if m else "thm%d" % n
        open(os.path.join(out, "%02d_%s.mm" % (n, SAFE.sub("_", nm))), "w").write(chunk)
        n += 1
    print("setmm-gptf: wrote %d context windows around 'Proof shortened by OpenAI' markers" % n)
    counts["setmm-gptf"] = [n, len(ai)]


# --- Rango / Coq modeling results ---
def coqmodeling():
    slug = "coq-modeling-results"
    files = glob.glob(BASE + "/" + slug + "/results/*.json")
    shutil.rmtree(os.path.join(BASE, slug, "standalone"), ignore_errors=True)
    for f in files:
        tag = os.path.basename(f)[:-5]
        if tag not in ("rango", "tactician", "proverbot", "graph2tac", "human"):
            continue
        try:
            d = json.load(open(f))
        except Exception as e:
            print("skip", tag, e)
            continue
        rs = d.get("results", d) if isinstance(d, dict) else d
        items = []
        for i, r in enumerate(rs):
            pf = r.get("proof")
            if not pf:
                continue
            thm = (r.get("thm") or {})
            nm = "%s_%d" % (os.path.basename(str(thm.get("path", "x"))), i)
            items.append((nm, pf))
        emit(slug, items, ext=".v", header=False, sub=tag)


if __name__ == "__main__":
    fns = {"mcb": mcb, "repos": repos, "theoremllama": theoremllama, "pythagoras": pythagoras,
           "matharena": matharena, "leanstar": leanstar, "dsp": dsp, "setmm": setmm,
           "coqmodeling": coqmodeling}
    for w in (sys.argv[1:] or list(fns)):
        try:
            fns[w]()
        except Exception as e:
            print("ERR", w, type(e).__name__, e)
    json.dump(counts, open(BASE + "/_logs/extract2_counts.json", "w"), indent=1)


def numinamath():
    import pandas as pd
    slug = "numinamath-proof-artifacts"
    d = pd.concat([pd.read_parquet(f) for f in glob.glob(BASE + "/" + slug + "/data/lite/shards/*.parquet")])
    shutil.rmtree(os.path.join(BASE, slug, "standalone"), ignore_errors=True)
    for track in ("prover", "human"):
        col = track + "_formal_proof"
        sub = d[d[col].astype(str).str.len() > 20]
        items = []
        for r in sub.itertuples():
            pf = getattr(r, col)
            st = r.formal_statement or ""
            txt = pf if "theorem" in str(pf) else (str(st).rstrip() + chr(10) + str(pf))
            items.append((str(r.uuid)[:20], txt))
        emit(slug, items, sub=track)
