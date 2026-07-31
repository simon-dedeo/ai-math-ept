"""Convert ExtractNetwork.lean JSON output into .edges files + manifest.

Usage: python json2edges.py IN_DIR OUT_DIR
Each JSON: {name, mode, levels, truncated, nodes, labels, edges:[[premise,dependent],...]}
Theorem node: label starting with 'THM:' (term mode) or node 0 (decl mode).
For decl mode we optionally filter compiler-internal names.
"""
import glob, json, os, re, sys

INTERNAL = re.compile(
    r"(\._|^_|\.match_|\.proof_|\.eq_def$|\.eq_\d+$|\.brecOn$|\.rec$|"
    r"\.recOn$|\.casesOn$|\.below$|\.ibelow$|\.noConfusion|_cstage|_unsafe)")


def convert(path, outdir, filter_internal=True):
    d = json.load(open(path))
    name = os.path.splitext(os.path.basename(path))[0]
    labels = d["labels"]
    mode = d.get("mode", "term")
    keep = None
    if mode == "decl" and filter_internal:
        keep = [not INTERNAL.search(l) for l in labels]
    out = os.path.join(outdir, name + ".edges")
    n_edges = 0
    with open(out, "w") as f:
        for a, b in d["edges"]:
            if keep is not None and not (keep[a] and keep[b]):
                continue
            f.write(f"{a}\t{b}\n")
            n_edges += 1
    thm = None
    if mode == "term":
        for i, l in enumerate(labels):
            if l.startswith("THM:"):
                thm = str(i)
                break
    else:
        thm = "0"
    return dict(name=name, path=name + ".edges", theorem=thm,
                mode=mode, levels=d.get("levels"),
                truncated=d.get("truncated"), n_edges=n_edges)


def main():
    indir, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    manifest = []
    for p in sorted(glob.glob(os.path.join(indir, "*.json"))):
        try:
            manifest.append(convert(p, outdir))
            print("[ok]", manifest[-1]["name"], manifest[-1]["n_edges"], "edges")
        except Exception as e:
            print("[fail]", p, e)
    with open(os.path.join(outdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
