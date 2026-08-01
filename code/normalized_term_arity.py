"""Normalize Coq and Lean proof values to a common constructor schema.

The historical CoqAST representation uses variadic ``App`` constructors and
retains binder names as children.  Lean's kernel ``Expr.app`` is binary and its
binder names are metadata rather than expressions.  Native in-degree is thus
not comparable across the two extractors.

This script constructs a deliberately small common schema for root proof
values (no recursive library expansion):

  * application is binary in both systems;
  * Lambda/Prod and Lam/Pi retain only domain and body;
  * LetIn/Let retain type, value, and body;
  * atoms remain leaves;
  * system-specific constructors are retained for an all-node sensitivity,
    but the primary positive-arity sample is App/Lam/Pi/Let only.

Coq terms come from the archived raw ``ProofTrees/*/d1.txt`` files.  Lean proof
values are reconstructed from the ordered edge stream in existing JSON files;
the first child of the virtual THM node is the proof value, and constants are
held at the frontier even in expanded files.

Outputs:
  results/normalized_term_arity/per_network.csv
  results/normalized_term_arity/summary.json
  results/normalized_term_arity/constructor_counts.csv
  report/standalone/normalized_arity_numbers.tex
  report/standalone/figures/normalized_indegree_check.{pdf,png}
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from poisson_indegree_appendix import (
    FIG,
    ROOT,
    SEED,
    analyse_graph,
    bh_rejections,
    calibration_rows,
    corpus_summary,
)


OUT = ROOT / "results" / "normalized_term_arity"
RAW_COQ = ROOT / "original_data" / "ManipulateProofTrees" / "ProofTrees"
CORE = {"App", "Lam", "Pi", "Let"}
COQ_CONSTRUCTORS = ("App", "Lambda", "Prod", "LetIn", "Case", "Cast", "Fix")


@dataclass
class NormalizedDAG:
    labels: list[str] = field(default_factory=list)
    children: list[tuple[int, ...]] = field(default_factory=list)
    ids: dict[tuple[str, tuple[int, ...], str], int] = field(default_factory=dict)
    root: int | None = None

    def atom(self, value: str) -> int:
        key = ("Atom", (), value)
        if key not in self.ids:
            self.ids[key] = len(self.labels)
            self.labels.append("Atom")
            self.children.append(())
        return self.ids[key]

    def node(self, label: str, children: list[int] | tuple[int, ...]) -> int:
        ordered = tuple(children)
        key = (label, ordered, "")
        if key not in self.ids:
            self.ids[key] = len(self.labels)
            self.labels.append(label)
            self.children.append(ordered)
        return self.ids[key]


def parse_sexpressions(text: str) -> list:
    """Parse the simple parenthesized CoqAST export without evaluating it."""
    roots: list = []
    stack: list[list] = []
    for match in re.finditer(r"\(|\)|[^\s()]+", text):
        token = match.group(0)
        if token == "(":
            stack.append([])
        elif token == ")":
            if not stack:
                raise ValueError("unbalanced closing parenthesis")
            value = stack.pop()
            (stack[-1] if stack else roots).append(value)
        else:
            (stack[-1] if stack else roots).append(token)
    if stack:
        raise ValueError("unbalanced opening parenthesis")
    return roots


def coq_path(name: str) -> Path:
    direct = RAW_COQ / name / "d1.txt"
    if direct.exists():
        return direct
    if name == "euclid_book":
        return RAW_COQ / "euclid_book_d1.txt"
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    matches = [p / "d1.txt" for p in RAW_COQ.iterdir()
               if p.is_dir() and re.sub(r"[^A-Za-z0-9_]+", "_", p.name) == safe]
    if len(matches) != 1:
        raise FileNotFoundError(f"could not uniquely map Coq tree {name}: {matches}")
    return matches[0]


def normalize_coq_term(term: list | str) -> NormalizedDAG:
    dag = NormalizedDAG()
    values: dict[int, int] = {}
    stack: list[tuple[list | str, bool]] = [(term, False)]
    while stack:
        current, visited = stack.pop()
        if not isinstance(current, list):
            values[id(current)] = dag.atom(str(current))
            continue
        if not current:
            values[id(current)] = dag.atom("EMPTY")
            continue
        if not visited:
            stack.append((current, True))
            for child in reversed(current[1:]):
                stack.append((child, False))
            continue
        tag = str(current[0])
        kids = [values[id(child)] for child in current[1:]]
        if tag == "App" and len(kids) >= 2:
            value = kids[0]
            for argument in kids[1:]:
                value = dag.node("App", [value, argument])
        elif tag == "Lambda" and len(kids) >= 3:
            value = dag.node("Lam", kids[-2:])
        elif tag == "Prod" and len(kids) >= 3:
            value = dag.node("Pi", kids[-2:])
        elif tag == "LetIn" and len(kids) >= 4:
            value = dag.node("Let", kids[-3:])
        elif tag == "Cast" and len(kids) >= 2:
            # Drop the cast-kind tag while retaining expression and type.
            value = dag.node("Cast", [kids[0], kids[-1]])
        elif tag in ("Definition", "Axiom") and kids:
            value = kids[-1]
        else:
            value = dag.node(f"Coq:{tag}", kids)
        values[id(current)] = value
    dag.root = values[id(term)]
    return dag


def coq_root_dag(name: str) -> NormalizedDAG:
    roots = parse_sexpressions(coq_path(name).read_text())
    definitions = [tree for tree in roots if isinstance(tree, list) and
                   tree and tree[0] in ("Definition", "Axiom")]
    if len(definitions) != 1 or len(definitions[0]) < 3:
        raise ValueError(f"{name}: expected one top-level definition, got {len(definitions)}")
    return normalize_coq_term(definitions[0][2])


def lean_root_dag(path: Path) -> NormalizedDAG:
    source = json.loads(path.read_text())
    n = int(source["nodes"])
    ordered_children: list[list[int]] = [[] for _ in range(n)]
    for child, parent in source["edges"]:
        ordered_children[int(parent)].append(int(child))
    theorem_nodes = [i for i, label in enumerate(source["labels"])
                     if label.startswith("THM:")]
    if len(theorem_nodes) != 1 or len(ordered_children[theorem_nodes[0]]) < 1:
        raise ValueError(f"{path}: missing unique virtual theorem root")
    proof_root = ordered_children[theorem_nodes[0]][0]
    dag = NormalizedDAG()
    values: dict[int, int] = {}
    stack: list[tuple[int, bool]] = [(proof_root, False)]
    while stack:
        node_id, visited = stack.pop()
        if node_id in values:
            continue
        label = source["labels"][node_id]
        # Expanded-term files attach definitions below constants.  The common
        # schema deliberately holds constants at the root-proof frontier.
        children = [] if label.startswith("C:") else ordered_children[node_id]
        if not visited and children:
            stack.append((node_id, True))
            for child in reversed(children):
                if child not in values:
                    stack.append((child, False))
            continue
        kids = [values[child] for child in children]
        if label == "App":
            value = dag.node("App", kids)
        elif label == "Lam":
            value = dag.node("Lam", kids)
        elif label == "Pi":
            value = dag.node("Pi", kids)
        elif label == "Let":
            value = dag.node("Let", kids)
        elif label == "MData" and kids:
            value = kids[-1]
        elif label.startswith("Proj:"):
            value = dag.node("Proj", kids)
        elif kids:
            value = dag.node(f"Lean:{label.split(':', 1)[0]}", kids)
        else:
            value = dag.atom(label)
        values[node_id] = value
    dag.root = values[proof_root]
    return dag


def arities(dag: NormalizedDAG, core_only: bool) -> tuple[np.ndarray, int, int, Counter]:
    degrees = np.asarray([len(set(children)) for children in dag.children], dtype=np.int64)
    labels = np.asarray(dag.labels, dtype=object)
    if core_only:
        positive_mask = np.isin(labels, list(CORE)) & (degrees > 0)
        # Leaves plus shared constructors define the projected common schema;
        # system-specific positive constructors are omitted rather than forced
        # into a false correspondence.
        included = (degrees == 0) | np.isin(labels, list(CORE))
    else:
        positive_mask = degrees > 0
        included = np.ones(len(degrees), dtype=bool)
    positive = degrees[positive_mask]
    total = int(included.sum())
    zero = int(np.sum(included & (degrees == 0)))
    constructors = Counter(labels[positive_mask].tolist())
    return positive, total, zero, constructors


def native_summary(degrees: list[int], labels: list[str]) -> dict:
    positive = [(degree, label) for degree, label in zip(degrees, labels) if degree > 0]
    app = [degree for degree, label in positive if label == "App"]
    return {
        "positive_nodes": len(positive),
        "positive_mean": float(np.mean([degree for degree, _ in positive])),
        "degree_two_share": float(np.mean([degree == 2 for degree, _ in positive])),
        "application_share_of_positive": float(len(app) / len(positive)),
        "application_mean_degree": float(np.mean(app)),
    }


def native_lean_diagnostic(paths: list[Path]) -> dict:
    degrees: list[int] = []
    labels: list[str] = []
    for path in paths:
        source = json.loads(path.read_text())
        incoming = [set() for _ in range(int(source["nodes"]))]
        for child, parent in source["edges"]:
            incoming[int(parent)].add(int(child))
        degrees.extend(map(len, incoming))
        labels.extend("App" if label == "App" else label for label in source["labels"])
    return native_summary(degrees, labels)


def native_coq_diagnostic() -> dict:
    degrees: list[int] = []
    labels: list[str] = []
    for path in sorted((ROOT / "networks" / "coq2022_edges").glob("*.edges")):
        incoming: dict[str, set[str]] = {}
        nodes: set[str] = set()
        for line in path.read_text().splitlines():
            fields = line.split()
            if len(fields) < 2:
                continue
            child, parent = fields[:2]
            nodes.update((child, parent))
            incoming.setdefault(parent, set()).add(child)
        for node in nodes:
            degrees.append(len(incoming.get(node, ())))
            labels.append(next((name for name in COQ_CONSTRUCTORS
                                if node.startswith(name)), "Other"))
    return native_summary(degrees, labels)


def add_analysis(rows: list[dict], plot_records: dict[str, list[dict]],
                 constructor_rows: list[dict], corpus: str, name: str,
                 dag: NormalizedDAG, counter: int) -> int:
    for core_only, schema in ((False, "all normalized constructors"),
                              (True, "shared binary core")):
        x, total, zero, constructors = arities(dag, core_only)
        row, record = analyse_graph(corpus, name, x, total, zero, SEED + counter)
        row["schema"] = schema
        rows.append(row)
        if core_only:
            plot_records[corpus].append(record)
        for label, count in constructors.items():
            constructor_rows.append({"corpus": corpus, "name": name,
                                     "schema": schema, "constructor": label,
                                     "positive_nodes": count})
        counter += 1
    return counter


def write_figure(calibration: pd.DataFrame) -> None:
    corpora = ["Coq root values", "Human Lean root values",
               "Matched human Lean root values", "Matched AI Lean root values"]
    colors = {"empirical": "#222222", "poisson": "#B24C3D", "cmp": "#294C60"}
    labels = {"empirical": "observed", "poisson": "Poisson", "cmp": "COM-Poisson"}
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8})
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.8), sharex=True)
    for ax, corpus in zip(axes.flat, corpora):
        data = calibration[calibration.corpus == corpus]
        degrees = list(data[data.model == "empirical"].degree)
        xpos = np.arange(len(degrees))
        for model in ("empirical", "poisson", "cmp"):
            values = data[data.model == model].probability.to_numpy()
            ax.plot(xpos, values, marker="o", ms=3, lw=1.2,
                    color=colors[model], label=labels[model])
        ax.set_title(corpus)
        ax.set_xticks(xpos, degrees)
        ax.set_yscale("log")
        ax.set_ylim(1e-5, 1.2)
        ax.grid(alpha=.18, lw=.5)
    axes[0, 0].set_ylabel("mean probability per proof")
    axes[1, 0].set_ylabel("mean probability per proof")
    axes[1, 0].set_xlabel("positive in-degree")
    axes[1, 1].set_xlabel("positive in-degree")
    axes[0, 0].legend(frameon=False, ncol=3, loc="lower center",
                      bbox_to_anchor=(1.08, 1.02))
    fig.tight_layout(rect=(0, 0, 1, .96))
    fig.savefig(FIG / "normalized_indegree_check.pdf", bbox_inches="tight")
    fig.savefig(FIG / "normalized_indegree_check.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_macros(summary: dict) -> None:
    groups = summary["shared_binary_core"]
    text = "% Generated by code/normalized_term_arity.py\n"
    specs = [
        ("NormCoq", "Coq root values"),
        ("NormLean", "Human Lean root values"),
        ("NormHuman", "Matched human Lean root values"),
        ("NormAI", "Matched AI Lean root values"),
    ]
    for macro, corpus in specs:
        group = groups[corpus]
        n = group["n_networks"]
        text += f"\\newcommand{{\\{macro}N}}{{{n}}}\n"
        text += f"\\newcommand{{\\{macro}DegreeTwo}}{{{group['median_fraction_degree_2']:.4f}}}\n"
        text += f"\\newcommand{{\\{macro}Mean}}{{{group['median_positive_mean']:.3f}}}\n"
        text += f"\\newcommand{{\\{macro}Reject}}{{{group['poisson_rejected_bh_0_05']}/{n}}}\n"
        text += f"\\newcommand{{\\{macro}ZIPReject}}{{{group['zip_rejected_bh_0_05']}/{n}}}\n"
    (ROOT / "report" / "standalone" / "normalized_arity_numbers.tex").write_text(text)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    constructor_rows: list[dict] = []
    plot_records = {name: [] for name in (
        "Coq root values", "Human Lean root values",
        "Matched human Lean root values", "Matched AI Lean root values")}
    counter = 0
    exclusions: dict[str, list[dict]] = {name: [] for name in plot_records}

    manifest = json.loads((ROOT / "networks" / "coq2022_edges" / "manifest.json").read_text())
    for i, item in enumerate(manifest, start=1):
        if item["name"] == "euclid_book":
            exclusions["Coq root values"].append({
                "name": item["name"], "reason": "hand-coded dependency list has no root proof AST"})
            continue
        dag = coq_root_dag(item["name"])
        core_x, _, _, _ = arities(dag, True)
        if len(core_x) < 20:
            exclusions["Coq root values"].append({
                "name": item["name"], "reason": "fewer than 20 positive shared-core nodes",
                "positive_core_nodes": len(core_x)})
            continue
        counter = add_analysis(rows, plot_records, constructor_rows,
                               "Coq root values", item["name"], dag, counter)
        if i % 10 == 0:
            print(f"normalized {i}/49 Coq roots", flush=True)

    study1 = pd.read_csv(ROOT / "results" / "study1" / "results.csv")
    lean_names = sorted(study1.loc[study1.name.str.endswith("_term"), "name"])
    for name in lean_names:
        dag = lean_root_dag(ROOT / "networks" / "batch1" / f"{name}.json")
        core_x, _, _, _ = arities(dag, True)
        if len(core_x) < 20:
            exclusions["Human Lean root values"].append({
                "name": name, "reason": "fewer than 20 positive shared-core nodes",
                "positive_core_nodes": len(core_x)})
            continue
        counter = add_analysis(rows, plot_records, constructor_rows,
                               "Human Lean root values", name, dag, counter)

    pair_ids = pd.read_csv(ROOT / "results" / "final_synthesis" /
                           "paired_belief_term0.csv").pair.tolist()
    for i, pair_id in enumerate(pair_ids, start=1):
        for side, corpus in (("human", "Matched human Lean root values"),
                             ("ai", "Matched AI Lean root values")):
            dag = lean_root_dag(ROOT / "networks" / f"paired_{side}" /
                                f"{pair_id}_term0.json")
            counter = add_analysis(rows, plot_records, constructor_rows,
                                   corpus, pair_id, dag, counter)
        if i % 50 == 0:
            print(f"normalized {i}/312 matched pairs", flush=True)

    frame = pd.DataFrame(rows)
    constructors = pd.DataFrame(constructor_rows)
    core = frame[frame.schema == "shared binary core"]
    all_nodes = frame[frame.schema == "all normalized constructors"]
    summary = {
        "normalization": {
            "scope": "root proof value only; no recursively expanded declarations or theorem type",
            "application": "binary",
            "binders": "binder names removed; domain and body retained",
            "let": "type, value, and body retained",
            "primary_positive_sample": sorted(CORE),
            "system_specific_constructors": "retained only in all-constructor sensitivity",
        },
        "exclusions": exclusions,
        "native_representation_diagnostic": {
            "note": "pooled nodes; diagnostic only because native constructor schemas differ",
            "Coq expanded terms": native_coq_diagnostic(),
            "Human Lean expanded terms": native_lean_diagnostic([
                ROOT / "networks" / "batch1" / f"{name}.json" for name in lean_names]),
            "Matched human Lean term0": native_lean_diagnostic([
                ROOT / "networks" / "paired_human" / f"{pair_id}_term0.json"
                for pair_id in pair_ids]),
            "Matched AI Lean term0": native_lean_diagnostic([
                ROOT / "networks" / "paired_ai" / f"{pair_id}_term0.json"
                for pair_id in pair_ids]),
        },
        "shared_binary_core": {
            corpus: corpus_summary(core[core.corpus == corpus])
            for corpus in plot_records
        },
        "all_constructor_sensitivity": {
            corpus: corpus_summary(all_nodes[all_nodes.corpus == corpus])
            for corpus in plot_records
        },
    }
    calibration = calibration_rows(plot_records)
    frame.to_csv(OUT / "per_network.csv", index=False)
    constructors.to_csv(OUT / "constructor_counts.csv", index=False)
    calibration.to_csv(OUT / "calibration.csv", index=False)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_figure(calibration)
    write_macros(summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
