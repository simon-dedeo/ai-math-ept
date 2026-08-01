"""
convert_hand_networks.py — convert the ORIGINAL hand-coded human proof networks
from the Viteri & DeDeo working archive into edge lists.

Source: /Users/simon/Desktop/OLDER_RESEARCH_ARCHIVE/SCOTT (local archive, not in
this repo). These five networks were hand-coded from original texts for the 2022
paper and were never published; they are not on GitHub or in the Elsevier
supplement.

Input format: one line per claim,
    <claim> <premise> <premise> ...
Premises may be bare labels (L2.4) or bracketed external citations ([35],
[Faltings-isogeny]). Bracketed items ARE genuine nodes — they are the external
results the proof leans on, and they are why e.g. Orlik & Strauch reaches 61
nodes from 40 lines.

Node-count reconciliation with published Table 1 (see report §1a-bis): counting
all tokens as nodes and then dropping degree-0 nodes reproduces Orlik & Strauch
exactly (61) and lands within a few percent on the others. The residual gap
reflects file-version/cleaning details of the original pipeline that we could
not reconstruct; the archive contains variant files (FLT_by_hand_NoC.txt,
herstein_cumulative_NoEx.txt) that differ slightly.

Usage:
    python convert_hand_networks.py <ARCHIVE_DIR> <OUT_DIR>
"""
import os
import re
import sys

TOK = re.compile(r"\[[^\]]+\]|[^\s\[\]]+")

FILES = {
    "wiles_flt": "FLT_by_hand.txt",
    "apollonius": "apollonius_by_hand.txt",
    "herstein": "herstein_cumulative.txt",
    "orlik_strauch": "jordan-holder.txt",     # Orlik & Strauch, Jordan-Hölder series
    "spinoza_ethics": "spinoza_by_hand.txt",  # bonus: not used in the 2022 paper
}
PUBLISHED_N = {"wiles_flt": 142, "apollonius": 446, "herstein": 280,
               "orlik_strauch": 61, "spinoza_ethics": None}


def convert(path, out):
    edges, nodes = [], set()
    for line in open(path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        toks = TOK.findall(line)
        if not toks:
            continue
        claim, prems = toks[0], toks[1:]
        nodes.add(claim)
        for p in prems:
            nodes.add(p)
            edges.append((p, claim))      # premise -> dependent
    with open(out, "w") as f:
        for a, b in edges:
            f.write(f"{a}\t{b}\n")
    return len(nodes), len(edges)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    print(f"{'network':16s} {'nodes':>6s} {'edges':>6s} {'published N':>12s}")
    for slug, fn in FILES.items():
        p = os.path.join(src, fn)
        if not os.path.exists(p):
            print(f"{slug:16s} MISSING {fn}")
            continue
        n, e = convert(p, os.path.join(dst, slug + ".edges"))
        pub = PUBLISHED_N[slug]
        print(f"{slug:16s} {n:6d} {e:6d} {str(pub):>12s}")


if __name__ == "__main__":
    main()
