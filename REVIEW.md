# Reviewer's guide

This document exists so a reviewer can check the work rather than take it on trust.
The current paper is [`report/horizon/main.tex`](report/horizon/main.tex), rendered
as [`output/pdf/proofs_for_now_and_proofs_for_later.pdf`](output/pdf/proofs_for_now_and_proofs_for_later.pdf).
The older claim map for [`report/REPORT.md`](report/REPORT.md) follows the current
paper audit below.

## 0. Current paper: claim → script → output

| claim | script | output |
|---|---|---|
| 3,630 exact-statement pairs after auditing 3,635 validation-flag candidates; final target body only | `code/paired_horizon.py` | `results/horizon/source_summary.json`, `source_pairs.csv.gz`, `target_pair_exclusions.csv` |
| claim density, explicit uptake, visible reach, naming, and matched tactic strata | same | `results/horizon/claims.csv.gz`, `by_source.csv`, `tactic_matched_strata.csv` |
| depth-aware use of elaborated local binders in 298 complete pairs | `code/extract_binder_use.py`, `code/analyze_binder_use.py` | `results/horizon/binder_summary.json`, `binder_claims.csv.gz` |
| model-relative information pulse at claim boundaries | `code/prepare_surprisal.py`, `code/token_surprisal.cpp`, `code/analyze_surprisal.py`, `code/collect_surprisal_sensitivity.py` | `results/horizon/surprisal_summary_w8.json`, `surprisal_sensitivity.csv`, `surprisal_provenance.json` |
| scope-correct term-DAG construction and 298-pair audit | `code/ExtractNetwork.lean`, `code/ExtractCore.lean.tmpl`, `code/extract_corpus.py`, `code/paired_term_structure.py` | `code/test_scoped_bvars.py`, `results/horizon/scoped_term_structure/` |

The source inclusion audit compares the final structured declaration signatures emitted by the
dataset elaborator, after removing comments and normalizing whitespace. It excludes one prover
artifact with no declaration and four mismatches (a wrong theorem join, a helper-only output, and
two changed propositions). The counts are serialized under `target_pair_audit` in
`source_summary.json`; `code/test_horizon_report.py` makes them a regression condition.

Two source-level failure modes are audited separately. Because the parser stops an explicit-use
window at a same-name redeclaration, `nonredeclared_name_sensitivity` removes every claim whose name
occurs more than once in its proof; all uptake and reach directions strengthen. The structured
proof-value overlap audit finds 181 token-identical values, 180 of which also have identical source
bodies. Excluding all 230 pairs with proof-value token similarity at least .90 leaves 3,400 pairs
and preserves every headline direction.

The primary limitations are observational provenance, lexical recognition of
named `have` rather than every possible source construct, current-Mathlib
compilation attrition in the term sample, and possible training overlap or style
affinity in the Goedel-Prover surprisal assay. The paper treats the last as
exploratory and does not infer human cognitive surprisal from it.
`code/test_horizon_report.py` checks the paper's headline values against the
JSON results, enforces the sub-200-word abstract, and verifies that the
bibliography begins after ten pages of main text.

## 1. Where things are

| what | where | in git? |
|---|---|---|
| analysis code | `code/` | yes |
| derived results (CSV/JSON/logs) | `results/` | yes |
| report + figures | `report/` | yes |
| **extracted proof networks** | `networks/` locally; Akdeniz mirror at `~/ai_math_ept/networks/` | no |
| **downloaded corpora** | `census/`, `corpora/` locally; Akdeniz mirror under `~/ai_math_ept/` | no |
| **formalization projects** | `projects/` locally; Akdeniz mirror at `~/ai_math_ept/projects/` | no |
| Mathlib checkout + olean cache | `mathlib4/` locally; Akdeniz mirror at `~/ai_math_ept/mathlib4/` | no |
| **2022 paper's original archive** | `/Users/simon/Desktop/OLDER_RESEARCH_ARCHIVE/SCOTT` (local, Simon's machine) | no |
| recovered 2022 ProofDAGs + CoqAST | `original_data/` locally; Akdeniz mirror at `~/ai_math_ept/original_data/` | no |

