"""
census.py — scalable structural census of formal-proof corpora.

Two tiers, because compilation is the bottleneck:

  TIER 1 (cheap, runs on anything):  per-proof SOURCE metrics + corpus-level
    named-citation graph. No Lean required. Scales to hundreds of repos.
  TIER 2 (expensive, curated):       elaborated proof-term networks via
    ExtractNetwork.lean (see extract_corpus.py) with x_min-swept alpha.

Tier-1 per-proof metrics (all computable from source text):
    n_lines, n_tactics, n_have         proof size and step count
    n_distinct_premises                distinct library lemmas invoked
    vocab_ratio                        distinct premises / total premise refs
                                       (LOW = repetition-without-reuse, the
                                        machine-authorship signature)
    automation_share                   closer tactics / (closer + structural)
    max_repeat                         most-repeated single proof line
    dup_line_share                     share of proof lines that are duplicates
    depth_indent                       max indentation depth (proof nesting)

Corpus-level: citation graph over declarations -> Q, alpha(x_min sweep),
never-cited share, Gini, plus the belief model if the graph is big enough.

Usage:
  python census.py --roots DIR [DIR ...] --out results/census
      [--label-map census/LABELS.tsv] [--jobs 8]

Each DIR is treated as one corpus (its basename is the slug), or, with
--each-subdir, each immediate subdirectory of DIR is a corpus.
"""
from __future__ import annotations
import argparse, csv, glob, json, os, re, sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DECL = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:private\s+|protected\s+|noncomputable\s+|public\s+)*"
    r"(theorem|lemma|def|abbrev|instance|structure|class|problem)\s+"
    r"([A-Za-z_][A-Za-z0-9_'.!?«»]*)", re.M)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_'.!?]*")
TACTIC = re.compile(
    r"(?:^|\s|;|<;>|\|)\s*([a-z_][a-zA-Z0-9_']*)\s*(?:\[|\s|$)", re.M)

CLOSERS = {
    "decide", "norm_num", "omega", "aesop", "linarith", "nlinarith", "positivity",
    "polyrith", "field_simp", "ring", "ring_nf", "simp", "simpa", "simp_all",
    "tauto", "bound", "gcongr", "measurability", "continuity", "fun_prop",
    "norm_cast", "push_cast", "trivial", "native_decide", "linear_combination",
    "simp_rw", "dsimp", "abel", "group", "assumption", "contradiction", "rfl",
    "finiteness", "arith", "sorry_free", "hint", "exact?", "apply?",
}
STRUCTURAL = {
    "exact", "apply", "refine", "intro", "intros", "rw", "rwa", "induction",
    "cases", "rcases", "obtain", "constructor", "use", "have", "calc", "conv",
    "unfold", "specialize", "subst", "by_cases", "ext", "funext", "convert",
    "exact_mod_cast", "change", "show", "rintro", "let", "set", "interval_cases",
    "left", "right", "injection", "symm", "trans", "nth_rewrite", "suffices",
}
# tokens that are Lean keywords / binders, not premise references
# Comments and string literals must be removed before ANY token counting:
# human proofs routinely carry the natural-language problem statement in a
# /- ... -/ docstring, whose capitalised words were previously counted as
# library premises. This inflated human premise counts and produced a spurious
# human-vs-AI "premise deficit" (see report 5g, corrected).
COMMENT = re.compile(r"--[^\n]*|/-.*?-/", re.S)
STRLIT = re.compile(r'"[^"\n]*"')


def strip_noncode(src):
    """Remove line comments, block comments and string literals."""
    return STRLIT.sub(" ", COMMENT.sub(" ", src))


STOP = set("""theorem lemma def abbrev instance structure class problem by have
show from fun let in with this at to using exact apply intro intros refine rfl
if then else match do return where deriving open import namespace end section
variable universe noncomputable private protected partial mutual attribute
set_option macro notation infixl infixr prefix postfix example sorry
forall exists and or not iff true false Type Prop Sort""".split())


def proof_bodies(src, strip=True):
    """Yield (name, kind, body) for each declaration in a source string.
    Comments/strings are stripped by default (see strip_noncode)."""
    if strip:
        src = strip_noncode(src)
    ms = list(DECL.finditer(src))
    for i, m in enumerate(ms):
        start = m.end()
        end = ms[i + 1].start() if i + 1 < len(ms) else len(src)
        yield m.group(2), m.group(1), src[start:end]


