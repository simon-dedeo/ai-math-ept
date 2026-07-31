"""
convert_coq_dags.py — convert the original Viteri-DeDeo ProofDAGs (node ->
children JSON, children = premises) into .edges files (premise\tdependent),
selecting per theorem the expansion depth the paper used: the first dN whose
node count exceeds 10,000, else the deepest available.

Usage: python convert_coq_dags.py ~/ai_math_ept/original_data/ManipulateProofTrees/ProofDAGs OUT_DIR
"""
import glob, json, os, re, sys


def convert_one(theorem_dir, outdir):
    name = os.path.basename(theorem_dir.rstrip("/"))
    depth_files = {}
    for p in glob.glob(os.path.join(theorem_dir, "d*.txt")):
        m = re.match(r"d(\d+)\.txt$", os.path.basename(p))
        if m:
            depth_files[int(m.group(1))] = p
    if not depth_files:
        return None
    # node counts per depth (cheap: count keys)
    chosen = None
    for d in sorted(depth_files):
        try:
            g = json.load(open(depth_files[d]))
        except Exception:
            continue
        chosen = (d, g)
        if len(g) > 10000:
            break
    if chosen is None:
        return None
    d, g = chosen
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    out = os.path.join(outdir, f"{safe}.edges")
    n_edges = 0
    with open(out, "w") as f:
        for parent, children in g.items():
            for ch in children:
                f.write(f"{ch}\t{parent}\n")   # premise -> dependent
                n_edges += 1
    # theorem node: a node that is nobody's child (roots); pick the one with
    # largest subtree implicitly -> let run_analysis's heuristic decide.
    return dict(name=safe, path=f"{safe}.edges", nodes=len(g),
                depth_used=d, n_edges=n_edges)


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    manifest = []
    for td in sorted(glob.glob(os.path.join(src, "*/"))):
        try:
            r = convert_one(td, outdir)
            if r:
                manifest.append(r)
                print(f"[ok] {r['name']}: {r['nodes']} nodes @ depth {r['depth_used']}")
        except Exception as e:
            print(f"[fail] {td}: {e}")
    with open(os.path.join(outdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"{len(manifest)} networks converted")


if __name__ == "__main__":
    main()
