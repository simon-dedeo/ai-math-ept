# Proofs for now and proofs for later

Research on the construction horizon of human- and AI-provenance Lean proofs,
building on Viteri & DeDeo, *Epistemic phase transitions in mathematical
proofs* (Cognition 225:105120, 2022).

**Start here:** [*Proofs for Now and Proofs for Later: The Amortization Horizon
of Human and Artificial Reasoning in Lean*](output/pdf/proofs_for_now_and_proofs_for_later.pdf),
with LaTeX source and figures in [`report/horizon/`](report/horizon/).

The earlier network replication and synthesis remain in
[`report/REPORT.md`](report/REPORT.md), and the preceding standalone paper remains
in [`report/standalone/`](report/standalone/). They are now background rather
than the main claim.

**For Scott Viteri and other readers of the 2022 work:**
[`SCOTT_GUIDE.md`](SCOTT_GUIDE.md) gives a short route through the new results,
documents the exact connection to
[`scottviteri/ManipulateProofTrees`](https://github.com/scottviteri/ManipulateProofTrees),
and links the recovered provenance of the original power-law convention.

**Reviewing this work?** [`REVIEW.md`](REVIEW.md) maps every claim in the report to the script and
output file that produced it, lists the seven claims withdrawn during the work and why, and names
the places the work is weakest. [`results/DATA_INVENTORY.md`](results/DATA_INVENTORY.md) enumerates
the bulk reproducibility data. These data are excluded from Git, but Simon retains complete local
and private cluster mirrors; the versioned derived evidence is sufficient for the public audits.

## What was found, in one paragraph

A formal proof has at least three products: a certificate for the kernel,
working memory for the current episode, and an interface for later proofs and
readers. In **3,630 validated human/AI pairs of the identical Lean statement**,
the AI track creates more named local claims, but those claims receive fewer
explicit references, remain visibly live for less of the proof, use much more
generic names, and more often become unused binders in the final elaborated term. The
kernel-level result is equally important: among claims that survive,
multi-use binders occur at essentially the same rate. The divergence is
therefore not “humans reuse, machines do not.” It lies in whether source
structure is transient search state or an addressable interface. We call its
governing variable the **amortization horizon**: how far into future reasoning a
constructor expects an abstraction to repay its cost. The hypothesis predicts
that AI given refactoring and downstream-library objectives can cross the
observed divide.

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
| `paired_horizon.py` | 3,630-pair exact-statement audit and source analysis: local-claim density, uptake, visible reach, naming, and tactic-stratum sensitivity |
| `ExtractBinderUseIterative.lean.tmpl`, `extract_binder_use.py`, `analyze_binder_use.py` | stack-safe one-pass elaborated-binder use, source-to-term alignment, and source/term transition analysis; the recursive linear and quadratic templates are retained as references |
| `test_binder_linear.py` | exact regression of both one-pass traversals against the reference under nested scope, plus a 12,000-deep stack-safety test |
| `prepare_surprisal.py`, `token_surprisal.cpp`, `ngram_surprisal.py`, `analyze_surprisal.py` | Goedel-Prover and leave-one-source-out token information at claim boundaries |
| `horizon_figures.py` | figures for the current paper |
| `ExtractNetwork.lean` | Lean 4 metaprogram: proof term → dependency DAG (`term0` scope-aware root term, `term` level-expanded, `decl` declaration-level). The Lean analogue of the 2022 CoqAST/ManipulateProofTrees pipeline. |
| `extract_corpus.py` | batch-elaborates a corpus of standalone `.lean` proofs (handles syntax drift, namespaces, per-corpus toolchains) |
| `proofnet.py` | network construction + structural statistics (degree distributions, power-law fits, modularity, DAG depth) |
| `belief.py` | the asymmetric-Ising belief model (numba): certainty curves, f₂, contour grids, ΔL₁ firewalls |
| `census.py` | two-tier structural census; Tier 1 needs no compilation and scales to any repo |
| `paired_numina.py` | **the key experiment**: human vs AI proofs of identical statements |
| `matched_leaneval.py`, `matched_hf.py` | matched-theorem experiments across prover systems |
| `within_system.py` | within-system noise floor (the control that calibrates the above) |
| `repro_xmin.py`, `implied_xmin.py`, `xmin_robust.py`, `repro_alpha.py` | reproduction of Table 1 and the x_min-convention analysis |
| `repro_validate.py` | power-law vs alternative distributions; random-DAG null models |
| `poisson_indegree_appendix.py` | direct Poisson, ZIP, hurdle, NB, and CMP tests of local arity in Coq and human/AI Lean |
| `normalized_term_arity.py` | common-schema Coq/Lean local-arity test: binary applications, binder-name removal, root proof values |
| `normalized_outdegree_sensitivity.py` | fixed-x_min reuse-tail sensitivity under that same normalized root-proof boundary |
| `convert_coq_dags.py`, `convert_hand_networks.py` | import the 2022 paper's own machine and hand-coded networks |
| `study4_etp.py`, `study4b_vampire.py`, `etp_belief.py` | Equational Theories Project: skeleton, percolation, ATP difficulty census |
| `study5_mathlib.py` | belief dynamics on all of Mathlib (308k declarations, 8.4M edges) |
| `study6`–`study9` | ETP provenance, automation dose–response, source-level cross-project graphs, matched pairs |
| `run_overnight.sh`, `phase2.sh` | unattended job chain |
| `test_toolkit.py` | sanity suite: chains show no EPT, tinkering DAGs do, abductive paradox reproduces |

## Reproducing the 2022 paper

`repro_xmin.py` shows Table 1 reproduces to within 0.010 on 40 of 44 estimable networks using a
**fixed** tail cutoff x_min = 10. Archived production code confirms this was an explicit fitting
cutoff, although four sub-1,000-node rows reproduce at x_min = 5; see the
[historical provenance note](results/HISTORICAL_POWERLAW_PROVENANCE.md). It does *not* reproduce
under Clauset–Shalizi–Newman's KS-selected x_min, which
chooses x_min ≈ 1 on these degree sequences because the distribution is power-law-like all the way
down. Any α quoted for a proof network should carry its x_min: the two conventions differ by ≈0.2
and correlate at zero.

`repro_validate.py` then checks the structural claim against null models: the out-degree beats an
exponential in 47 of 47 networks and is significantly heavier-tailed than size- and density-matched
random DAGs (α 2.27 vs 2.75), so heavy-tailed reuse is a fact about proofs rather than an artifact
of the fit. It is *not* separable from a lognormal, which is the standard caveat for power-law
claims and applies to the published values equally.

`poisson_indegree_appendix.py` reproduces the complementary in-degree claim in each corpus's native
graph format. It rejects Poisson in all 49 recovered Coq networks; giving leaves a special zero term
does not rescue the fit. Its original direct Coq--Lean contrast is withdrawn, however, because
CoqAST applications are variadic while Lean applications are binary. The apples-to-apples
`normalized_term_arity.py` analysis makes applications binary on both sides, removes Coq binder-name
children, and uses root proof values. The degree-two share then becomes 0.9903 in Coq and 0.9976 in
human Lean. Every eligible graph still rejects both zero-truncated and zero-inflated Poisson, with
hurdle CMP preferred. The conclusion is about grammar-constrained local arity, not a cognitive
signature.

The same normalization also qualifies out-degree. At fixed x_min = 10 the median exponent remains
near two (2.340 in Coq, 2.489 in human Lean), but only 23/48 and 12/33 root proofs are estimable and
most power-law-versus-exponential tests are inconclusive. Strong heavy-tail evidence therefore
belongs to the expanded-network scale; it is not invariant to moving the boundary to one root proof.
The paired human--AI exponent also reverses its tiny sign: `term0` gives 2.531 vs 2.527, while
normalized proof values give 2.355 vs 2.381. There is no representation-robust authorship direction.
