"""Fail-closed audit for the standalone paper's quantitative and editorial claims."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "report/standalone/main.tex"
NUMBERS = ROOT / "report/standalone/numbers.tex"
OUT = ROOT / "results/paper_claim_audit.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def close(actual: float, expected: float, tolerance: float, label: str) -> None:
    require(abs(actual - expected) <= tolerance, f"{label}: {actual} != {expected}")


def macro_map(text: str) -> dict[str, str]:
    return dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", text))


def numeric_macro(macros: dict[str, str], name: str) -> float:
    return float(macros[name].replace(",", ""))


def abstract_word_count() -> int:
    source = TEX.read_text()
    abstract = source.split("\\begin{abstract}", 1)[1].split("\\end{abstract}", 1)[0]
    for name, value in sorted(macro_map(NUMBERS.read_text()).items(),
                              key=lambda item: -len(item[0])):
        abstract = abstract.replace(f"\\{name}{{}}", value).replace(f"\\{name}", value)
    result = subprocess.run(
        ["detex"], input=abstract, text=True, capture_output=True, check=True
    )
    return len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", result.stdout))


def citation_keys(tex: str) -> set[str]:
    found = set()
    for block in re.findall(r"\\cite[tp]?\{([^}]*)\}", tex):
        found.update(key.strip() for key in block.split(","))
    return found


def bibliography_keys() -> set[str]:
    text = "\n".join(
        (ROOT / path).read_text()
        for path in ("report/final/references.bib", "report/standalone/references_extra.bib")
    )
    return set(re.findall(r"^@\w+\{([^,]+),", text, flags=re.MULTILINE))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    tex = TEX.read_text()
    macros = macro_map(NUMBERS.read_text())
    paired = json.loads((ROOT / "results/standalone_paper/summary.json").read_text())
    historical = json.loads(
        (ROOT / "results/coq_lean_confirmation_xmin10/summary.json").read_text()
    )
    coq_tail_fits = read_csv(
        ROOT / "results/coq_lean_confirmation_xmin10/coq_model_comparisons_xmin10.csv"
    )
    lean_tail_fits = read_csv(
        ROOT / "results/coq_lean_confirmation_xmin10/lean_model_comparisons_xmin10.csv"
    )
    extraction = json.loads(
        (ROOT / "results/paired_term_structure/extraction_counts.json").read_text()
    )
    source_rows = read_csv(ROOT / "results/paired_numina_corrected.csv")
    term_rows = read_csv(ROOT / "results/paired_term_structure/term0.csv")
    belief_rows = read_csv(ROOT / "results/final_synthesis/paired_belief_term0_r32.csv")
    belief_metadata = json.loads(
        (ROOT / "results/final_synthesis/paired_belief_term0_r32.json").read_text()
    )
    checks = []

    # Design and sample accounting.
    require({key: paired[key] for key in (
        "source_pairs", "term_pairs", "source_groups", "term_source_groups",
        "bootstraps", "seed"
    )} == {
        "source_pairs": 2321,
        "term_pairs": 312,
        "source_groups": 12,
        "term_source_groups": 12,
        "bootstraps": 20000,
        "seed": 20260801,
    }, "paired design changed")
    require(historical["design"]["human_lean_term_networks"] == 33, "Lean term n")
    require(historical["design"]["published_coq_networks"] == 47, "published Coq n")
    require(historical["design"]["recovered_coq_networks"] == 49, "recovered Coq n")
    require(historical["design"]["coq_edge_networks_refit"] == 49 and
            historical["design"]["lean_edge_networks_refit"] == 33 and
            historical["design"]["tail_xmin"] == 10,
            "fixed-tail edge-fit design changed")
    require(len(source_rows) == 2321, "corrected source row count")
    require(len(term_rows) == len(belief_rows) == 312, "term/belief row count")
    require(extraction["paired_term0_ids"] == 494 and
            extraction["clean_paired_term0_ids"] == 312,
            "eligible/clean term accounting")
    require({row["pair"] for row in term_rows} == {row["pair"] for row in belief_rows},
            "term and belief IDs differ")
    require(all(float(row[side]) == 1.0 for row in belief_rows
                for side in ("h_root_component_share", "a_root_component_share")),
            "a retained belief graph is not wholly in the theorem-root component")
    require(all(row["h_has_sorry"] == row["a_has_sorry"] == "False"
                for row in term_rows), "an error-recovery term entered the clean sample")
    require(all(row["h_n_constants"] == row["h_n_distinct_constants"] and
                row["a_n_constants"] == row["a_n_distinct_constants"]
                for row in term_rows), "constant vertices are not structurally distinct")
    require(all(int(row[side]) >= 1 for row in source_rows
                for side in ("h_n_lines", "a_n_lines",
                             "h_n_premise_refs", "a_n_premise_refs")),
            "a corrected source proof lacks a measurable body or premise-like reference")
    source_ids = {"pair_" + row["uuid"][:8] for row in source_rows}
    require(len(source_ids & {row["pair"] for row in term_rows}) == 184,
            "source/term overlap changed")
    require({key: belief_metadata[key] for key in ("n_pairs", "runs", "sweeps")} ==
            {"n_pairs": 312, "runs": 32, "sweeps": 10},
            "belief simulation design changed")
    checks.append("sample accounting")

    # Headline paired estimates and the macros that enter prose.
    close(paired["source"]["line_pair_correlation"]["spearman_rho"], numeric_macro(macros, "LineRho"), .005, "line rho")
    close(paired["term"]["node_pair_correlation"]["spearman_rho"], numeric_macro(macros, "NodeRho"), .005, "node rho")
    close(paired["source"]["have_per_tactic"]["median_ratio"], numeric_macro(macros, "HaveRatio"), .005, "have ratio")
    close(paired["term"]["interior_per_constant"]["median_ratio"], numeric_macro(macros, "InteriorRatio"), .005, "interior ratio")
    close(paired["belief"]["three_condition_average"]["mean_paired_difference"], numeric_macro(macros, "BeliefDifference"), .000005, "belief difference")
    close(paired["belief"]["interior_belief_correlation"]["spearman_rho"], numeric_macro(macros, "DecouplingRho"), .0005, "decoupling rho")
    require(paired["cross_layer"]["n_overlap"] == int(macros["CrossLayerN"]), "cross-layer n")
    close(paired["cross_layer"]["spearman_rho"], numeric_macro(macros, "CrossLayerRho"), .005, "cross-layer rho")
    checks.append("same-theorem estimates and manuscript macros")

    # Historical tail and replication claims.
    recovery = historical["published_exponent_recovery"]
    require(recovery["refit_available_n"] == 44, "estimable published exponents")
    require(recovery["absolute_difference_le_0_01"] == 40, "exponents within .01")
    require(recovery["absolute_difference_le_0_02"] == 43, "exponents within .02")
    close(recovery["median_absolute_difference"], .003, 1e-12, "median alpha discrepancy")
    coq = historical["fixed_xmin_10_alpha"]["coq"]
    lean = historical["fixed_xmin_10_alpha"]["human_lean_terms_edge_refit"]
    close(coq["median"], numeric_macro(macros, "CoqAlpha"), .0005, "Coq alpha10")
    close(lean["median"], numeric_macro(macros, "LeanAlpha"), .0005, "Lean alpha10")
    comparison = historical["fixed_xmin_10_comparison"]
    close(comparison["u"], 895.0, 1e-12, "Coq--Lean Mann--Whitney U")
    close(comparison["p"], .1242208914, 1e-10, "Coq--Lean Mann--Whitney p")
    require(historical["model_comparisons"]["coq_out_degree"]["exponential"] == {
        "n": 45, "power_law_favored": 43, "alternative_favored": 0, "inconclusive": 2
    }, "Coq fixed-tail exponential comparison")
    require(historical["model_comparisons"]["coq_out_degree"]["lognormal"] == {
        "n": 45, "power_law_favored": 0, "alternative_favored": 2, "inconclusive": 43
    }, "Coq fixed-tail lognormal comparison")
    require(historical["model_comparisons"]["human_lean_out_degree"]["exponential"] == {
        "n": 33, "power_law_favored": 33, "alternative_favored": 0, "inconclusive": 0
    }, "Lean fixed-tail exponential comparison")
    require(historical["model_comparisons"]["human_lean_out_degree"]["lognormal"] == {
        "n": 33, "power_law_favored": 0, "alternative_favored": 0, "inconclusive": 33
    }, "Lean fixed-tail lognormal comparison")
    require(len(coq_tail_fits) == 49 and len(lean_tail_fits) == 33,
            "fixed-tail fit row count")
    require(all(float(row["out_xmin"]) == 10 for row in coq_tail_fits + lean_tail_fits),
            "a model comparison did not hold xmin at 10")
    require(sum(bool(row.get("out_p_power_vs_lognormal")) for row in coq_tail_fits) == 45 and
            sum(bool(row.get("out_p_power_vs_lognormal")) for row in lean_tail_fits) == 33,
            "fixed-tail lognormal eligibility changed")
    checks.append("fixed-xmin Coq--Lean confirmation")

    # The exact artifact that was reproduced on ORCHARD and cited in the appendix.
    archive = ROOT / "results/standalone_paper/standalone_paper_outputs.tar.gz"
    require(sha256(archive) ==
            "b90b31e99003d40ffdc9e8bad9a027d00d6302cc2798d7c4cf9a520468de48c4",
            "ORCHARD result archive checksum")
    checks.append("ORCHARD artifact identity")

    # Monte Carlo and implementation sanity checks.  The earlier 8-chain run
    # is not used for inference, but gives an independent convergence check on
    # the near-zero population contrast.
    belief8 = read_csv(ROOT / "results/final_synthesis/paired_belief_term0.csv")
    require({row["pair"] for row in belief8} == {row["pair"] for row in belief_rows},
            "8- and 32-chain pair sets differ")

    def paired_belief_average(row: dict[str, str]) -> float:
        return sum(float(row[f"a_theorem_{eps}"]) - float(row[f"h_theorem_{eps}"])
                   for eps in ("0.1", "0.05", "0.01")) / 3.0

    mean8 = statistics.fmean(paired_belief_average(row) for row in belief8)
    mean32 = statistics.fmean(paired_belief_average(row) for row in belief_rows)
    require(abs(mean8) < .002 and abs(mean32) < .002,
            "near-zero belief contrast is not stable across chain counts")
    sanity = (ROOT / "results/test_toolkit.log").read_text()
    chain = re.search(r"chain n=200.*?([0-9.]+).*?expect low", sanity)
    copy = re.search(r"eps=0\.010\s+mean=([0-9.]+)\s+thm=([0-9.]+)", sanity)
    paradox = re.search(r"certainty\(abd=0\.99\)=([0-9.]+).*?abd=0\.9999\)=([0-9.]+)", sanity)
    require(chain and float(chain.group(1)) < .75, "chain sanity check")
    require(copy and float(copy.group(1)) >= .99 and float(copy.group(2)) >= .99,
            "copy-model EPT sanity check")
    require(paradox and float(paradox.group(2)) < float(paradox.group(1)),
            "abductive-paradox sanity check")
    checks.append("belief dynamics and Monte Carlo sensitivity")

    # Model-level qualifications that prevent overclaiming.
    require(historical["endpoint_checks"]["coq_all_firewall_scores_positive"], "Coq firewalls")
    require(historical["endpoint_checks"]["human_lean_all_firewall_scores_positive"], "Lean firewalls")
    flat_tex = re.sub(r"\s+", " ", tex)
    required_phrases = (
        "model implication, not a measurement of a reader",
        "they are not equivalence tests",
        "Nor does ``more interior'' mean ``less understanding.''",
        "We do not confirm a universal, cutoff-free pure power law",
        "The belief result is not behavioral evidence",
    )
    for phrase in required_phrases:
        require(phrase in flat_tex, f"missing qualification: {phrase}")
    require(r"\frac{|V(G(P))|-|C_V(P)|}{|C_D(P)|+1}" in tex,
            "interior-load equation no longer distinguishes vertices from declarations")
    checks.append("scope and non-equivalence qualifications")

    # Editorial requirements.
    words = abstract_word_count()
    require(words < 250, f"abstract has {words} words")
    require(tex.lower().count("epistemic decoupling") >= 10, "thesis is not organizing the paper")
    labels = re.findall(r"\\label\{([^}]+)\}", tex)
    require(len(labels) == len(set(labels)), "duplicate LaTeX labels")
    lines = [re.sub(r"\s+", " ", line.strip()) for line in tex.splitlines() if line.strip()]
    require(not any(left == right for left, right in zip(lines, lines[1:])),
            "duplicate adjacent source lines")
    cited = citation_keys(tex)
    missing = cited - bibliography_keys()
    require(not missing, f"missing bibliography keys: {sorted(missing)}")
    bib_text = (ROOT / "report/final/references.bib").read_text() + \
        (ROOT / "report/standalone/references_extra.bib").read_text()
    for identifier in (
        "10.1016/j.cognition.2022.105120", "arXiv:2603.13680",
        "arXiv:2606.03743", "arXiv:2606.04273", "arXiv:2504.21801",
        "10.1038/s41586-025-09833-y", "10.1007/s11245-025-10164-w",
    ):
        require(identifier in bib_text, f"missing verified bibliographic identifier: {identifier}")
    checks.append("abstract, thesis focus, labels, duplication, and citations")

    report = {
        "status": "pass",
        "abstract_words_detex": words,
        "checks": checks,
        "evidence": {
            "paired_summary": "results/standalone_paper/summary.json",
            "historical_summary": "results/coq_lean_confirmation_xmin10/summary.json",
            "manuscript": "report/standalone/main.tex",
        },
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