def proof_metrics(body):
    lines = [l for l in body.split("\n") if l.strip()]
    nonempty = [l.strip() for l in lines]
    tactics = TACTIC.findall(body)
    tac = [t for t in tactics if t in CLOSERS or t in STRUCTURAL]
    cl = sum(1 for t in tac if t in CLOSERS)
    st = sum(1 for t in tac if t in STRUCTURAL)
    idents = [t for t in IDENT.findall(body)
              if t not in STOP and not t.isdigit()]
    # premise-like: dotted or capitalized identifiers (library references)
    prem = [t for t in idents if ("." in t or t[0].isupper())]
    cnt = Counter(nonempty)
    dup = sum(c for l, c in cnt.items() if c > 1 and len(l) > 8)
    return dict(
        n_lines=len(lines),
        n_tactics=len(tac),
        n_have=body.count("have "),
        n_premise_refs=len(prem),
        n_distinct_premises=len(set(prem)),
        vocab_ratio=round(len(set(prem)) / max(len(prem), 1), 4),
        automation_share=round(cl / max(cl + st, 1), 4),
        max_repeat=max(cnt.values()) if cnt else 0,
        dup_line_share=round(dup / max(len(nonempty), 1), 4),
        depth_indent=max((len(l) - len(l.lstrip()) for l in lines), default=0),
    )


def lean_files(root):
    out = []
    for p in glob.glob(f"{root}/**/*.lean", recursive=True):
        if "/.lake/" in p or "/lakefile" in p:
            continue
        out.append(p)
    return sorted(out)


def hill(deg, xmin):
    x = np.asarray([d for d in deg if d >= xmin], dtype=float)
    if len(x) < 10:
        return np.nan
    return float(1.0 + len(x) / np.sum(np.log(x / (xmin - 0.5))))


def analyze_corpus(slug, root, meta=None):
    files = lean_files(root)
    if not files:
        return None, []
    per_proof, decls, bodies = [], [], {}
    for p in files:
        try:
            src = strip_noncode(open(p, encoding="utf-8", errors="ignore").read())
        except Exception:
            continue
        if re.search(r"\bsorry\b", src):
            continue
        for name, kind, body in proof_bodies(src):
            if name not in bodies:
                decls.append(name)
                bodies[name] = body
            if kind in ("theorem", "lemma", "problem") and ":= by" in body[:400]:
                row = dict(corpus=slug, file=os.path.relpath(p, root), name=name)
                row.update(proof_metrics(body))
                per_proof.append(row)
    if not decls:
        return None, []

    # corpus-level citation graph
    S = set(decls)
    reuse = Counter()
    edges = 0
    for v, body in bodies.items():
        for tok in set(IDENT.findall(body)):
            if tok in S and tok != v:
                reuse[tok] += 1
                edges += 1
    deg = np.array([reuse.get(d, 0) for d in decls])
    row = dict(corpus=slug, n_files=len(files), n_decls=len(decls),
               n_proofs=len(per_proof), n_citation_edges=edges,
               frac_never_cited=float((deg == 0).mean()),
               mean_reuse=float(deg.mean()))
    for xm in (5, 10, 20):
        row[f"alpha_x{xm}"] = round(hill(deg, xm), 3) if not np.isnan(hill(deg, xm)) else None
    if per_proof:
        for k in ("n_lines", "n_tactics", "n_have", "n_distinct_premises",
                  "vocab_ratio", "automation_share", "dup_line_share",
                  "depth_indent"):
            vals = np.array([r[k] for r in per_proof], dtype=float)
            row[f"median_{k}"] = round(float(np.median(vals)), 4)
    if meta:
        row.update(meta)
    return row, per_proof


_META = {}


def _work(t):
    slug, root = t
    try:
        return analyze_corpus(slug, root, _META.get(slug))
    except Exception as e:
        print(f"[fail] {slug}: {e}", flush=True)
        return None, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--each-subdir", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label-map", default=None,
                    help="TSV with columns slug,<meta...> to join onto corpora")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    meta = {}
    if args.label_map and os.path.exists(args.label_map):
        with open(args.label_map) as f:
            for r in csv.DictReader(f, delimiter="\t"):
                meta[r.get("slug", "")] = {k: v for k, v in r.items()
                                           if k != "slug"}

    targets = []
    for root in args.roots:
        if args.each_subdir:
            for d in sorted(glob.glob(f"{root}/*/")):
                targets.append((os.path.basename(d.rstrip("/")), d.rstrip("/")))
        else:
            targets.append((os.path.basename(root.rstrip("/")), root.rstrip("/")))
    print(f"{len(targets)} corpora", flush=True)

    global _META
    _META = meta
    corp_rows, proof_rows = [], []
    if args.jobs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(args.jobs) as pool:
            for row, pp in pool.imap_unordered(_work, targets):
                if row:
                    corp_rows.append(row)
                    proof_rows.extend(pp)
                    print(f"[ok] {row['corpus']}: {row['n_decls']} decls, "
                          f"{row['n_proofs']} proofs, "
                          f"never_cited={row['frac_never_cited']:.3f}", flush=True)
    else:
        for t in targets:
            row, pp = _work(t)
            if row:
                corp_rows.append(row)
                proof_rows.extend(pp)

    import pandas as pd
    pd.DataFrame(corp_rows).to_csv(f"{args.out}/corpora.csv", index=False)
    pd.DataFrame(proof_rows).to_csv(f"{args.out}/proofs.csv.gz", index=False,
                                    compression="gzip")
    print(f"\nwrote {len(corp_rows)} corpora, {len(proof_rows)} proofs -> {args.out}")


if __name__ == "__main__":
    main()
