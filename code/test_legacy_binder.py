"""Exercise legacy `letFun` decoding under nested, shadowed source `have`s."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    template = (ROOT / "code/ExtractBinderUseLegacy.lean.tmpl").read_text()
    workdir = ROOT / "tmp/horizon/legacy_binder"
    workdir.mkdir(parents=True, exist_ok=True)
    lean_path = workdir / "nested.lean"
    output_path = workdir / "nested.json"
    source = """import Mathlib

open Nat Finset List

theorem legacy_nested (p q : Prop) (hp : p) (hq : q) : p ∧ p ∧ q := by
  have unused : p := by exact hp
  have outer : p := by exact hp
  have inner : q := by
    have outer : q := by exact hq
    exact outer
  exact ⟨outer, outer, inner⟩
"""
    lean_path.write_text(
        source + "\n" + template
        + f'\n#eval Horizon.writeBinderStats `legacy_nested "{output_path}"\n'
    )
    subprocess.run(
        ["lake", "env", "lean", str(lean_path)], cwd=ROOT / "mathlib4_v415",
        text=True, capture_output=True, check=True, timeout=300,
    )
    result = json.loads(output_path.read_text())
    decoded = [
        (item["kind"], item["name"], item["uses"])
        for item in result["lets"]
    ]
    assert decoded == [
        ("have_fun", "unused", 0),
        ("have_fun", "outer", 2),
        ("have_fun", "inner", 1),
        ("have_fun", "outer", 1),
    ], result

    family_lean = workdir / "family_spellings.lean"
    family_output = workdir / "family_spellings.json"
    family_source = """import Mathlib

theorem legacy_family_spellings :
    (∀ n : Nat, n = n) ∧ (∀ n : Nat, n = n) := by
  have binder_form (n : Nat) : n = n := by rfl
  have forall_form : ∀ n : Nat, n = n := by intro n; rfl
  exact ⟨binder_form, forall_form⟩
"""
    family_lean.write_text(
        family_source + "\n" + template
        + f'\n#eval Horizon.writeBinderStats `legacy_family_spellings "{family_output}"\n'
    )
    subprocess.run(
        ["lake", "env", "lean", str(family_lean)], cwd=ROOT / "mathlib4_v415",
        text=True, capture_output=True, check=True, timeout=300,
    )
    family_result = json.loads(family_output.read_text())
    family_binders = [
        (item["kind"], item["name"], item["uses"])
        for item in family_result["lets"]
    ]
    assert family_binders == [
        ("have_fun", "binder_form", 1),
        ("have_fun", "forall_form", 1),
    ], family_result

    # A corpus proof opens `List`, whose `count` declaration once shadowed an
    # internal accumulator name in this template under Lean 4.15.
    pair = "pair_08a52a63"
    corpus_source = (ROOT / f"census/paired_numina_exact/human/{pair}.lean").read_text()
    corpus_lean = workdir / f"{pair}.lean"
    corpus_output = workdir / f"{pair}.json"
    corpus_lean.write_text(
        corpus_source + "\n" + template
        + f'\n#eval Horizon.writeBinderStats `number_theory_97342 "{corpus_output}"\n'
    )
    subprocess.run(
        ["lake", "env", "lean", str(corpus_lean)], cwd=ROOT / "mathlib4_v415",
        text=True, capture_output=True, check=True, timeout=300,
    )
    corpus_result = json.loads(corpus_output.read_text())
    corpus_names = [item["name"] for item in corpus_result["lets"]]
    assert "mod_nine_eq_sum_digts_mod_nine" in corpus_names, corpus_result

    print({
        "root_nodes": result["root_nodes"], "decoded": decoded,
        "family_spellings": family_binders,
        "corpus_regression_binders": len(corpus_names),
    })


if __name__ == "__main__":
    main()
