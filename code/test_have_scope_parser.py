"""Integration regression for Lean-parser tactic scope endpoints."""
from pathlib import Path

import pytest

from paired_horizon import named_have_claims, parser_have_ranges, proof_body


ROOT = Path(__file__).resolve().parents[1]


def test_lean_parser_clips_sibling_tactic_branch() -> None:
    if not (ROOT / "mathlib4" / "lakefile.lean").exists():
        pytest.skip("local Mathlib environment is not materialized")
    source = """
theorem demo : True ∧ True := by
  constructor
  · have hlocal : True := by trivial
    exact hlocal
  · let hlocal : Prop := True
    exact True.intro
"""
    ranges, audit = parser_have_ranges([proof_body(source)], ROOT)
    assert audit["parsed"] == 1
    assert ranges[0] is not None and len(ranges[0]) == 1
    claims = named_have_claims(source, ranges[0], require_parser_match=True)
    assert len(claims) == 1
    assert claims[0]["explicit_uses"] == 1
    assert claims[0]["unscoped_explicit_uses"] == 2
    assert claims[0]["scope_end"] < len(proof_body(source))
