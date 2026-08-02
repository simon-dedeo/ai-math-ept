"""Regression: the one-pass binder extractor matches the quadratic reference."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


SOURCE = """import Mathlib

theorem horizonBinderRegression (p q : Prop) (hp : p) (hq : q) : p :=
  let first : p := hp
  let unused : q := hq
  let shifted : q → p := fun _ => first
  let copied : p ∧ p := ⟨shifted hq, first⟩
  copied.1
"""


def run(root: Path, mathlib: Path, template: Path, label: str) -> dict:
    workdir = root / "tmp" / "horizon" / "binder_regression"
    workdir.mkdir(parents=True, exist_ok=True)
    output = workdir / f"{label}.json"
    source = workdir / f"{label}.lean"
    source.write_text(
        SOURCE + "\n" + template.read_text() +
        f'\n#eval Horizon.writeBinderStats `horizonBinderRegression "{output}"\n'
    )
    subprocess.run(
        ["lake", "env", "lean", str(source)], cwd=mathlib, check=True,
        text=True, capture_output=True, timeout=300,
    )
    return json.loads(output.read_text())


def run_deep_iterative(root: Path, mathlib: Path) -> None:
    """Exercise a depth that makes recursive interpreter traversal abort."""
    workdir = root / "tmp" / "horizon" / "binder_regression"
    source = workdir / "iterative_deep.lean"
    template = (root / "code/ExtractBinderUseIterative.lean.tmpl").read_text()
    source.write_text(
        "import Mathlib\n\n" + template + """

open Lean in
def iterativeDeepRegression : IO Unit := do
  let depth := 12000
  let mut expr := mkConst `True
  for _ in [0:depth] do
    expr := mkApp expr (mkConst `True)
  let (nodes, lets) := Horizon.collectLetsIterative expr
  if nodes != 1 + 2 * depth || !lets.isEmpty then
    throw (IO.userError s!"unexpected deep traversal result: {nodes}, {lets.size}")

#eval iterativeDeepRegression
"""
    )
    subprocess.run(
        ["lake", "env", "lean", str(source)], cwd=mathlib, check=True,
        text=True, capture_output=True, timeout=300,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mathlib-dir", type=Path, default=Path("mathlib4"))
    args = parser.parse_args()
    root = args.root.resolve()
    mathlib = args.mathlib_dir if args.mathlib_dir.is_absolute() else root / args.mathlib_dir
    reference = run(root, mathlib, root / "code/ExtractBinderUse.lean.tmpl", "reference")
    linear = run(root, mathlib, root / "code/ExtractBinderUseLinear.lean.tmpl", "linear")
    iterative = run(
        root, mathlib, root / "code/ExtractBinderUseIterative.lean.tmpl", "iterative"
    )
    assert linear == reference, (linear, reference)
    assert iterative == reference, (iterative, reference)
    assert any(item["name"] == "unused" and item["uses"] == 0 for item in linear["lets"])
    assert any(item["name"] == "first" and item["uses"] == 2 for item in linear["lets"])
    assert any(item["name"] == "shifted" and item["uses"] == 1 for item in linear["lets"])
    run_deep_iterative(root, mathlib)
    print({"root_nodes": linear["root_nodes"], "lets": linear["lets"]})


if __name__ == "__main__":
    main()
