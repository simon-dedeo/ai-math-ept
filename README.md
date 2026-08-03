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
output file that produced it, lists the claims withdrawn during the work and why, and names
the places the work is weakest. [`results/DATA_INVENTORY.md`](results/DATA_INVENTORY.md) enumerates
the bulk reproducibility data. These data are excluded from Git, but Simon retains complete local
and private cluster mirrors; the versioned derived evidence is sufficient for the public audits.

## What was found, in one paragraph

A formal proof has at least three products: a certificate for the kernel,
working memory for the current episode, and an interface for later proofs and
readers. In **3,630 validated human/AI pairs of the identical Lean statement**,
the AI track creates more named local claims, but those claims receive fewer
explicit references, are less often adopted at all, use much more
generic names, and less often state a callable family. Thus the abundance of `have` statements
previously offered as evidence of human-like clarity measures decomposition, not consolidation.
The denominator matters: per 100 proof-body tokens AI still supplies more claims referenced at least
once (1.96 versus 1.52), while humans supply more claims referenced repeatedly (0.470 versus 0.318), carrying
non-placeholder names (0.805 versus 0.348), or stating a family (0.103 versus 0.052).
The absolute lexical-reference curve therefore crosses between one and two later mentions; the
human advantage at two or more holds in all 12 source groups and survives the 834-pair length match.
But after mentions within one downstream construction are collapsed, absolute multi-consumer-site
supply is unresolved; the crossover is textual addressability, not a count of cognitive retrieval episodes.
The resulting local-claim construction DAG is nevertheless denser and more branching for humans
in 206 exact-equal-node pairs, while maximum chain length is unresolved rather than more serial for AI.
The family comparison collapses
equivalent binder and explicit-`forall` spellings: rates are 5.24% versus 1.68%, and within
identical-theorem pairs family claims occur only on the human side 310 times versus only on the AI
side 102 times. Within proofs containing both family and instance claims, family claims are
substantially more likely to be adopted and multiply referenced in both tracks. This persists after
matching each family to a nearby instance claim within the same proof, so it is not merely an
earlier-position advantage; conditional source multi-reference uplift is actually larger for AI in
the directly comparable subset. The gap is therefore in how often that interface form is selected,
not whether AI can use it. In the complete
production-term census, AI source boundaries more often disappear (21.8% versus 9.8%) or are
duplicated, while human boundaries more often map one-to-one (58.0% versus 44.0%). Aggregate
multi-use remains nearly equal (32.2% versus 34.2%), but conditional on surviving at all it is
higher for AI (43.7% versus 35.7% human). Within proofs containing both aligned family
and instance binders, however, families are preferentially retained on both tracks, while their
multi-use uplift is robust only for humans after within-proof position matching; the direct
between-track interaction is unresolved. The divergence is
therefore not “humans reuse, machines do not.” It lies in whether source
structure is transient search state or an addressable interface. This is the
**consolidation–composition split**: large differences in deliberate source retrieval, but weak or
reversed differences in compiler-produced term fan-out. We call its
governing variable the **amortization horizon**: how far into future reasoning a
constructor expects an abstraction to repay its cost. The hypothesis predicts
that AI given refactoring and downstream-library objectives can cross the
observed divide. A rate–distortion formulation makes the cognitive claim precise: an interface
compresses a proof episode against the future work or loss of correspondence experienced by a
particular consumer. A second principle constrains the measurement itself: a functional proof statistic
must be invariant under transformations that preserve its stated consumer's response. Lean's
version-dependent `have` encoding and an exponential zeta-reduction example show why raw proof
graphs fail that test for kernel-level meaning. In one recurrence theorem, a human proof replaces
unfolding with a reusable closed form; the AI's one-line `norm_num` proof denotes a shared term whose
fully expanded tree count has 535 digits. This is a representation fact, not a cognitive score, but
it makes the difference between naming an invariant and delegating the present computation concrete.

One measurement correction is especially important. Lean's parser now identifies both the end of
each complete `have` construction and the tail of its enclosing tactic scope before reference
counting. This prevents an older shadowed name in `have h : P := f h` from being credited to the new
`h`, and excludes same-spelled tokens in sibling branches. Exact ranges cover 39,646 of 40,626
candidate claims, and the result is unchanged in the 3,511 theorem pairs with complete two-sided
alignment: scoped uses are 1.35 human versus 0.82 AI, while zero uptake is 22.2% versus 36.9%.
Conditional on adoption and on a later claim boundary being available, human and AI claims are
equally likely to cross at least one such boundary (83.6% versus 85.0%). Pooled human claims remain
referenced across more source tokens (35.0 versus 23.9, measured after construction), while the
fraction of available boundaries crossed is statistically unresolved (63.7% versus 62.0%). Both
duration measures are unresolved under length matching. “Horizon” is therefore decomposed
into adoption and duration: the robust difference is selection for uptake, not an AI inability to
carry an adopted claim forward.

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
| `paired_horizon.py`, `ExtractHaveRanges.lean` | 3,630-pair exact-statement audit and Lean-parser-bounded source analysis: local-claim density, lexical uptake, conservative consumer sites, visible reach, naming, generalized-family syntax, and automation sensitivities |
| `ExtractBinderUseMemoLegacy.lean.tmpl`, `ExtractBinderUseLegacy.lean.tmpl`, `ExtractBinderUseLinear.lean.tmpl`, `extract_binder_use.py`, `analyze_binder_use.py` | semantic decoding of production Lean 4.15 `letFun` and current Lean `letE` encodings, stack-safe memoized binder use, source-to-term alignment, and source/term transitions |
| `binder_memo_audit.py` | equivalence audit of the memoized production traversal against the legacy recursive traversal, including the largest legacy-success terms and every source group |
| `results/horizon/binder_root_tree_extremes.csv` | ranked, exact arbitrary-precision tree-occurrence counts; these diagnose representation expansion and are not treated as intrinsic proof sizes |
| `compare_binder_toolchains.py`, `test_binder_toolchain_shift.py`, `test_legacy_binder.py`, `test_certificate_representation.py` | cross-version retention audit and regressions for nested scope, equivalent family spellings, and exponential representation shifts |
| `test_binder_linear.py` | exact regression of both one-pass traversals against the reference under nested scope, plus a 12,000-deep stack-safety test |
| `prepare_surprisal.py`, `token_surprisal.cpp`, `ngram_surprisal.py`, `analyze_surprisal.py` | Goedel-Prover and leave-one-source-out token information at claim boundaries |
| `name_type_retrieval.py` | paired within-proof name-to-type retrieval assay; its chance-normalized null prevents semantic over-reading of name diversity |
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
