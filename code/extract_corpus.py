"""
extract_corpus.py — extract proof networks from a corpus of standalone .lean
proof files by appending the EPTX extractor and elaborating each file.

Usage:
  python extract_corpus.py CORPUS_DIR OUT_DIR PROJECT_DIR \
      [--core ExtractCore.lean.tmpl] [--jobs 8] [--max-files N] [--maxnodes 12000]

CORPUS_DIR: directory with .lean files, each containing >=1 `theorem <name>`.
OUT_DIR:    where <file-stem>_{term0,term,decl}.json land.
PROJECT_DIR: a lake project whose environment provides the file's imports
             (e.g. the mathlib4 checkout, or the corpus's own pinned project).
The generated work files are placed in PROJECT_DIR/eptx_work/ and run with
`lake env lean <file>` from PROJECT_DIR.

Theorem detection: last `theorem NAME` or `lemma NAME` in the file (miniF2F
files have exactly one; files with helper lemmas -> the final one is the goal).
Files containing `sorry` are skipped.
"""
import argparse, os, re, subprocess, sys, glob, json
from concurrent.futures import ThreadPoolExecutor, as_completed

THM_RE = re.compile(r"^\s*(?:protected\s+)?(?:private\s+)?(?:theorem|lemma|problem)\s+([A-Za-z0-9_'.«»]+)",
                    re.M)


def find_theorem(src):
    names = THM_RE.findall(src)
    return names[-1] if names else None


def gen_workfile(src, thm, out_base, core_text, maxnodes):
    # ensure `import Mathlib` present at least once, imports must stay on top
    body = src.rstrip() + "\n\n"
    return (body
            + "-- ===== EPTX extraction (appended) =====\n"
            + core_text
            + f"\n#eval EPTX.extractFor `{thm} \"{out_base}\" (maxNodes := {maxnodes})\n")


def run_one(args, work_path, project_dir, env):
    try:
        r = subprocess.run(["lake", "env", "lean", work_path],
                           cwd=project_dir, env=env, capture_output=True,
                           text=True, timeout=1500)
        return r.returncode, r.stdout[-2000:] + r.stderr[-2000:]
    except subprocess.TimeoutExpired:
        return -9, "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus_dir")
    ap.add_argument("out_dir")
    ap.add_argument("project_dir")
    ap.add_argument("--core", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ExtractCore.lean.tmpl"))
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--max-files", type=int, default=0)
    ap.add_argument("--maxnodes", type=int, default=12000)
    ap.add_argument("--strip-imports", action="store_true",
                    help="replace all imports with 'import Mathlib'")
    ap.add_argument("--fix-syntax", action="store_true",
                    help="modernize old Mathlib syntax (big-operator 'in' -> '∈')")
    args = ap.parse_args()

    core_text = open(args.core).read()
    args.project_dir = os.path.abspath(args.project_dir)
    os.makedirs(args.out_dir, exist_ok=True)
    workdir = os.path.join(args.project_dir, "eptx_work")
    os.makedirs(workdir, exist_ok=True)

    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.elan/bin") + ":" + env["PATH"]

    files = sorted(glob.glob(os.path.join(args.corpus_dir, "*.lean")))
    if args.max_files:
        files = files[: args.max_files]

    jobs = []
    skipped = []
    for p in files:
        src = open(p).read()
        stem = os.path.splitext(os.path.basename(p))[0]
        if re.search(r"\bsorry\b", src):
            skipped.append((stem, "sorry"))
            continue
        thm = find_theorem(src)
        if not thm:
            skipped.append((stem, "no theorem"))
            continue
        if args.strip_imports:
            src = re.sub(r"^import .*$", "", src, flags=re.M)
            src = "import Mathlib\n" + src
        if args.fix_syntax:
            # ∑ x in s, ... -> ∑ x ∈ s, ...   (binder membership notation change)
            src = re.sub(r"([∑∏⨆⨅⋃⋂][^,\n]{0,60}?) in ", r"\1 ∈ ", src)
        out_base = os.path.abspath(os.path.join(args.out_dir, stem))
        # skip if already done
        if os.path.exists(out_base + "_decl.json"):
            continue
        wp = os.path.join(workdir, stem + "_x.lean")
        with open(wp, "w") as f:
            f.write(gen_workfile(src, thm, out_base, core_text, args.maxnodes))
        jobs.append((stem, wp))

    print(f"{len(jobs)} jobs, {len(skipped)} skipped", flush=True)
    results = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(run_one, args, wp, args.project_dir, env): stem
                for stem, wp in jobs}
        for fut in as_completed(futs):
            stem = futs[fut]
            rc, out = fut.result()
            ok = rc == 0 and "[ok]" in out
            results[stem] = "ok" if ok else "fail"
            tag = "ok " if ok else "FAIL"
            print(f"[{tag}] {stem}" + ("" if ok else f"  rc={rc} :: {out[:600]}"),
                  flush=True)

    summary = dict(total=len(files), ran=len(jobs),
                   ok=sum(1 for v in results.values() if v == "ok"),
                   fail=sum(1 for v in results.values() if v == "fail"),
                   skipped=skipped)
    with open(os.path.join(args.out_dir, "SUMMARY.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "skipped"}))


if __name__ == "__main__":
    main()
