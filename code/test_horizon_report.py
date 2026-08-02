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
        (ROOT / "results/horizon/name_retrieval_last_summary.json").read_text()
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
    close(source["claim_rates"]["human"]["explicit_uses_per_claim"]["estimate"], 1.4423)
    close(source["claim_rates"]["ai"]["explicit_uses_per_claim"]["estimate"], 0.8678)
    close(source["claim_rates"]["human"]["zero_uptake_share"]["estimate"], 0.2219)
    close(source["claim_rates"]["ai"]["zero_uptake_share"]["estimate"], 0.3632)
    close(source["claim_rates"]["human"]["multi_uptake_share"]["estimate"], 0.2650)
    close(source["claim_rates"]["ai"]["multi_uptake_share"]["estimate"], 0.1207)
    parametric = source["parametric_claim_difference"]
    close(parametric["human"], 0.02890)
    close(parametric["ai"], 0.00206)
    assert parametric["source_cluster_ci"][1] < 0
    parametric_profiles = source["parametric_claim_profiles"]
    assert parametric_profiles["human"]["claims"] == 431
    assert parametric_profiles["ai"]["claims"] == 53
    close(parametric_profiles["human"]["multi_uptake_share"], 0.5336)
    close(parametric_profiles["ai"]["multi_uptake_share"], 0.5660)
    assert source["parametric_proof_pair_audit"] == {
        "human_any": 247,
        "ai_any": 29,
        "both": 27,
        "human_only": 220,
        "ai_only": 2,
        "neither": 3381,
    }
    generalized = source["generalized_claim_difference"]
    close(generalized["human"], 0.05600)
    close(generalized["ai"], 0.01909)
    assert generalized["source_cluster_ci"][1] < 0
    assert source["generalized_proof_pair_audit"] == {
        "human_any": 491,
        "ai_any": 279,
        "both": 171,
        "human_only": 320,
        "ai_only": 108,
        "neither": 3031,
    }
    family_function = source["within_proof_feature_associations"]["generalized_claim"]
    assert family_function["human"]["eligible_proofs"] == 401
    assert family_function["ai"]["eligible_proofs"] == 271
    assert family_function["human"]["adopted"]["source_cluster_ci"][0] > 0
    assert family_function["ai"]["multi_uptake"]["source_cluster_ci"][0] > 0
    paired_family = family_function["paired_both_tracks"]
    assert paired_family["eligible_pairs"] == 129
    assert paired_family["multi_uptake"]["source_cluster_ci"][0] > 0
    position_family = source["position_matched_family_associations"]["caliper_0_25"]
    assert position_family["human"]["eligible_proofs"] == 269
    assert position_family["ai"]["eligible_proofs"] == 226
    for side in ("human", "ai"):
        assert position_family[side]["adopted"]["source_cluster_ci"][0] > 0
        assert position_family[side]["multi_uptake"]["source_cluster_ci"][0] > 0
    no_native_decide = source["automation_exclusion_sensitivity"]["native_decide"]
    assert no_native_decide["pairs"] == 3214
    close(no_native_decide["generalized_claim_share"]["human"], 0.05353)
    close(no_native_decide["generalized_claim_share"]["ai"], 0.01919)
    assert no_native_decide["generalized_claim_share"]["source_cluster_ci"][1] < 0
    coordinates = source["interface_coordinate_correlations"]
    assert coordinates["pairs_with_claims_on_both_sides"] == 1883
    close(coordinates["spearman"]["explicit_uses"]["long_reach"], 0.3230, 0.002)
    count_matched = source["claim_count_sensitivity"]["exact_equal_positive"]
    assert count_matched["pairs"] == 210
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
    close(reach["adoption_probability"]["human"], 0.7781)
    close(reach["adoption_probability"]["ai"], 0.6368)
    close(reach["explicit_use_count_given_adoption"]["human"], 1.8533)
    close(reach["explicit_use_count_given_adoption"]["ai"], 1.3627)
    assert reach["explicit_use_count_given_adoption"]["source_cluster_ci"][1] < 0
    close(reach["last_use_token_distance_given_adoption"]["human"], 56.7723)
    close(reach["last_use_token_distance_given_adoption"]["ai"], 43.0957)
    assert reach["last_use_token_distance_given_adoption"]["source_cluster_ci"][1] < 0
    crossing = reach["crosses_any_later_boundary_given_adoption_and_opportunity"]
    close(crossing["human"], 0.7511)
    close(crossing["ai"], 0.7520)
    assert crossing["source_cluster_ci"][0] < 0 < crossing["source_cluster_ci"][1]
    normalized_reach = reach["fraction_available_boundaries_crossed_given_adoption"]
    close(normalized_reach["human"], 0.4912)
    close(normalized_reach["ai"], 0.4543)
    assert normalized_reach["source_cluster_ci"][1] < 0
    reach_controls = source["uptake_reach_matched_controls"]
    equal_claims = reach_controls["exact_equal_positive_claim_count"]
    assert equal_claims["pairs"] == 210
    equal_profile = equal_claims["profile"]
    assert equal_profile["adoption_probability"]["source_cluster_ci"][1] < 0
    assert equal_profile["fraction_available_boundaries_crossed_given_adoption"][
        "source_cluster_ci"
    ][0] > 0
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
    assert unique_names["explicit_uses_per_claim"]["human_claims"] == 9985
    assert unique_names["explicit_uses_per_claim"]["ai_claims"] == 15149
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
    assert binder["source_claim_retention_complete_pairs"]["human"]["denominator"] == 14911
    close(binder["claim_rates_complete_pairs"]["human"]["zero_term_use"]["estimate"], 0.0971)
    close(binder["claim_rates_complete_pairs"]["ai"]["zero_term_use"]["estimate"], 0.2170)
    close(binder["claim_rates_complete_pairs"]["human"]["one_term_use"]["estimate"], 0.5816)
    close(binder["claim_rates_complete_pairs"]["ai"]["one_term_use"]["estimate"], 0.4420)
    close(binder["claim_rates_complete_pairs"]["human"]["multi_term_use"]["estimate"], 0.3213)
    close(binder["claim_rates_complete_pairs"]["ai"]["multi_term_use"]["estimate"], 0.3411)
    zero_delta = binder["claim_rate_differences_complete_pairs"]["zero_term_use"]
    multi_delta = binder["claim_rate_differences_complete_pairs"]["multi_term_use"]
    polarized_delta = binder["claim_rate_differences_complete_pairs"]["polarized_term_use"]
    assert zero_delta["source_cluster_ci"][0] > 0
    assert multi_delta["source_cluster_ci"][0] < 0 < multi_delta["source_cluster_ci"][1]
    assert polarized_delta["source_cluster_ci"][0] > 0
    conditional_multi = binder["multi_term_use_conditional_on_retention"]
    close(conditional_multi["human"]["estimate"], 0.3559)
    close(conditional_multi["ai"]["estimate"], 0.4356)
    assert conditional_multi["ai_minus_human"]["source_cluster_ci"][0] > 0
    family_term = binder["within_proof_generality_term_association"]
    assert family_term["human"]["proofs"] == 395
    assert family_term["ai"]["proofs"] == 271
    for side in ("human", "ai"):
        assert family_term[side]["zero_term_use"]["source_cluster_ci"][1] < 0
    assert family_term["human"]["multi_term_use"]["source_cluster_ci"][0] > 0
    ai_family_multi = family_term["ai"]["multi_term_use"]["source_cluster_ci"]
    assert ai_family_multi[0] < 0 < ai_family_multi[1]
    matched_family_term = binder["position_matched_generality_term_association"][
        "caliper_0_25"
    ]
    assert matched_family_term["human"]["eligible_proofs"] == 263
    assert matched_family_term["ai"]["eligible_proofs"] == 226
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
    assert matched_interaction["eligible_pairs"] == 85
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

    assert surprise["paired"]["mean_boundary_excess_nll"]["n_pairs"] == 177
    close(surprise["paired"]["mean_boundary_excess_nll"]["human_median"], 0.3571)
    close(surprise["paired"]["mean_boundary_excess_nll"]["ai_median"], 0.0278)
    within_generality = surprise["within_document_generality"]
    assert within_generality["human"]["content_boundary_excess_nll"]["documents"] == 23
    assert within_generality["ai"]["content_boundary_excess_nll"]["documents"] == 22
    assert within_generality["human"]["content_boundary_excess_nll"]["wilcoxon_p"] > 0.05
    assert within_generality["ai"]["content_boundary_excess_nll"]["wilcoxon_p"] > 0.05
    assert loso_provenance["documents"] == 624
    assert loso_provenance["documents_labeled_unknown_source"] == 2
    assert len(loso_provenance["token_offsets_sha256"]) == 64
    assert loso["paired"]["mean_boundary_excess_nll"]["wilcoxon_p"] < 0.05
    assert loso["paired"]["mean_content_boundary_excess_nll"]["wilcoxon_p"] > 0.05

    assert name_mean["pairs"] == 230 and name_last["pairs"] == 230
    for summary in (name_mean, name_last):
        lo, hi = summary["metrics"]["retrieval_percentile"]["source_cluster_ci"]
        assert lo < 0 < hi
        lo, hi = summary["metrics"]["top1_excess_chance"]["source_cluster_ci"]
        assert lo < 0 < hi
    equal_names = name_mean["equal_claim_count_sensitivity"]["top1"]
    assert equal_names["pairs"] == 57
    assert abs(equal_names["ai_minus_human"]) < 0.003

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
