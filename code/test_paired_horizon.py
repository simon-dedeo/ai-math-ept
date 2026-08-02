"""Focused parser tests for paired_horizon.py."""
from paired_horizon import (
    named_have_claims,
    proof_body,
    serialized_target_signature,
    serialized_target_value,
    side_metrics,
)
from analyze_binder_use import lcs_matches


def test_comments_and_strings_do_not_count() -> None:
    source = '''
import Mathlib
theorem demo : True := by
  have h1 : True := by trivial
  -- h1 h1
  let s := "h1"
  exact h1
'''
    claims = named_have_claims(source)
    assert len(claims) == 1
    assert claims[0]["explicit_uses"] == 1


def test_only_final_target_declaration_is_analyzed() -> None:
    source = '''
lemma helper : True := by
  have old : True := by trivial
  exact old
theorem target : True := by
  have current : True := by trivial
  exact current
'''
    assert [claim["name"] for claim in named_have_claims(source)] == ["current"]


def test_redeclaration_ends_counting_window() -> None:
    source = '''
theorem demo : True := by
  have h1 : True := by trivial
  exact h1
  have h1 : True := by trivial
  exact h1
'''
    claims = named_have_claims(source)
    assert [claim["explicit_uses"] for claim in claims] == [1, 1]
    assert all(claim["redeclared_name"] for claim in claims)


def test_claim_horizon_counts_intervening_claims() -> None:
    source = '''
theorem demo : True := by
  have first : True := by trivial
  have middle : True := by trivial
  have last : True := first
  exact last
'''
    claims = named_have_claims(source)
    assert claims[0]["intervening_claims_to_last_use"] == 2
    assert claims[1]["explicit_uses"] == 0
    assert claims[2]["intervening_claims_to_last_use"] == 0


def test_anonymous_have_is_separate() -> None:
    metrics, claims = side_metrics(
        "theorem demo : True := by\n  have : True := by trivial\n  exact this", []
    )
    assert claims == []
    assert metrics["anonymous_haves"] == 1


def test_unicode_identifier_is_counted() -> None:
    source = "theorem demo : True := by\n  have h₄ : True := by trivial\n  exact h₄"
    claims = named_have_claims(source)
    assert [(claim["name"], claim["explicit_uses"]) for claim in claims] == [("h₄", 1)]
    assert claims[0]["placeholder_name"]


def test_lcs_skips_generated_binders_and_preserves_order() -> None:
    source = ["h1", "mid", "h2", "h1"]
    term = ["generated", "h1", "h1", "mid", "aux", "h2", "h1"]
    assert lcs_matches(source, term) == [(0, 1), (1, 3), (2, 5), (3, 6)]


def test_serialized_signature_ignores_comments_but_not_statement_changes() -> None:
    human = [{
        "kind": "theorem", "full_name": "demo",
        "signature": {"pp": "(n : ℕ) -- source note\n : n = n"},
    }]
    same = [{
        "kind": "theorem", "full_name": "demo",
        "signature": {"pp": "(n : ℕ) : n = n"},
    }]
    changed = [{
        "kind": "theorem", "full_name": "demo",
        "signature": {"pp": "(n : ℕ) : n + 0 = n"},
    }]
    assert serialized_target_signature(human) == serialized_target_signature(same)
    assert serialized_target_signature(human) != serialized_target_signature(changed)
    assert serialized_target_signature([]) is None


def test_serialized_value_is_proof_only_and_comment_normalized() -> None:
    declaration = [{
        "signature": {"pp": ": True"},
        "value": {"pp": ":= by\n  -- note\n  trivial"},
    }]
    assert serialized_target_value(declaration) == ":= by trivial"
    assert serialized_target_value([]) is None


if __name__ == "__main__":
    test_comments_and_strings_do_not_count()
    test_only_final_target_declaration_is_analyzed()
    test_redeclaration_ends_counting_window()
    test_claim_horizon_counts_intervening_claims()
    test_anonymous_have_is_separate()
    test_unicode_identifier_is_counted()
    test_lcs_skips_generated_binders_and_preserves_order()
    test_serialized_signature_ignores_comments_but_not_statement_changes()
    test_serialized_value_is_proof_only_and_comment_normalized()
    print("paired_horizon parser tests passed")
