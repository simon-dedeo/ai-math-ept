#!/usr/bin/env python
"""Study 3: textual/structural comparison of human vs Gauss Lean 4 source."""
import re, os, sys, json, subprocess, statistics
from collections import Counter, defaultdict

HOME = os.path.expanduser("~")
HUMAN_SNAP = "/tmp/human_snapshot_sp"
MATHINC_SP = f"{HOME}/ai_math_ept/corpora/mathinc-sphere-packing"
STRONGPNT = f"{HOME}/ai_math_ept/corpora/mathinc-strongpnt"
HUMAN_REPO = f"{HOME}/ai_math_ept/projects/Sphere-Packing-Lean"
OUT = f"{HOME}/ai_math_ept/results/study3_source"
os.makedirs(OUT, exist_ok=True)

# ---------- identifiers / tokenizing ----------
SUB = "₀-ₜ"          # subscripts
SUP = "¹²³⁰⁴-⁹"
GRK = "Α-Ωα-ω"
ID_START = f"A-Za-z_{GRK}"
ID_CONT = f"A-Za-z0-9_'!?{SUB}{SUP}{GRK}′"
IDENT_RE = re.compile(f"[{ID_START}][{ID_CONT}]*")
NAME_RE = re.compile(f"[{ID_START}][{ID_CONT}]*(?:\\.[{ID_START}0-9][{ID_CONT}]*)*")
DOTTED_RE = re.compile(f"(?<![\\w.])([A-Z][{ID_CONT}]*(?:\\.[{ID_START}0-9][{ID_CONT}]*)+)")
DOTTEDANY_RE = re.compile(f"(?<![\\w.])([{ID_START}][{ID_CONT}]*(?:\\.[{ID_START}0-9][{ID_CONT}]*)+)")

KEYWORDS = ("theorem", "lemma", "def", "abbrev", "instance", "structure",
            "class", "inductive")
MODS = r"(?:(?:public|private|protected|noncomputable|partial|unsafe|scoped|local)\s+)*"
DECL_RE = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?" + MODS +
                     r"(theorem|lemma|def|abbrev|instance|structure|class(?:\s+inductive)?|inductive)\b\s*(.*)$")
LEAN_STOP = set("""by have show exact intro apply rw simp fun let obtain rcases cases match with
do then else end open namespace section import module public private variable theorem lemma def
abbrev instance structure class inductive where deriving fin Nat Int Real Complex Prop Type Sort
this rfl trivial simpa omega linarith ring norm at mul add sub div neg le lt eq ne of and or not
iff forall exists set map comp id val mk fst snd left right some none true false
symm trans congr refl subst elim out cast coe rec inj injeq mono aux ext""".split())

def strip_comments(text):
    """Remove -- line comments and /- -/ block comments (handles nesting)."""
    out = []
    i, n, depth = 0, len(text), 0
    while i < n:
        if depth == 0 and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/-", i):
            depth += 1; i += 2
        elif depth > 0 and text.startswith("-/", i):
            depth -= 1; i += 2
        elif depth > 0:
            out.append("\n" if text[i] == "\n" else " "); i += 1
        else:
            out.append(text[i]); i += 1
    return "".join(out)

def lean_files(root, subdirs=None):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".lake", ".git", "blueprint", "home_page")]
        for f in filenames:
            if f.endswith(".lean"):
                p = os.path.join(dirpath, f)
                files.append(os.path.relpath(p, root))
    return sorted(files)

def parse_repo(root):
    """Return list of decl dicts + per-file line counts."""
    decls, file_lines = [], {}
    for rel in lean_files(root):
        raw = open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()
        clean = strip_comments(raw)
        lines = clean.split("\n")
        file_lines[rel] = len([l for l in raw.split("\n") if l.strip()])
        # find decl start lines
        starts = []
        for i, l in enumerate(lines):
            m = DECL_RE.match(l)
            if m:
                kw = "class" if m.group(1).startswith("class") else m.group(1)
                rest = m.group(2)
                nm = NAME_RE.match(rest.strip())
                name = nm.group(0) if nm else None
                if name in ("class", "inductive"):  # 'class inductive X'
                    nm2 = NAME_RE.match(rest.strip()[len(name):].strip())
                    name = nm2.group(0) if nm2 else None
                starts.append((i, kw, name))
        boundary_re = re.compile(r"^(end\b|namespace\b|section\b|noncomputable section\b|open\b[^i]*$|variable\b|import\b|module\b|attribute\b|set_option\b|#|@\[)")
        for k, (i, kw, name) in enumerate(starts):
            j = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
            # trim at structural boundary lines
            for t in range(i + 1, j):
                if boundary_re.match(lines[t]):
                    j = t; break
            body = "\n".join(lines[i:j]).rstrip()
            nonempty = [l for l in body.split("\n") if l.strip()]
            decls.append(dict(file=rel, kw=kw, name=name, start=i,
                              n_lines=len(nonempty), text=body))
    return decls, file_lines

