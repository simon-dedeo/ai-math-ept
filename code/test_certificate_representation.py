"""Regression: zeta-equivalent term representations can differ exponentially.

The synthetic expression has one shared copy of the previous level behind a
``let`` and uses its binder twice.  Raw syntax therefore grows linearly, while
Lean's own zeta reduction expands it into a binary tree.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPTH = 14


def main() -> None:
    template = (ROOT / "code/ExtractBinderUseLinear.lean.tmpl").read_text()
    workdir = ROOT / "tmp/horizon/certificate_representation"
    workdir.mkdir(parents=True, exist_ok=True)
    lean_path = workdir / "representation.lean"
    output_path = workdir / "representation.json"
    lean_path.write_text(
        "import Mathlib\n\n" + template
        + "\n\nnamespace Horizon\nopen Lean\n"
        + "def sharedExpr : Nat → Expr\n"
        + "  | 0 => .lit (.natVal 0)\n"
        + "  | n + 1 =>\n"
        + "    .letE `x (.const ``Nat []) (sharedExpr n)\n"
        + "      (.app (.app (.const ``Nat.add []) (.bvar 0)) (.bvar 0)) false\n"
        + "def writeRepresentationStats (n : Nat) (path : String) : CoreM Unit :=\n"
        + "  _root_.Lean.Meta.MetaM.run' do\n"
        + "    let raw := sharedExpr n\n"
        + "    let rawType ← _root_.Lean.Meta.inferType raw\n"
        + "    let reduced ← _root_.Lean.Meta.zetaReduce raw\n"
        + "    let reducedType ← _root_.Lean.Meta.inferType reduced\n"
        + "    let rawTypeOk ← _root_.Lean.Meta.isDefEq rawType (.const ``Nat [])\n"
        + "    let reducedTypeOk ← _root_.Lean.Meta.isDefEq reducedType (.const ``Nat [])\n"
        + "    let typesDefEq ← _root_.Lean.Meta.isDefEq rawType reducedType\n"
        + "    let (rawNodes, rawLets) := collectLetsLinear raw\n"
        + "    let (zetaNodes, zetaLets) := collectLetsLinear reduced\n"
        + "    let payload := \"{\\\"depth\\\":\" ++ toString n ++\n"
        + "      \",\\\"raw_nodes\\\":\" ++ toString rawNodes ++\n"
        + "      \",\\\"raw_lets\\\":\" ++ toString rawLets.size ++\n"
        + "      \",\\\"zeta_nodes\\\":\" ++ toString zetaNodes ++\n"
        + "      \",\\\"zeta_lets\\\":\" ++ toString zetaLets.size ++\n"
        + "      \",\\\"raw_type_nat\\\":\" ++ toString rawTypeOk ++\n"
        + "      \",\\\"zeta_type_nat\\\":\" ++ toString reducedTypeOk ++\n"
        + "      \",\\\"types_definitionally_equal\\\":\" ++ toString typesDefEq ++ \"}\"\n"
        + "    IO.FS.writeFile path payload\n"
        + "end Horizon\n\n"
        + f'#eval Horizon.writeRepresentationStats {DEPTH} "{output_path}"\n'
    )
    subprocess.run(
        ["lake", "env", "lean", str(lean_path)], cwd=ROOT / "mathlib4",
        text=True, capture_output=True, check=True, timeout=300,
    )
    result = json.loads(output_path.read_text())
    assert result["raw_nodes"] == 1 + 7 * DEPTH, result
    assert result["raw_lets"] == DEPTH, result
    assert result["zeta_nodes"] == 4 * 2**DEPTH - 3, result
    assert result["zeta_lets"] == 0, result
    assert result["raw_type_nat"] is True, result
    assert result["zeta_type_nat"] is True, result
    assert result["types_definitionally_equal"] is True, result
    print(result)


if __name__ == "__main__":
    main()
