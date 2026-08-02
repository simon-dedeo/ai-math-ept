"""Focused regressions for the name-to-type retrieval assay."""
from __future__ import annotations

import numpy as np

from name_type_retrieval import average_tied_percentile, claim_type, naturalize
from paired_horizon import named_have_declarations, proof_body


def test_explicit_type_stops_at_top_level_assignment() -> None:
    source = """
theorem demo : True := by
  have family (n : Nat) : (fun x : Nat => x + n) n = 2 * n := by omega
  exact True.intro
"""
    body = proof_body(source)
    declarations = named_have_declarations(body)
    assert len(declarations) == 1
    assert claim_type(body, declarations[0]) == "(fun x : Nat => x + n) n = 2 * n"


def test_inferred_type_is_excluded() -> None:
    source = "theorem demo : True := by\n  have h := True.intro\n  exact h"
    body = proof_body(source)
    declaration = named_have_declarations(body)[0]
    assert claim_type(body, declaration) is None


def test_tied_percentile_uses_average_rank() -> None:
    similarities = np.asarray([0.7, 0.7, 0.2])
    assert average_tied_percentile(similarities, 0) == 0.75
    assert average_tied_percentile(similarities, 2) == 0.0


def test_naturalize_never_emits_an_empty_prompt_key() -> None:
    assert naturalize("prime_factor") == "prime factor"
    assert naturalize("__") == "__"


if __name__ == "__main__":
    test_explicit_type_stops_at_top_level_assignment()
    test_inferred_type_is_excluded()
    test_tied_percentile_uses_average_rank()
    test_naturalize_never_emits_an_empty_prompt_key()
    print("name_type_retrieval tests passed")