def split_proof(text):
    """Return proof body text after first top-level ':=' (or after final 'by'). None if none."""
    depth = 0
    i, n = 0, len(text)
    header_done = False
    while i < n - 1:
        c = text[i]
        if c in "([{⟨": depth += 1
        elif c in ")]}⟩": depth -= 1
        elif c == ":" and text[i + 1] == "=" and depth <= 0:
            return text[i + 2:]
        i += 1
    m = re.search(r"\bby\b", text)
    return text[m.end():] if m else None

def gini(xs):
    xs = sorted(xs)
    n = len(xs)
    s = sum(xs)
    if n == 0 or s == 0: return 0.0
    cum = 0.0
    for i, x in enumerate(xs, 1):
        cum += i * x
    return (2 * cum) / (n * s) - (n + 1) / n

def pctl(xs, p):
    if not xs: return 0
    xs = sorted(xs)
    k = min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))
    return xs[k]

# ---------- load corpora ----------
print("parsing human snapshot...", file=sys.stderr)
human_decls, human_fl = parse_repo(HUMAN_SNAP)
print("parsing mathinc sphere-packing...", file=sys.stderr)
mi_decls, mi_fl = parse_repo(MATHINC_SP)
print("parsing strongpnt...", file=sys.stderr)
pnt_decls, pnt_fl = parse_repo(STRONGPNT)

human_names = set(d["name"] for d in human_decls if d["name"])
human_norm = set(" ".join(d["text"].split()) for d in human_decls)

# attribution of mathinc decls
for d in mi_decls:
    norm = " ".join(d["text"].split())
    if norm in human_norm:
        d["origin"] = "retained"
    elif d["name"] and d["name"] in human_names:
        d["origin"] = "modified"
    else:
        d["origin"] = "gauss_new"
gauss_sp = [d for d in mi_decls if d["origin"] == "gauss_new"]

# file-level attribution
human_files = {rel: open(os.path.join(HUMAN_SNAP, rel), encoding="utf-8", errors="replace").read()
               for rel in lean_files(HUMAN_SNAP)}
file_attr = Counter()
file_attr_lines = Counter()
for rel in lean_files(MATHINC_SP):
    txt = open(os.path.join(MATHINC_SP, rel), encoding="utf-8", errors="replace").read()
    nl = len(txt.split("\n"))
    if rel not in human_files:
        cat = "new"
    elif " ".join(txt.split()) == " ".join(human_files[rel].split()):
        cat = "identical"
    else:
        cat = "modified"
    file_attr[cat] += 1
    file_attr_lines[cat] += nl

LAYERS = {
    "HUMAN_sp": dict(decls=human_decls, corpus=human_decls, root=HUMAN_SNAP),
    "GAUSS_sp": dict(decls=gauss_sp, corpus=mi_decls, root=MATHINC_SP),
    "GAUSS_pnt": dict(decls=pnt_decls, corpus=pnt_decls, root=STRONGPNT),
}

results = {"meta": {
    "human_snapshot_commit": "e075be668cde9878f113ed43e55b738cf9e572eb (2026-02-02)",
    "attribution": {
        "mathinc_decls_total": len(mi_decls),
        "retained_exact": sum(1 for d in mi_decls if d["origin"] == "retained"),
        "modified_name_match": sum(1 for d in mi_decls if d["origin"] == "modified"),
        "gauss_new": len(gauss_sp),
        "file_level": {k: [file_attr[k], file_attr_lines[k]] for k in file_attr},
    },
}}

