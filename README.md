# Proof networks in the age of AI

Extending Viteri & DeDeo, *Epistemic phase transitions in mathematical proofs*
(Cognition 225:105120, 2022) to machine-generated mathematics.

**Start here:** [`report/REPORT.md`](report/REPORT.md).

**Latest standalone paper:** [*Epistemic Decoupling in Human and Machine
Proofs*](output/pdf/epistemic_decoupling_human_ai_proofs.pdf), with LaTeX source in
[`report/standalone/`](report/standalone/).

**For Scott Viteri and other readers of the 2022 work:**
[`SCOTT_GUIDE.md`](SCOTT_GUIDE.md) gives a short route through the new results,
documents the exact connection to
[`scottviteri/ManipulateProofTrees`](https://github.com/scottviteri/ManipulateProofTrees),
and isolates the remaining question about the original power-law convention.

**Reviewing this work?** [`REVIEW.md`](REVIEW.md) maps every claim in the report to the script and
output file that produced it, lists the seven claims withdrawn during the work and why, and names
the places the work is weakest. [`results/DATA_INVENTORY.md`](results/DATA_INVENTORY.md) enumerates
the bulk reproducibility data. These data are excluded from Git, but are mirrored both in this
working directory on Simon's Mac and at `akdeniz.lan.cmu.edu:~/ai_math_ept/`.

## What was found, in one paragraph

The 2022 results replicate across a change of proof assistant, four years, and a tenfold larger
library — and Table 1 itself reproduces once the fixed tail-cutoff convention is recovered (40 of 47
networks within 0.010 of the published α). Applied to AI-generated mathematics, the headline is
narrower than "AI proofs are structurally different," because at matched difficulty most apparent
differences dissolve: the theorem explains far more structural variance than the system does, and
one system resampled on one theorem varies more than systems differ from each other. What survives
every control is a paired result. Given **2,583 statements with both a validated human proof and a
validated machine proof**, proof length is statistically identical (p = 0.20) while the machine
cites **half as many distinct library results** (10 → 5) and introduces **twice as many inline
`have` steps** (3 → 6). Where a human reaches for an existing lemma, the machine builds the step
itself. Scaled to a corpus, that is the accumulation deficit measured directly: the
machine-generated files of the Equational Theories Project have 98.3% of declarations never cited
against 45.6% for the human files of the same project. **Machine-generated mathematics verifies but
does not accumulate.**

## Layout

| path | contents |
|---|---|
| `code/` | analysis toolkit (below) |
| `results/` | derived results: CSVs, JSONs, per-study outputs, logs |
| `report/` | working report + figures |
| `output/pdf/` | versioned final paper PDFs |
| `networks/`, `original_data/`, `corpora/`, `census/`, `projects/`, `mathlib4/` | local, Git-ignored reproducibility cache mirrored from Akdeniz |
| `REVIEW.md` | reviewer's guide: claim → script → output, withdrawn claims, weak points |
| `sync.sh` | pull code + results from akdeniz, commit, push |

## Toolkit

| file | what it does |
|---|---|
| `ExtractNetwork.lean` | Lean 4 metaprogram: proof term → dependency DAG (`term0` raw term, `term` level-expanded, `decl` declaration-level). The Lean analogue of the 2022 CoqAST/ManipulateProofTrees pipeline. |
| `extract_corpus.py` | batch-elaborates a corpus of standalone `.lean` proofs (handles syntax drift, namespaces, per-corpus toolchains) |
| `proofnet.py` | network construction + structural statistics (degree distributions, power-law fits, modularity, DAG depth) |
| `belief.py` | the asymmetric-Ising belief model (numba): certainty curves, f₂, contour grids, ΔL₁ firewalls |
| `census.py` | two-tier structural census; Tier 1 needs no compilation and scales to any repo |
| `paired_numina.py` | **the key experiment**: human vs AI proofs of identical statements |
| `matched_leaneval.py`, `matched_hf.py` | matched-theorem experiments across prover systems |
| `within_system.py` | within-system noise floor (the control that calibrates the above) |
| `repro_xmin.py`, `implied_xmin.py`, `xmin_robust.py`, `repro_alpha.py` | reproduction of Table 1 and the x_min-convention analysis |
| `repro_validate.py` | power-law vs alternative distributions; random-DAG null models |
| `convert_coq_dags.py`, `convert_hand_networks.py` | import the 2022 paper's own machine and hand-coded networks |
| `study4_etp.py`, `study4b_vampire.py`, `etp_belief.py` | Equational Theories Project: skeleton, percolation, ATP difficulty census |
| `study5_mathlib.py` | belief dynamics on all of Mathlib (308k declarations, 8.4M edges) |
| `study6`–`study9` | ETP provenance, automation dose–response, source-level cross-project graphs, matched pairs |
| `run_overnight.sh`, `phase2.sh` | unattended job chain |
| `test_toolkit.py` | sanity suite: chains show no EPT, tinkering DAGs do, abductive paradox reproduces |

## Reproducing the 2022 paper

`repro_xmin.py` shows Table 1 reproduces to within 0.010 on 40 of 47 networks using a **fixed** tail
cutoff x_min ≈ 10. It does *not* reproduce under Clauset–Shalizi–Newman's KS-selected x_min, which
chooses x_min ≈ 1 on these degree sequences because the distribution is power-law-like all the way
down. Any α quoted for a proof network should carry its x_min: the two conventions differ by ≈0.2
and correlate at zero.

`repro_validate.py` then checks the structural claim against null models: the out-degree beats an
exponential in 47 of 47 networks and is significantly heavier-tailed than size- and density-matched
random DAGs (α 2.27 vs 2.75), so heavy-tailed reuse is a fact about proofs rather than an artifact
of the fit. It is *not* separable from a lognormal, which is the standard caveat for power-law
claims and applies to the published values equally.