Bulk data is excluded deliberately (size), not to hide it. Simon's working checkout contains a
Git-ignored local mirror, while `results/census_manifests/` carries the collection
manifests, and `results/DATA_INVENTORY.md` records corpus file counts and sizes so
a reviewer can see what exists without SSH access.

The bulk-data mirrors are private working storage, not anonymous download endpoints.
The original Coq DAGs are independently available from Scott Viteri's public
[`ManipulateProofTrees`](https://github.com/scottviteri/ManipulateProofTrees)
repository. Contact Simon for the larger Lean-network and corpus mirrors.

## 2. Claim → script → output map

| report § | claim | script | output |
|---|---|---|---|
| §1 | Table 1 reproduces at fixed x_min ≈ 10 (40/47 within 0.010) | `code/repro_xmin.py` | `results/repro_xmin_best.csv` |
| §1 | CSN auto-x_min picks x_min ≈ 1 here and does *not* reproduce | `code/repro_alpha.py`, `code/implied_xmin.py` | `results/repro_alpha.csv`, `results/implied_xmin.csv` |
| §1 | Coq-vs-Lean α depends on x_min; n.s. near tail, diverges far tail | `code/xmin_robust.py`, `code/refit_xmin10.py` | `results/alpha_xmin10.csv` |
| §1a-bis | hand-coded human networks recovered; Wiles α 3.46 vs 3.39 | `code/convert_hand_networks.py`, `code/hand_alpha.py` | `results/hand_human/` |
| §1b | heavy tail beats exponential 47/47; lognormal not excluded | `code/repro_validate.py` | `results/repro_validate.csv` |
| §1b | α discriminates vs random-DAG null (2.27 / 2.46 / 2.75) | `code/repro_validate.py` | same |
| appendix A.2 | common-schema out-degree sensitivity at fixed x_min=10 | `code/normalized_outdegree_sensitivity.py` | `results/normalized_outdegree/` |
| appendix A.3 | historical native-format Poisson/ZIP replication | `code/poisson_indegree_appendix.py` | `results/poisson_indegree/` |
| appendix A.3 | comparable Coq/Lean local arity after binary normalization | `code/normalized_term_arity.py` | `results/normalized_term_arity/` |
| §2 | AI proof-term tails *heavier* than human (x_min sweep) | `code/refit_xmin10.py`, `code/xmin_robust.py` | `results/alpha_xmin10.csv` |
| §3 | Gauss vs human source census (reuse, duplication, defs) | `results/study3_source/study3.py` | `results/study3_source/` |
| §4/§5a | ETP skeleton, percolation, edge-disjoint paths | `code/study4_etp.py` | `results/study4/etp_stats.json` |
| §4b | all 8.17M true implications one-shot ATP-provable | `code/study4b_vampire.py` | `results/study4/` (partial; see §4 caveats) |
| §5a | belief model on ETP skeleton (0.976 at ε=0.01) | `code/etp_belief.py` | `results/study4/etp_belief.json` |
| §5 | Mathlib-scale belief dynamics (explicit vs full layers) | `code/study5_mathlib.py` | `results/study5/mathlib_ept.json` |
| §5b | human-proved ETP implications carry 5× derivation load | `code/study6_etp_provenance.py` | `results/study6/etp_provenance.json` |
| §5c | automation dose–response (N1 falsified) | `code/study7_dose_response.py` | `results/study7/` |
| §5d | source-level cross-project graphs; ETP generated files Q=0.145 | `code/study8_source_graphs.py` | `results/study8/source_graphs.csv` |
| §5e | census of 137k proofs; vocab ratio by length; corpus-level n.s. | `code/census.py` + `code/LABELS.tsv` | `results/census_all/` |
| §5f | matched-theorem experiment (lean-eval) | `code/matched_leaneval.py` | `results/matched_leaneval/` |
| §5f-bis | large-n replication (HF census) | `code/matched_hf.py` | `results/matched_hf_records.csv.gz` |
| §5f-ter | within-system noise floor | `code/within_system.py` | `results/within_system.csv.gz` |
| §5g | **paired human/AI, same statement** (the key result) | `code/paired_numina.py` | `results/paired_numina.csv` |
| figures | fig1–3 | `code/fig_local.py` | `report/figures/` |

Toolkit internals: `code/proofnet.py` (network construction + structural stats),
`code/belief.py` (the asymmetric-Ising model), `code/ExtractNetwork.lean`
(proof term → DAG), `code/extract_corpus.py` (batch elaboration).
`code/test_toolkit.py` is the sanity suite (chain shows no EPT, tinkering DAG
does, abductive paradox reproduces).

## 3. Claims I withdrew, and why

A reviewer should check these were actually corrected in the report, not just noted.

| withdrawn claim | why | replaced by |
|---|---|---|
| "Lean has thinner reuse tails than Coq (α 2.27→2.47, p=0.0006)" | artifact of CSN auto-x_min | §1: n.s. at x_min ≤ 11; far tail goes the *other* way |
| "ETP is distinguished by lack of independent derivation paths" | classical Coq DAGs measure the same (1.04) | §5a: withdrawn; ETP fragility is derivability-semantics only |
| "ETP is epistemically fragile" | belief model gives 0.976, comparable to proofs | §5a: reframed as storage-minimal, not fragile |
| "vocab ratio separates AI from human corpora (p=5e-120)" | pseudo-replication on 4 corpora; corpus-level p=0.51 | §5e: holds per-proof at matched length, not per-corpus |
| "vocabulary collapse is downstream of verbosity" | paired design holds length fixed, effect undiminished | §5g |
| "`have`-step concordance W=0.73" | did not replicate at scale (W=0.07) | §5f-bis |
| "path disjointness does not distinguish these objects" | too strong — real *vs random* is significant | §1b |
| "native Lean arity is much more concentrated than native Coq arity" | parser artifact: Lean `App` is binary; archived CoqAST `App` is variadic and binder names are children | appendix A.3: common-schema Coq 0.9903 vs Lean 0.9976 degree-two share |
| "expanded-graph out-degree evidence is representation-robust" | normalized root proofs retain similar exponents but usually cannot distinguish power law from exponential | appendix A.2: strong tail evidence restricted to the expanded-network scale |
| "human or AI provenance has a directional effect on the fixed-10 out-degree exponent" | the tiny paired difference reverses from -0.009 in `term0` to +0.025 after proof-value normalization | appendix A.2 and Table 3: no representation-robust authorship effect |
| unexpanded term-DAG reuse is a semantic reuse measure | raw de Bruijn indices from unrelated binder scopes were interned together, creating false shared variable nodes | the extractor now assigns scope-specific identities; current paper uses depth-aware binder occurrence and withdraws old semantic readings of `term0` topology |

## 4. Where I think this is weakest — please attack these first

1. **`code/census.py`'s premise heuristic is a regex.** "Premise-like" = a token
   that is dotted or capitalised and not a Lean keyword. Three headline results
   (§5e, §5g, §5f) lean on it. It will miscount: local hypothesis names like `hx`
   are excluded correctly, but structure projections, French-quote identifiers,
   and `open`ed namespaces are handled crudely. **A reviewer should hand-check a
   sample of proofs against the metric.** An elaborated-term version (Tier 2)
   would be authoritative and is only partly done.
2. **`vocab_ratio` is not the same quantity everywhere.** In `census.py` it is
   computed within one declaration body; in `paired_numina.py` and
   `matched_leaneval.py` distinct premises are counted over the whole submission
   while references are counted over bodies, so it can exceed 1. Only
   within-analysis comparisons are valid. This is stated in the report but it is
   an easy thing to misread across sections.
3. **Corpus labels in `code/LABELS.tsv` are hand-assigned by me** from papers and
   READMEs, including the `architecture` column that §5f turns on. Several are
   judgement calls (is Seed-Prover "whole-proof" or "agentic"? I coded it
   `whole_proof_agentic`). 18 of 49 corpora are unlabeled.
4. **Model labels in the lean-eval data are self-reported free text** by
   submitters; several are human-in-the-loop or multi-model ensembles. 560 of
   1,042 records are private, so the public set is a biased sample.
5. **Compilation attrition.** AI corpora span Lean toolchains v4.10–v4.32; where
   I re-elaborated against current Mathlib, roughly a third of files failed. That
   selects toward simpler proofs. Matched designs mitigate; §5e does not.
6. **Small blocks.** §5f rests on a 7×7 complete block. §5b has only 20
   human-authored edges in the sampled ETP set.
7. **`study4b_vampire.py`'s headline** ("every true implication is one-shot
   ATP-provable") comes from cross-tabulating the Vampire dump against the
   outcomes matrix. The run was interrupted before writing its full JSON; the
   number in the report comes from the log. **Re-run it to confirm.**
8. **The ΔL₁ firewall statistic uses my normalization, not the paper's** — values
   are not comparable to the published +9…+21. Only within-pipeline comparisons
   are meaningful.
9. **Belief-model rule.** The original C code (`CMU_ISING_bi/ising.c` in the
   archive) uses Metropolis with weight `exp(-β·d)`; the published text describes
   Glauber `exp(-2βD)/(1+exp(-2βD))`. I implemented the published text. Both
   satisfy detailed balance for the same stationary distribution, and my f₂
   reproduces (0.994 vs 0.991) — but a reviewer may want to run both.

## 5. How to re-run

For the current paper, from this checkout with the local ignored data caches:

```bash
PY=.venv/bin/python
$PY code/paired_horizon.py
$PY code/extract_binder_use.py --pairs results/paired_term_structure/term0.csv --jobs 8
$PY code/analyze_binder_use.py
$PY code/horizon_figures.py
$PY code/test_horizon_report.py

c++ -std=c++17 $(pkg-config --cflags llama) code/token_surprisal.cpp \
  -o tmp/token_surprisal $(pkg-config --libs llama)
$PY code/prepare_surprisal.py
tmp/token_surprisal models/Goedel-Prover-V2-8B.Q4_K_M.gguf \
  tmp/horizon/surprisal_manifest.tsv results/horizon/token_surprisal.tsv 8192 256
for w in 4 8 16 32; do
  $PY code/analyze_surprisal.py --window "$w" --tag "w$w"
done
$PY code/collect_surprisal_sensitivity.py
```

The model URL, hash, inference version, prompt mode, and hardware are in
`results/horizon/surprisal_provenance.json`. The raw 9.1 MB token table is
ignored but deterministically regenerable from the local model and manifest.

For the older network studies on the private mirror:

```bash
ssh akdeniz.lan.cmu.edu
cd ~/ai_math_ept
export PATH=$HOME/.elan/bin:$PATH
PY=venv/bin/python

$PY code/test_toolkit.py                    # sanity suite, ~1 min
$PY code/repro_xmin.py                      # Table 1 reproduction
$PY code/repro_validate.py                  # null models (slow: ~2h)
$PY code/census.py --roots census census/hf census/human corpora \
      --each-subdir --out results/census_all --jobs 6
$PY code/paired_numina.py                   # the key paired result
$PY code/matched_hf.py                      # matched-theorem, large n
bash code/run_overnight.sh                  # studies 6-9 in sequence
```

Everything is deterministic given the same inputs (fixed seeds throughout)
**except** anything reading live GitHub/HuggingFace, and the belief simulations,
which are Monte Carlo — reported values are means over 8–30 runs.

## 6. What a reviewer cannot check without akdeniz

The corpora themselves. If Codex is running locally, it can review all code, all
derived numbers, the report, and the git history — but it cannot re-derive
`results/*` without the data. If that matters, the cheapest fix is to sync
`results/` plus a sample of `networks/` (a few hundred MB) rather than the full
83 GB.