for lname, L in LAYERS.items():
    decls, corpus = L["decls"], L["corpus"]
    R = {}
    # 1. census
    census = Counter(d["kw"] for d in decls)
    n_thm = census["theorem"] + census["lemma"]
    n_def = census["def"] + census["abbrev"] + census["structure"] + census["class"] + census["inductive"]
    R["census"] = dict(census)
    R["n_decls"] = len(decls)
    R["defs_to_theorems"] = round(n_def / n_thm, 4) if n_thm else None
    R["total_decl_lines"] = sum(d["n_lines"] for d in decls)

    # 2. size distributions
    sizes = [d["n_lines"] for d in decls]
    R["decl_lines"] = dict(mean=round(statistics.mean(sizes), 2), median=statistics.median(sizes),
                           p90=pctl(sizes, 90), max=max(sizes))
    proofs = []
    for d in decls:
        if d["kw"] in ("theorem", "lemma"):
            p = split_proof(d["text"])
            if p is not None:
                plines = [l for l in p.split("\n") if l.strip()]
                proofs.append(dict(name=d["name"], text=p, n_lines=len(plines),
                                   haves=len(re.findall(r"\bhave\b", p))))
    R["n_proofs"] = len(proofs)
    pl = [p["n_lines"] for p in proofs]
    hv = [p["haves"] for p in proofs]
    R["proof_lines"] = dict(mean=round(statistics.mean(pl), 2), median=statistics.median(pl),
                            p90=pctl(pl, 90), max=max(pl)) if pl else None
    R["haves_per_proof"] = dict(mean=round(statistics.mean(hv), 2), median=statistics.median(hv),
                                p90=pctl(hv, 90), max=max(hv),
                                frac_ge5=round(sum(1 for x in hv if x >= 5) / len(hv), 4)) if hv else None

    # 3. reuse / citation graph (targets = decls, citers = corpus)
    import random
    tok_cache, dot_cache = [], []
    for d in corpus:
        tok_cache.append(set(IDENT_RE.findall(d["text"])))
        dot_cache.append(set(DOTTEDANY_RE.findall(d["text"])))
    target_names = {}
    skipped_short = 0
    for idx, d in enumerate(decls):
        nm = d["name"]
        if not nm:
            skipped_short += 1; continue
        last = nm.split(".")[-1]
        use_last = len(last) >= 3 and last.lower() not in LEAN_STOP
        use_full = "." in nm
        if not (use_last or use_full):
            skipped_short += 1; continue
        target_names.setdefault(nm, []).append(d)

    bare_re_cache = {}

    def bare_re(last):
        r = bare_re_cache.get(last)
        if r is None:
            r = re.compile(f"(?<![.{ID_CONT}]){re.escape(last)}(?![{ID_CONT}])")
            bare_re_cache[last] = r
        return r

    def is_cited(nm, i):
        # bare (unqualified) reference: last component as token, not preceded by '.'
        last = nm.split(".")[-1]
        if (len(last) >= 3 and last.lower() not in LEAN_STOP and last in tok_cache[i]
                and bare_re(last).search(corpus[i]["text"])):
            return True
        # fully-qualified reference
        return "." in nm and nm in dot_cache[i]

    cite_count = {}
    for nm, ds in target_names.items():
        own = set(id(d) for d in ds)
        c = 0
        for i, d in enumerate(corpus):
            if id(d) in own: continue
            if is_cited(nm, i):
                c += 1
        cite_count[nm] = c
    ccs = list(cite_count.values())
    thm_names = set(d["name"] for d in decls if d["kw"] in ("theorem", "lemma") and d["name"] in cite_count)
    thm_ccs = [cite_count[n] for n in thm_names]
    # size-matched control: citers restricted to random sample of 1600 corpus decls
    N_CITE = 1600
    matched_fracs, matched_means = [], []
    for seed in range(5):
        rng = random.Random(seed)
        idxs = list(range(len(corpus)))
        if len(idxs) > N_CITE:
            idxs = rng.sample(idxs, N_CITE)
        fr0, mtot = 0, 0
        for nm, ds in target_names.items():
            own = set(id(d) for d in ds)
            c = sum(1 for i in idxs if id(corpus[i]) not in own and is_cited(nm, i))
            if c == 0: fr0 += 1
            mtot += c
        matched_fracs.append(fr0 / len(target_names))
        matched_means.append(mtot / len(target_names))
        if len(corpus) <= N_CITE: break
    R["reuse"] = dict(
        n_named_targets=len(cite_count), skipped=skipped_short,
        n_citers=len(corpus),
        frac_never_cited=round(sum(1 for c in ccs if c == 0) / len(ccs), 4),
        frac_thm_never_cited=round(sum(1 for c in thm_ccs if c == 0) / len(thm_ccs), 4) if thm_ccs else None,
        mean_citations=round(statistics.mean(ccs), 3), median=statistics.median(ccs),
        p90=pctl(ccs, 90), p99=pctl(ccs, 99), max=max(ccs),
        gini=round(gini(ccs), 4),
        matched1600_frac_never_cited=round(statistics.mean(matched_fracs), 4),
        matched1600_mean_citations=round(statistics.mean(matched_means), 3),
        top10=sorted(cite_count.items(), key=lambda kv: -kv[1])[:10],
    )

    # 4. duplication: 5-line shingles of normalized proof lines
    shingle_counts = Counter()
    total_shingles = 0
    have_lines = Counter()
    for p in proofs:
        norm = [" ".join(l.split()) for l in p["text"].split("\n") if l.strip()]
        for l in norm:
            if re.match(r"(?:·\s*)?have\b", l) and ":=" in l:
                have_lines[l] += 1
        for i in range(len(norm) - 4):
            shingle_counts[hash(tuple(norm[i:i + 5]))] += 1
            total_shingles += 1
    dup_inst = sum(c for c in shingle_counts.values() if c > 1)
    hl_total = sum(have_lines.values())
    hl_dup = sum(c for c in have_lines.values() if c > 1)
    R["duplication"] = dict(
        total_5line_shingles=total_shingles,
        dup_rate=round(dup_inst / total_shingles, 4) if total_shingles else None,
        distinct_shingles=len(shingle_counts),
        have_lines_total=hl_total,
        have_lines_dup_rate=round(hl_dup / hl_total, 4) if hl_total else None,
        top_have=[(c, l[:120]) for l, c in have_lines.most_common(8) if c > 2],
    )

    # 5. Mathlib-style external identifiers
    own_short = set(d["name"] for d in corpus if d["name"])
    own_roots = set()
    for d in corpus:
        for m in re.finditer(r"^\s*namespace\s+([\w.-￿]+)", d["text"], re.M):
            own_roots.add(m.group(1).split(".")[0])
    root_txt = " ".join(open(os.path.join(L["root"], f), encoding="utf-8", errors="replace").read()
                        for f in lean_files(L["root"])[:5])
    own_roots |= {"SpherePacking", "StrongPNT"}
    own_last = set(n.split(".")[-1] for n in own_short)

    def ext_idents(dd):
        ext = Counter()
        for d in dd:
            for m in DOTTED_RE.finditer(d["text"]):
                full = m.group(1)
                parts = full.split(".")
                if parts[0] in own_roots: continue
                if full in own_short or parts[-1] in own_last: continue
                ext[full] += 1
        return ext

    ext = ext_idents(decls)
    tot_lines = R["total_decl_lines"]
    # size-matched distinct vocab: subsample decls to ~16k lines (5 seeds)
    TARGET_LINES = 16182
    matched_distinct = []
    for seed in range(5):
        rng = random.Random(seed)
        dd = list(decls); rng.shuffle(dd)
        acc, cum = [], 0
        for d in dd:
            acc.append(d); cum += d["n_lines"]
            if cum >= TARGET_LINES: break
        matched_distinct.append(len(ext_idents(acc)))
        if tot_lines <= TARGET_LINES: break
    R["mathlib"] = dict(distinct=len(ext), occurrences=sum(ext.values()),
                        distinct_per_kloc=round(1000 * len(ext) / tot_lines, 2),
                        occ_per_kloc=round(1000 * sum(ext.values()) / tot_lines, 2),
                        matched16k_distinct=round(statistics.mean(matched_distinct), 1))
    results[lname] = R
    print(f"{lname}: {len(decls)} decls done", file=sys.stderr)

