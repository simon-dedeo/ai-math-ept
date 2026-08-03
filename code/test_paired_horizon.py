"""Focused parser tests for paired_horizon.py."""
import numpy as np
import pandas as pd

from paired_horizon import (
    named_have_declarations,
    named_have_claims,
    proof_body,
    serialized_target_signature,
    serialized_target_value,
    side_metrics,
    token_supply_difference,
    position_matched_family_associations,
    within_proof_feature_associations,
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


def test_constructor_side_shadowed_name_is_not_downstream_use() -> None:
    source = '''
theorem demo (h : True) : True := by
  have h : True := h
  exact h
'''
    body = proof_body(source)
    declaration = named_have_declarations(body)[0]
    construction_end = body.index("\n  exact h")
    claims = named_have_claims(
        source,
        [(declaration["start"], construction_end)],
        require_parser_match=True,
    )
    assert len(claims) == 1
    assert claims[0]["explicit_uses"] == 1
    assert claims[0]["first_use_delay_tokens"] == 1


def test_nested_tactic_scope_ends_before_sibling_branch() -> None:
    source = '''
theorem demo : True ∧ True := by
  constructor
  · have hlocal : True := by trivial
    exact hlocal
  · let hlocal : Prop := True
    exact True.intro
'''
    body = proof_body(source)
    declarations = named_have_declarations(body)
    local = declarations[0]
    construction_end = body.index("\n    exact hlocal")
    scope_end = body.index("\n  · let hlocal")
    claims = named_have_claims(
        source,
        [(local["start"], construction_end, scope_end)],
        require_parser_match=True,
    )
    assert len(claims) == 1
    assert claims[0]["explicit_uses"] == 1
    assert claims[0]["unscoped_explicit_uses"] == 2
    assert claims[0]["scope_excluded_reference_tokens"] == 1


def test_inner_construction_claims_are_not_later_outer_boundaries() -> None:
    source = '''
theorem demo : True := by
  have outer : True := by
    have inner : True := by trivial
    exact inner
  exact outer
'''
    body = proof_body(source)
    declarations = named_have_declarations(body)
    outer_end = body.index("\n  exact outer")
    inner_end = body.index("\n    exact inner")
    claims = named_have_claims(
        source,
        [
            (declarations[0]["start"], outer_end, len(body)),
            (declarations[1]["start"], inner_end, outer_end),
        ],
        require_parser_match=True,
    )
    assert claims[0]["later_claims_available"] == 0
    assert claims[0]["intervening_claims_to_last_use"] == 0


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


def test_redeclaration_also_ends_reach_opportunity() -> None:
    source = '''
theorem demo : True := by
  have h1 : True := by trivial
  have middle : True := h1
  have h1 : True := by trivial
  exact h1
'''
    claims = named_have_claims(source)
    assert claims[0]["later_claims_available"] == 1
    assert claims[0]["intervening_claims_to_last_use"] == 1
    assert claims[0]["fraction_available_claims_to_last_use"] == 1.0


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
    assert claims[0]["later_claims_available"] == 2
    assert claims[0]["fraction_available_claims_to_last_use"] == 1.0
    assert claims[1]["explicit_uses"] == 0
    assert claims[1]["fraction_available_claims_to_last_use"] is None
    assert claims[2]["intervening_claims_to_last_use"] == 0
    assert claims[2]["later_claims_available"] == 0
    assert claims[2]["fraction_available_claims_to_last_use"] is None


def test_anonymous_have_is_separate() -> None:
    metrics, claims = side_metrics(
        "theorem demo : True := by\n  have : True := by trivial\n  exact this", []
    )
    assert claims == []
    assert metrics["anonymous_haves"] == 1
    metrics, claims = side_metrics(
        "theorem demo : True := by\n  have _ : True := by trivial\n  trivial", []
    )
    assert claims == []
    assert metrics["anonymous_haves"] == 1


def test_unicode_identifier_is_counted() -> None:
    source = "theorem demo : True := by\n  have h₄ : True := by trivial\n  exact h₄"
    claims = named_have_claims(source)
    assert [(claim["name"], claim["explicit_uses"]) for claim in claims] == [("h₄", 1)]
    assert claims[0]["placeholder_name"]


def test_binder_bearing_local_lemma_is_counted() -> None:
    source = '''
theorem demo : True := by
  have reusable (n m : ℕ) {α : Type} (f : α → Fin (n + (m + 1))) : True := by
    trivial
  have bare x : True := by
    trivial
  have ground : True := reusable 0 0 (fun _ => 0)
  exact ground
'''
    claims = named_have_claims(source)
    assert [claim["name"] for claim in claims] == ["reusable", "bare", "ground"]
    assert claims[0]["binder_groups"] == 3
    assert claims[0]["parametric_claim"]
    assert claims[1]["binder_groups"] == 1
    assert claims[1]["parametric_claim"]
    assert not claims[2]["parametric_claim"]
    assert claims[0]["explicit_uses"] == 1


def test_equivalent_universal_local_lemma_is_generalized() -> None:
    source = '''
theorem demo : True := by
  have binder_form (n : ℕ) : n = n := by simp
  have forall_form : ∀ n : ℕ, n = n := by intro n; rfl
  have parenthesized : (∀ n : ℕ, n = n) := by intro n; rfl
  have ordinary : True := by trivial
  exact ordinary
'''
    claims = named_have_claims(source)
    assert claims[0]["parametric_claim"] and claims[0]["generalized_claim"]
    assert not claims[0]["universal_claim"]
    assert not claims[1]["parametric_claim"] and claims[1]["generalized_claim"]
    assert claims[1]["universal_claim"]
    assert claims[2]["universal_claim"] and claims[2]["generalized_claim"]
    assert not claims[3]["generalized_claim"]


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


def test_within_proof_feature_association_holds_proof_fixed() -> None:
    rows = []
    for side in ("h", "a"):
        rows.extend([
            {"pair": "p1", "source": "s1", "side": side,
             "generalized_claim": True, "placeholder_name": False,
             "explicit_uses": 2, "intervening_claims_to_last_use": 1},
            {"pair": "p1", "source": "s1", "side": side,
             "generalized_claim": False, "placeholder_name": True,
             "explicit_uses": 0, "intervening_claims_to_last_use": 0},
        ])
    result = within_proof_feature_associations(
        pd.DataFrame(rows), 100, np.random.default_rng(7)
    )
    for side in ("human", "ai"):
        family = result["generalized_claim"][side]
        assert family["eligible_proofs"] == 1
        assert family["adopted"]["flagged_minus_unflagged"] == 1.0
        assert family["explicit_uses"]["flagged_minus_unflagged"] == 2.0
    paired = result["generalized_claim"]["paired_both_tracks"]
    assert paired["eligible_pairs"] == 1
    assert paired["multi_uptake"]["ai_minus_human"] == 0.0


def test_family_position_matching_uses_nearest_claim() -> None:
    rows = []
    for side in ("h", "a"):
        for index, (family, uses) in enumerate([
            (False, 0), (False, 0), (True, 2), (False, 0), (False, 0)
        ]):
            rows.append({
                "pair": "p1", "source": "s1", "side": side,
                "claim_index": index, "generalized_claim": family,
                "explicit_uses": uses,
            })
    result = position_matched_family_associations(
        pd.DataFrame(rows), 100, np.random.default_rng(11)
    )
    for matching in ("all_matches", "caliper_0_25"):
        for side in ("human", "ai"):
            summary = result[matching][side]
            assert summary["eligible_proofs"] == 1
            assert summary["matched_claim_pairs"] == 1
            assert summary["multi_uptake"]["family_minus_instance"] == 1.0


def test_token_supply_is_not_claim_selectivity() -> None:
    frame = pd.DataFrame([
        {
            "source": "s1", "h_adopted_haves": 1, "h_tokens": 100,
            "a_adopted_haves": 3, "a_tokens": 200,
            "h_chars": 1000, "a_chars": 1500,
        },
        {
            "source": "s2", "h_adopted_haves": 1, "h_tokens": 100,
            "a_adopted_haves": 3, "a_tokens": 200,
            "h_chars": 1000, "a_chars": 1500,
        },
    ])
    result = token_supply_difference(
        frame, "adopted_haves", 100, np.random.default_rng(3)
    )
    assert result["human"] == 1.0
    assert result["ai"] == 1.5
    assert result["ai_minus_human"] == 0.5
    assert result["source_groups_ai_higher"] == 2
    assert result["source_groups_total"] == 2
    character_result = token_supply_difference(
        frame, "adopted_haves", 100, np.random.default_rng(4),
        denominator="chars", multiplier=1000,
        unit="claims per 1,000 characters",
    )
    assert character_result["human"] == 1.0
    assert character_result["ai"] == 2.0


def test_boundary_count_can_be_padded_without_uptake() -> None:
    padding = "\n".join(
        f"  have junk_{index} : True := by trivial" for index in range(7)
    )
    source = f"theorem demo : True := by\n{padding}\n  exact True.intro"
    claims = named_have_claims(source)
    assert len(claims) == 7
    assert sum(claim["explicit_uses"] > 0 for claim in claims) == 0
    assert sum(claim["explicit_uses"] == 0 for claim in claims) == 7


def test_distinct_consumer_sites_collapse_tokens_within_one_construction() -> None:
    source = '''
theorem demo : True := by
  have basis : True := by trivial
  have use1 : True := by exact basis
  have use2 : True := by exact basis
  exact use1
'''
    body = proof_body(source)
    declarations = named_have_declarations(body)
    ends = [
        body.index("\n  have use1"),
        body.index("\n  have use2"),
        body.index("\n  exact use1"),
    ]
    ranges = [
        (declaration["start"], end, len(body))
        for declaration, end in zip(declarations, ends)
    ]
    claims = named_have_claims(
        source, ranges,
        require_parser_match=True,
    )
    assert claims[0]["explicit_uses"] == 2
    assert claims[0]["distinct_consumer_sites"] == 2
    assert claims[0]["named_claim_consumer_sites"] == 2
    metrics, _ = side_metrics(source, [], ranges)
    assert metrics["named_claim_dependency_edges"] == 2
    assert metrics["named_claim_branchpoints"] == 1
    assert metrics["longest_named_claim_chain"] == 1

    one_consumer = '''
theorem demo : True := by
  have basis : True := by trivial
  have use_both : True ∧ True := by exact ⟨basis, basis⟩
  exact use_both.1
'''
    body = proof_body(one_consumer)
    declarations = named_have_declarations(body)
    claims = named_have_claims(
        one_consumer,
        [
            (declarations[0]["start"], body.index("\n  have use_both"), len(body)),
            (declarations[1]["start"], body.index("\n  exact use_both"), len(body)),
        ],
        require_parser_match=True,
    )
    assert claims[0]["explicit_uses"] == 2
    assert claims[0]["distinct_consumer_sites"] == 1


def test_named_claim_construction_graph_chain_depth() -> None:
    source = '''
theorem demo : True := by
  have c1 : True := by trivial
  have c2 : True := by exact c1
  have c3 : True := by exact c2
  exact c3
'''
    body = proof_body(source)
    declarations = named_have_declarations(body)
    ends = [
        body.index("\n  have c2"),
        body.index("\n  have c3"),
        body.index("\n  exact c3"),
    ]
    ranges = [
        (declaration["start"], end, len(body))
        for declaration, end in zip(declarations, ends)
    ]
    metrics, _ = side_metrics(source, [], ranges)
    assert metrics["named_claim_dependency_edges"] == 2
    assert metrics["named_claim_branchpoints"] == 0
    assert metrics["longest_named_claim_chain"] == 2


if __name__ == "__main__":
    test_comments_and_strings_do_not_count()
    test_constructor_side_shadowed_name_is_not_downstream_use()
    test_only_final_target_declaration_is_analyzed()
    test_redeclaration_ends_counting_window()
    test_redeclaration_also_ends_reach_opportunity()
    test_claim_horizon_counts_intervening_claims()
    test_anonymous_have_is_separate()
    test_unicode_identifier_is_counted()
    test_binder_bearing_local_lemma_is_counted()
    test_equivalent_universal_local_lemma_is_generalized()
    test_lcs_skips_generated_binders_and_preserves_order()
    test_serialized_signature_ignores_comments_but_not_statement_changes()
    test_serialized_value_is_proof_only_and_comment_normalized()
    test_within_proof_feature_association_holds_proof_fixed()
    test_family_position_matching_uses_nearest_claim()
    test_token_supply_is_not_claim_selectivity()
    test_boundary_count_can_be_padded_without_uptake()
    test_distinct_consumer_sites_collapse_tokens_within_one_construction()
    test_named_claim_construction_graph_chain_depth()
    print("paired_horizon parser tests passed")
