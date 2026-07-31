"""
extract_corpus_ns.py — namespace-aware variant of extract_corpus.py.

Identical CLI, but the target theorem name is fully qualified by tracking
`namespace` / `section` / `end` nesting, so files like Compfiles'

    namespace Imo2019P1
    problem imo2019_p1 ... := by ...
    end Imo2019P1

resolve to `Imo2019P1.imo2019_p1` in the appended #eval.
"""
import argparse, os, re, subprocess, sys, glob, json
from concurrent.futures import ThreadPoolExecutor, as_completed

TOK_RE = re.compile(
    r"^\s*(?:@\[[^\]\n]*\]\s*)?"
    r"(?:"
    r"(?P<ns>namespace)\s+(?P<nsname>[A-Za-z0-9_'.«»]+)"
    r"|(?:public\s+|noncomputable\s+)*(?P<sec>section)(?:\s+(?P<secname>[A-Za-z0-9_'.«»]+))?\s*$"
    r"|(?P<end>end)(?:\s+(?P<endname>[A-Za-z0-9_'.«»]+))?\s*$"
    r"|(?:protected\s+|private\s+)?(?:theorem|lemma|problem)\s+(?P<thm>[A-Za-z0-9_'.«»]+)"
    r")",
    re.M)


def strip_comments(src):
    """Remove -- line comments and (nested) /- -/ block comments."""
    out = []
    i, n = 0, len(src)
    depth = 0
    while i < n:
        c = src[i]
        if depth == 0 and c == '-' and src[i:i+2] == '--':
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if c == '/' and src[i:i+2] == '/-':
            depth += 1
            i += 2
            continue
        if depth > 0 and c == '-' and src[i:i+2] == '-/':
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(c)
        elif c == '\n':
            out.append(c)  # keep line structure
        i += 1
    return ''.join(out)


def find_theorem(src):
    """Return the fully qualified name of the LAST theorem/lemma/problem."""
    src = strip_comments(src)
    stack = []  # list of ('ns', name_component) or ('sec', name_or_None)
    last = None
    for m in TOK_RE.finditer(src):
        if m.group('ns'):
            for comp in m.group('nsname').split('.'):
                stack.append(('ns', comp))
        elif m.group('sec'):
            stack.append(('sec', m.group('secname')))
        elif m.group('end'):
            name = m.group('endname')
            if not name:
                if stack:
                    stack.pop()
            elif stack and stack[-1][0] == 'sec':
                # a named end closing a (possibly dotted-name) section: pop it
                stack.pop()
            else:
                # namespace end: pops one stack entry per name component
                for _ in range(len(name.split('.'))):
                    if stack:
                        stack.pop()
        elif m.group('thm'):
            prefix = '.'.join(c for k, c in stack if k == 'ns')
            nm = m.group('thm')
            last = (prefix + '.' + nm) if prefix else nm
    return last


def gen_workfile(src, thm, out_base, core_text, maxnodes):
    body = src.rstrip() + "\n\n"
    return (body
            + "-- ===== EPTX extraction (appended) =====\n"
            + core_text
            + f"\n#eval EPTX.extractFor `{thm} \"{out_base}\" (maxNodes := {maxnodes})\n")


def run_one(args, work_path, project_dir, env):
    try:
        r = subprocess.run(["lake", "env", "lean", work_path],
                           cwd=project_dir, env=env, capture_output=True,
                           text=True, timeout=2400)
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
        out_base = os.path.abspath(os.path.join(args.out_dir, stem))
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