# 6. sorry over time (human repo)
print("sorry timeline...", file=sys.stderr)
def git(args, cwd=HUMAN_REPO):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True).stdout

log = git(["log", "--format=%H|%cd", "--date=short", "--reverse", "main"]).strip().split("\n")
by_month = {}
for line in log:
    h, dt = line.split("|")
    by_month.setdefault(dt[:7], (h, dt))  # first commit of month
timeline = []
for mon in sorted(by_month):
    h, dt = by_month[mon]
    out = git(["grep", "-c", "-w", "sorry", h, "--", "*.lean"])
    n = sum(int(l.rsplit(":", 1)[1]) for l in out.strip().split("\n") if l)
    timeline.append((mon, dt, n))
# HEAD + snapshot
for label, ref in [("snapshot_2026-02-02", "e075be668cde9878f113ed43e55b738cf9e572eb"), ("HEAD", "HEAD")]:
    out = git(["grep", "-c", "-w", "sorry", ref, "--", "*.lean"])
    n = sum(int(l.rsplit(":", 1)[1]) for l in out.strip().split("\n") if l)
    timeline.append((label, "", n))
results["sorry_timeline"] = timeline
# sorries in gauss repos
for label, root in [("mathinc_sp", MATHINC_SP), ("strongpnt", STRONGPNT)]:
    n = 0
    for f in lean_files(root):
        n += len(re.findall(r"\bsorry\b", strip_comments(open(os.path.join(root, f), encoding="utf-8", errors="replace").read())))
    results[f"sorry_{label}"] = n

with open(f"{OUT}/study3_results.json", "w") as fh:
    json.dump(results, fh, indent=1, default=str)
print(json.dumps(results, indent=1, default=str))
