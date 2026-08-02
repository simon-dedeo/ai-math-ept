"""Consistency checks for numerical and layout claims in the horizon paper."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def close(value: float, target: float, tolerance: float = 5e-4) -> None:
    assert abs(value - target) <= tolerance, (value, target)


def page_text(pdf: Path, page: int) -> str:
    return subprocess.check_output(
        ["pdftotext", "-f", str(page), "-l", str(page), str(pdf), "-"],
        text=True,
    )


def main() -> None:
    source = json.loads((ROOT / "results/horizon/source_summary.json").read_text())
    binder = json.loads((ROOT / "results/horizon/binder_summary.json").read_text())
    surprise = json.loads((ROOT / "results/horizon/surprisal_summary_w8.json").read_text())
    loso = json.loads(
        (ROOT / "results/horizon/surprisal_summary_loso_bigram_w8.json").read_text()
    )
    loso_provenance = json.loads(
        (ROOT / "results/horizon/surprisal_loso_bigram_provenance.json").read_text()
    )
    name_mean = json.loads(
        (ROOT / "results/horizon/name_retrieval_mean/summary.json").read_text()
    )
    name_last = json.loads(
        (ROOT / "results/horizon/name_retrieval_last/summary.json").read_text()
    )
    term = json.loads((ROOT / "results/horizon/scoped_term_structure/term0.json").read_text())
    tex = (ROOT / "report/horizon/main.tex").read_text()
    pdf = ROOT / "output/pdf/proofs_for_now_and_proofs_for_later.pdf"

    assert source["pairs"] == 3630 and source["source_groups"] == 12
    assert source["target_pair_audit"] == {
        "flag_valid_candidates": 3635,
        "missing_target_declaration": 1,
        "mismatched_target_header": 4,
        "exact_statement_pairs": 3630,
    }
    assert source["pretarget_declaration_audit"]["identical_shared_scaffolding"] == 158
    assert source["pretarget_declaration_audit"]["human_only"] == 0
    assert source["pretarget_declaration_audit"]["ai_only"] == 11
    assert source["pretarget_declaration_audit"]["ai_only_artifacts_referencing_helper"] == 7
    assert source["pretarget_declaration_audit"]["ai_only_helper_names"] == ["lemma_1", "lemma_2"]
    parser_audit = source["have_scope_parser_audit"]
    assert parser_audit["parsed"] == 7111 and parser_audit["failed"] == 149
    assert parser_audit["regex_named_claims"] == 40626
    assert parser_audit["parser_matched_named_claims"] == 39646
    assert parser_audit["pairs_fully_parsed_and_aligned"] == 3511
    close(parser_audit["named_claim_coverage"], 0.97588)
    strict_parser = source["fully_parsed_pair_sensitivity"]
    assert strict_parser["pairs"] == 3511
    assert strict_parser["explicit_uses_per_claim"]["source_cluster_ci"][1] < 0
    assert strict_parser["zero_uptake_share"]["source_cluster_ci"][0] > 0
    scope_audit = source["scope_clipping_audit"]
    assert scope_audit["human"]["excluded_name_tokens"] == 1068
    assert scope_audit["ai"]["excluded_name_tokens"] == 1157
    assert scope_audit["human"]["claims_with_excluded_name_tokens"] == 442
    assert scope_audit["ai"]["claims_with_excluded_name_tokens"] == 568
    close(source["claim_rates"]["human"]["explicit_uses_per_claim"]["estimate"], 1.3526)
    close(source["claim_rates"]["ai"]["explicit_uses_per_claim"]["estimate"], 0.8208)
    close(source["claim_rates"]["human"]["zero_uptake_share"]["estimate"], 0.2216)
    close(source["claim_rates"]["ai"]["zero_uptake_share"]["estimate"], 0.3694)
    close(source["claim_rates"]["human"]["multi_uptake_share"]["estimate"], 0.2401)
    close(source["claim_rates"]["ai"]["multi_uptake_share"]["estimate"], 0.1025)
    parametric = source["parametric_claim_difference"]
    close(parametric["human"], 0.02762)
    close(parametric["ai"], 0.00207)
    assert parametric["source_cluster_ci"][1] < 0
    parametric_profiles = source["parametric_claim_profiles"]
    assert parametric_profiles["human"]["claims"] == 401
    assert parametric_profiles["ai"]["claims"] == 52
    close(parametric_profiles["human"]["multi_uptake_share"], 0.5336)
    close(parametric_profiles["ai"]["multi_uptake_share"], 0.5577)
    assert source["parametric_proof_pair_audit"] == {
        "human_any": 233,
        "ai_any": 28,
        "both": 26,
        "human_only": 207,
        "ai_only": 2,
        "neither": 3395,
    }
    generalized = source["generalized_claim_difference"]
    close(generalized["human"], 0.05241)
    close(generalized["ai"], 0.01679)
    assert generalized["source_cluster_ci"][1] < 0
    assert source["generalized_proof_pair_audit"] == {
        "human_any": 455,
        "ai_any": 247,
        "both": 145,
        "human_only": 310,
        "ai_only": 102,
        "neither": 3073,
    }
    family_function = source["within_proof_feature_associations"]["generalized_claim"]
    assert family_function["human"]["eligible_proofs"] == 369
    assert family_function["ai"]["eligible_proofs"] == 239
    assert family_function["human"]["adopted"]["source_cluster_ci"][0] > 0
    assert family_function["ai"]["multi_uptake"]["source_cluster_ci"][0] > 0
    paired_family = family_function["paired_both_tracks"]
    assert paired_family["eligible_pairs"] == 110
    assert paired_family["multi_uptake"]["source_cluster_ci"][0] > 0
    position_family = source["position_matched_family_associations"]["caliper_0_25"]
    assert position_family["human"]["eligible_proofs"] == 248
    assert position_family["ai"]["eligible_proofs"] == 199
    for side in ("human", "ai"):
        assert position_family[side]["adopted"]["source_cluster_ci"][0] > 0
        assert position_family[side]["multi_uptake"]["source_cluster_ci"][0] > 0
    assert position_family["paired_both_tracks"]["multi_uptake"][
        "source_cluster_ci"
    ][0] > 0
    no_native_decide = source["automation_exclusion_sensitivity"]["native_decide"]
    assert no_native_decide["pairs"] == 3214
    close(no_native_decide["generalized_claim_share"]["human"], 0.05113)
    close(no_native_decide["generalized_claim_share"]["ai"], 0.01717)
    assert no_native_decide["generalized_claim_share"]["source_cluster_ci"][1] < 0
    lexicon = source["name_lexicon"]
    assert lexicon["human"]["types"] == 3578
    assert lexicon["ai"]["types"] == 1662
    close(lexicon["human"]["effective_vocabulary"], 369.447, 0.001)
    close(lexicon["ai"]["effective_vocabulary"], 77.460, 0.001)
    coordinates = source["interface_coordinate_correlations"]
    assert coordinates["pairs_with_claims_on_both_sides"] == 1816
    close(coordinates["spearman"]["explicit_uses"]["long_reach"], 0.3413, 0.002)
    count_matched = source["claim_count_sensitivity"]["exact_equal_positive"]
    assert count_matched["pairs"] == 206
    assert count_matched["explicit_uses_per_claim"]["source_cluster_ci"][1] < 0
    assert count_matched["zero_uptake_share"]["source_cluster_ci"][0] > 0
    assert count_matched["generalized_claim_share"]["source_cluster_ci"][1] < 0
    length_matched = source["length_matched_sensitivity"]["within_ten_percent"]
    assert length_matched["pairs"] == 834
    assert length_matched["explicit_uses_per_claim"]["source_cluster_ci"][1] < 0
    assert length_matched["zero_uptake_share"]["source_cluster_ci"][0] > 0
    assert length_matched["long_horizon_share"]["source_cluster_ci"][1] < 0
    assert length_matched["generalized_claim_share"]["source_cluster_ci"][1] < 0
    reach = source["uptake_reach_decomposition"]
    close(reach["adoption_probability"]["human"], 0.7784)
    close(reach["adoption_probability"]["ai"], 0.6306)
    close(reach["explicit_use_count_given_adoption"]["human"], 1.7378)
    close(reach["explicit_use_count_given_adoption"]["ai"], 1.3016)
    assert reach["explicit_use_count_given_adoption"]["source_cluster_ci"][1] < 0
    close(reach["last_use_token_distance_given_adoption"]["human"], 35.0449)
    close(reach["last_use_token_distance_given_adoption"]["ai"], 23.8942)
    assert reach["last_use_token_distance_given_adoption"]["source_cluster_ci"][1] < 0
    crossing = reach["crosses_any_later_boundary_given_adoption_and_opportunity"]
    close(crossing["human"], 0.8365)
    close(crossing["ai"], 0.8496)
    assert crossing["source_cluster_ci"][0] < 0 < crossing["source_cluster_ci"][1]
    normalized_reach = reach["fraction_available_boundaries_crossed_given_adoption"]
    close(normalized_reach["human"], 0.6370)
    close(normalized_reach["ai"], 0.6205)
    assert normalized_reach["source_cluster_ci"][0] < 0 < normalized_reach[
        "source_cluster_ci"
    ][1]
    reach_controls = source["uptake_reach_matched_controls"]
    equal_claims = reach_controls["exact_equal_positive_claim_count"]
    assert equal_claims["pairs"] == 206
    equal_profile = equal_claims["profile"]
    assert equal_profile["adoption_probability"]["source_cluster_ci"][1] < 0
    equal_normalized = equal_profile[
        "fraction_available_boundaries_crossed_given_adoption"
    ]["source_cluster_ci"]
    assert equal_normalized[0] < 0 < equal_normalized[1]
    matched_length = reach_controls["within_ten_percent_length"]
    assert matched_length["pairs"] == 834
    matched_profile = matched_length["profile"]
    assert matched_profile["adoption_probability"]["source_cluster_ci"][1] < 0
    for metric in (
        "last_use_token_distance_given_adoption",
        "crosses_any_later_boundary_given_adoption_and_opportunity",
        "fraction_available_boundaries_crossed_given_adoption",
    ):
        lo, hi = matched_profile[metric]["source_cluster_ci"]
        assert lo < 0 < hi
    unique_names = source["nonredeclared_name_sensitivity"]
    assert unique_names["explicit_uses_per_claim"]["human_claims"] == 9691
    assert unique_names["explicit_uses_per_claim"]["ai_claims"] == 14795
    assert unique_names["explicit_uses_per_claim"]["source_cluster_ci"][1] < 0
    assert unique_names["zero_uptake_share"]["source_cluster_ci"][0] > 0
    assert unique_names["long_horizon_share"]["source_cluster_ci"][1] < 0
    overlap = source["target_value_overlap_audit"]
    assert overlap["identical_pairs"] == 181
    assert overlap["similarity_at_least_0_9"] == 230
    assert overlap["sensitivity_excluding_similarity_at_least_0_9"]["pairs"] == 3400
    rendering_matches = source["certificate_rendering_match_audit"]
    assert rendering_matches["pairs"] == 181
    assert rendering_matches["source_body_also_identical"] == 180

    assert binder["tasks"] == 7260 and binder["pairs_with_both_sides"] == 3630
    assert binder["task_status"] == {"ok": 7260}
    assert binder["source_claim_retention_complete_pairs"]["human"]["denominator"] == 14519
    assert binder["source_claim_retention_complete_pairs"]["ai"]["denominator"] == 25127
    close(binder["claim_rates_complete_pairs"]["human"]["zero_term_use"]["estimate"], 0.0981)
    close(binder["claim_rates_complete_pairs"]["ai"]["zero_term_use"]["estimate"], 0.2180)
    close(binder["claim_rates_complete_pairs"]["human"]["one_term_use"]["estimate"], 0.5803)
    close(binder["claim_rates_complete_pairs"]["ai"]["one_term_use"]["estimate"], 0.4401)
    close(binder["claim_rates_complete_pairs"]["human"]["multi_term_use"]["estimate"], 0.3216)
    close(binder["claim_rates_complete_pairs"]["ai"]["multi_term_use"]["estimate"], 0.3419)
    zero_delta = binder["claim_rate_differences_complete_pairs"]["zero_term_use"]
    multi_delta = binder["claim_rate_differences_complete_pairs"]["multi_term_use"]
    polarized_delta = binder["claim_rate_differences_complete_pairs"]["polarized_term_use"]
    assert zero_delta["source_cluster_ci"][0] > 0
    assert multi_delta["source_cluster_ci"][0] < 0 < multi_delta["source_cluster_ci"][1]
    assert polarized_delta["source_cluster_ci"][0] > 0
    conditional_multi = binder["multi_term_use_conditional_on_retention"]
    close(conditional_multi["human"]["estimate"], 0.3566)
    close(conditional_multi["ai"]["estimate"], 0.4372)
    assert conditional_multi["ai_minus_human"]["source_cluster_ci"][0] > 0
    assert conditional_multi["ai_minus_human"]["source_groups_ai_higher"] == 11
    assert conditional_multi["ai_minus_human"]["leave_one_source_out_range"][0] > 0
    family_term = binder["within_proof_generality_term_association"]
    assert family_term["human"]["proofs"] == 367
    assert family_term["ai"]["proofs"] == 239
    for side in ("human", "ai"):
        assert family_term[side]["zero_term_use"]["source_cluster_ci"][1] < 0
    assert family_term["human"]["multi_term_use"]["source_cluster_ci"][0] > 0
    ai_family_multi = family_term["ai"]["multi_term_use"]["source_cluster_ci"]
    assert ai_family_multi[0] < 0 < ai_family_multi[1]
    matched_family_term = binder["position_matched_generality_term_association"][
        "caliper_0_25"
    ]
    assert matched_family_term["human"]["eligible_proofs"] == 245
    assert matched_family_term["ai"]["eligible_proofs"] == 199
    for side in ("human", "ai"):
        assert matched_family_term[side]["zero_term_use"]["source_cluster_ci"][1] < 0
        assert matched_family_term[side]["zero_term_use"][
            "leave_one_source_out_range"
        ][1] < 0
    assert matched_family_term["human"]["multi_term_use"]["source_cluster_ci"][0] > 0
    assert matched_family_term["human"]["multi_term_use"][
        "leave_one_source_out_range"
    ][0] > 0
    matched_ai_multi = matched_family_term["ai"]["multi_term_use"]["source_cluster_ci"]
    assert matched_ai_multi[0] < 0 < matched_ai_multi[1]
    matched_interaction = matched_family_term["paired_both_tracks"]
    assert matched_interaction["eligible_pairs"] == 79
    for metric in ("zero_term_use", "one_term_use", "multi_term_use"):
        lo, hi = matched_interaction[metric]["source_cluster_ci"]
        assert lo < 0 < hi
    unambiguous_family_term = binder[
        "position_matched_generality_term_unambiguous_sensitivity"
    ]["caliper_0_25"]
    for side in ("human", "ai"):
        assert unambiguous_family_term[side]["zero_term_use"]["source_cluster_ci"][1] < 0
    assert unambiguous_family_term["human"]["multi_term_use"]["source_cluster_ci"][0] > 0
    unambiguous_ai_multi = unambiguous_family_term["ai"]["multi_term_use"][
        "source_cluster_ci"
    ]
    assert unambiguous_ai_multi[0] < 0 < unambiguous_ai_multi[1]
    tree = binder["root_tree_representation"]
    assert tree["human"]["max_decimal_digits"] == 11
    assert tree["ai"]["max_decimal_digits"] == 535
    assert tree["ai"]["tasks_at_least_100_digits"] == 3

    boundary_pulse = surprise["paired"]["mean_boundary_excess_nll"]
    assert boundary_pulse["n_pairs"] == 169
    close(boundary_pulse["human_median"], 0.3336)
    close(boundary_pulse["ai_median"], 0.0204)
    assert boundary_pulse["source_cluster_ci"][1] < 0
    content_pulse = surprise["paired"]["mean_content_boundary_excess_nll"]
    close(content_pulse["human_median"], 0.1751)
    close(content_pulse["ai_median"], 0.0355)
    assert content_pulse["source_cluster_ci"][1] < 0
    within_generality = surprise["within_document_generality"]
    assert within_generality["human"]["content_boundary_excess_nll"]["documents"] == 22
    assert within_generality["ai"]["content_boundary_excess_nll"]["documents"] == 19
    assert within_generality["human"]["content_boundary_excess_nll"]["wilcoxon_p"] > 0.05
    close(within_generality["ai"]["content_boundary_excess_nll"]["wilcoxon_p"], 0.04013)
    assert loso_provenance["documents"] == 624
    assert loso_provenance["documents_labeled_unknown_source"] == 2
    assert len(loso_provenance["token_offsets_sha256"]) == 64
    assert loso["paired"]["mean_boundary_excess_nll"]["wilcoxon_p"] < 0.05
    assert loso["paired"]["mean_content_boundary_excess_nll"]["wilcoxon_p"] > 0.05
    assert loso["paired"]["mean_boundary_excess_nll"]["source_cluster_ci"][1] < 0
    assert loso["paired"]["mean_content_boundary_excess_nll"]["source_cluster_ci"][1] < 0

    assert name_mean["pairs"] == 229 and name_last["pairs"] == 229
    for summary in (name_mean, name_last):
        lo, hi = summary["metrics"]["retrieval_percentile"]["source_cluster_ci"]
        assert lo < 0 < hi
        lo, hi = summary["metrics"]["top1_excess_chance"]["source_cluster_ci"]
        assert lo < 0 < hi
    equal_names = name_mean["equal_claim_count_sensitivity"]["top1"]
    assert equal_names["pairs"] == 61
    assert abs(equal_names["ai_minus_human"]) < 0.01

    assert term["n_pairs"] == 298
    lo, hi = term["metrics"]["alpha_x10"]["cluster_ci"]
    assert lo < 0 < hi
    assert term["metrics"]["max_outdeg"]["median_paired_diff"] == 0

    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    assert abstract
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", abstract.group(1))
    assert len(words) < 200, len(words)
    assert pdf.exists()
    assert "References" not in page_text(pdf, 10)
    assert "References" in page_text(pdf, 11)
    assert "Reproducibility and robustness" in page_text(pdf, 13)
    print({"source_pairs": 3630, "term_pairs": 3630, "abstract_words": len(words),
           "main_text_pages": 10})


if __name__ == "__main__":
    main()
