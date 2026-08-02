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
    close(source["claim_rates"]["human"]["explicit_uses_per_claim"]["estimate"], 1.4190)
    close(source["claim_rates"]["ai"]["explicit_uses_per_claim"]["estimate"], 0.8646)
    close(source["claim_rates"]["human"]["zero_uptake_share"]["estimate"], 0.2289)
    close(source["claim_rates"]["ai"]["zero_uptake_share"]["estimate"], 0.3638)
    close(source["claim_rates"]["human"]["multi_uptake_share"]["estimate"], 0.2570)
    close(source["claim_rates"]["ai"]["multi_uptake_share"]["estimate"], 0.1199)
    count_matched = source["claim_count_sensitivity"]["exact_equal_positive"]
    assert count_matched["pairs"] == 211
    assert count_matched["explicit_uses_per_claim"]["source_cluster_ci"][1] < 0
    assert count_matched["zero_uptake_share"]["source_cluster_ci"][0] > 0
    unique_names = source["nonredeclared_name_sensitivity"]
    assert unique_names["explicit_uses_per_claim"]["human_claims"] == 9584
    assert unique_names["explicit_uses_per_claim"]["ai_claims"] == 15102
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

    assert binder["pairs_with_both_sides"] == 298
    close(binder["claim_rates_complete_pairs"]["human"]["zero_term_use"]["estimate"], 0.1400)
    close(binder["claim_rates_complete_pairs"]["ai"]["zero_term_use"]["estimate"], 0.2335)
    close(binder["claim_rates_complete_pairs"]["human"]["multi_term_use"]["estimate"], 0.3505)
    close(binder["claim_rates_complete_pairs"]["ai"]["multi_term_use"]["estimate"], 0.3586)
    zero_delta = binder["claim_rate_differences_complete_pairs"]["zero_term_use"]
    multi_delta = binder["claim_rate_differences_complete_pairs"]["multi_term_use"]
    assert zero_delta["source_cluster_ci"][0] > 0
    assert multi_delta["source_cluster_ci"][0] < 0 < multi_delta["source_cluster_ci"][1]

    assert surprise["paired"]["mean_boundary_excess_nll"]["n_pairs"] == 174
    close(surprise["paired"]["mean_boundary_excess_nll"]["human_median"], 0.3445)
    close(surprise["paired"]["mean_boundary_excess_nll"]["ai_median"], 0.0241)
    assert loso_provenance["documents"] == 624
    assert loso_provenance["documents_labeled_unknown_source"] == 2
    assert len(loso_provenance["token_offsets_sha256"]) == 64
    assert loso["paired"]["mean_boundary_excess_nll"]["wilcoxon_p"] < 0.05
    assert loso["paired"]["mean_content_boundary_excess_nll"]["wilcoxon_p"] > 0.05

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
    print({"source_pairs": 3630, "term_pairs": 298, "abstract_words": len(words),
           "main_text_pages": 10})


if __name__ == "__main__":
    main()
