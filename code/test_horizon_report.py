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
    term = json.loads((ROOT / "results/horizon/scoped_term_structure/term0.json").read_text())
    tex = (ROOT / "report/horizon/main.tex").read_text()
    pdf = ROOT / "output/pdf/proofs_for_now_and_proofs_for_later.pdf"

    assert source["pairs"] == 3635 and source["source_groups"] == 12
    close(source["claim_rates"]["human"]["explicit_uses_per_claim"]["estimate"], 1.4197)
    close(source["claim_rates"]["ai"]["explicit_uses_per_claim"]["estimate"], 0.8643)
    close(source["claim_rates"]["human"]["zero_uptake_share"]["estimate"], 0.2277)
    close(source["claim_rates"]["ai"]["zero_uptake_share"]["estimate"], 0.3639)
    close(source["claim_rates"]["human"]["multi_uptake_share"]["estimate"], 0.2576)
    close(source["claim_rates"]["ai"]["multi_uptake_share"]["estimate"], 0.1198)

    assert binder["pairs_with_both_sides"] == 298
    close(binder["claim_rates_complete_pairs"]["human"]["zero_term_use"]["estimate"], 0.1400)
    close(binder["claim_rates_complete_pairs"]["ai"]["zero_term_use"]["estimate"], 0.2335)
    close(binder["claim_rates_complete_pairs"]["human"]["multi_term_use"]["estimate"], 0.3505)
    close(binder["claim_rates_complete_pairs"]["ai"]["multi_term_use"]["estimate"], 0.3586)

    assert surprise["paired"]["mean_boundary_excess_nll"]["n_pairs"] == 174
    close(surprise["paired"]["mean_boundary_excess_nll"]["human_median"], 0.3445)
    close(surprise["paired"]["mean_boundary_excess_nll"]["ai_median"], 0.0241)

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
    print({"source_pairs": 3635, "term_pairs": 298, "abstract_words": len(words),
           "main_text_pages": 10})


if __name__ == "__main__":
    main()
