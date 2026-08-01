"""Sanity checks for the cross-system constructor normalization."""

import json
import tempfile
from pathlib import Path

import numpy as np

from normalized_term_arity import (
    arities,
    lean_root_dag,
    normalize_coq_term,
    parse_sexpressions,
)
from normalized_outdegree_sensitivity import out_degrees


# The parser preserves one top-level Coq definition and its variadic App.
parsed = parse_sexpressions("(Definition th (App f a b))")
assert parsed == [["Definition", "th", ["App", "f", "a", "b"]]]

# Coq's variadic application is converted to the same binary spine as Lean.
coq = normalize_coq_term(["App", "f", "a", "b"])
coq_x, coq_n, coq_z, coq_labels = arities(coq, True)
assert sorted(coq_x.tolist()) == [2, 2]
assert coq_labels == {"App": 2}

# Binder names are metadata in the common schema, not dependency leaves.
lam = normalize_coq_term(["Lambda", "x", "T", ["App", "f", "x"]])
lam_x, _, _, lam_labels = arities(lam, True)
assert sorted(lam_x.tolist()) == [2, 2]
assert lam_labels == {"App": 1, "Lam": 1}

# A synthetic Lean edge stream for the same f a b term normalizes identically.
lean_json = {
    "nodes": 7,
    "labels": ["C:f", "C:a", "App", "C:b", "App", "C:T", "THM:th"],
    "edges": [[0, 2], [1, 2], [2, 4], [3, 4], [4, 6], [5, 6]],
}
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "term0.json"
    path.write_text(json.dumps(lean_json))
    lean = lean_root_dag(path)
lean_x, lean_n, lean_z, lean_labels = arities(lean, True)
assert np.array_equal(np.sort(coq_x), np.sort(lean_x))
assert (coq_n, coq_z, coq_labels) == (lean_n, lean_z, lean_labels)
assert np.array_equal(np.sort(out_degrees(coq, True)),
                      np.sort(out_degrees(lean, True)))

print({
    "coq_binary_arities": coq_x.tolist(),
    "lean_binary_arities": lean_x.tolist(),
    "lambda_core_arities": lam_x.tolist(),
})
