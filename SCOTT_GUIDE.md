# A guide for Scott

This repository extends the research program of Scott Viteri and Simon DeDeo,
[*Epistemic phase transitions in mathematical proofs*](https://doi.org/10.1016/j.cognition.2022.105120),
from classical Coq proofs to contemporary human- and AI-provenance Lean artifacts. The
main thesis is now the **amortization horizon**: proof construction differs according
to which future consumer an abstraction is expected to serve. A second, methodological
claim is the **consumer-invariance principle**: a graph statistic can describe a
consumer's function only if it survives transformations that preserve that consumer's
response. The older epistemic-decoupling analysis is retained as background, not as
the central result.

## The shortest route through the project

1. Read [*Proofs for Now and Proofs for Later*](output/pdf/proofs_for_now_and_proofs_for_later.pdf).
2. Inspect its [LaTeX source](report/horizon/main.tex), the
   [3,630-pair source summary](results/horizon/source_summary.json), and the
   [semantic binder summary](results/horizon/binder_summary.json).
3. For the representation checks, see `code/test_binder_toolchain_shift.py`,
   `code/test_certificate_representation.py`, and
   [the cross-toolchain summary](results/horizon/binder_toolchain_summary.json).
4. For the model-relative information assay, inspect
   [the eight-token summary](results/horizon/surprisal_summary_w8.json) and
   [leave-one-source-out control](results/horizon/surprisal_summary_loso_bigram_w8.json).
5. For the historical bridge, inspect the
   [fixed-tail Coq--Lean summary](results/coq_lean_confirmation_xmin10/summary.json)
   and [method note](results/coq_lean_confirmation_xmin10/README.md).
6. [`REVIEW.md`](REVIEW.md) is the longer claim-to-script-to-output map, including
   negative results and withdrawn claims.

## Direct connection to `ManipulateProofTrees`

The historical analysis does use
[`scottviteri/ManipulateProofTrees`](https://github.com/scottviteri/ManipulateProofTrees)
directly. The recovered local checkout is byte-identical, for the central Org source
and README, to upstream commit
[`7aeaf156`](https://github.com/scottviteri/ManipulateProofTrees/commit/7aeaf156031d80726c7a8cf9b6fce0b4eefd3fe7).
It contains 49 theorem directories and 234 saved depth-specific DAGs.

The bridge is:

```text
Coq proof object
  -> CoqAST exported tree
  -> ManipulateProofTrees structural-sharing DAG
  -> code/convert_coq_dags.py
  -> premise-to-dependent edge list
  -> the same statistics used for Lean proof terms
```

[`code/convert_coq_dags.py`](code/convert_coq_dags.py) converts all 49 saved Coq
networks. [`code/ExtractNetwork.lean`](code/ExtractNetwork.lean) is the Lean analogue:
it elaborates a proof term and deduplicates repeated subterms into a DAG.

There is one terminology trap worth making explicit. A saved `ProofDAGs` dictionary
maps each constructor node to its children. In `ManipulateProofTrees.org`,
`getNodeOutdegrees` therefore measures expression arity, while `getNodeIndegrees`
measures how often a subexpression is reused. The current converter reverses each
stored parent-to-child link into a premise-to-dependent edge. Consequently,
NetworkX **out-degree** in this repository is Scott's stored-DAG **in-degree**: both
measure reuse. This orientation change is intentional, but it can make two analyses
look contradictory if one compares their degree labels rather than their edges.

## What survives from the 2022 analysis

The 49 recovered Coq networks include 47 networks that match rows in the published
table by exact node count. With a fixed discrete tail cutoff
\(x_{\min}=10\), 40 of the 44 networks that meet the modern audit's minimum-tail
rule are within 0.010 of the published values (43 within 0.020). In these archived
expanded graphs, reuse is unambiguously heavy relative to an exponential null. The stronger
claim that it is a *pure* power law is not identified: at fixed \(x_{\min}=10\),
a power law beats a lognormal in none of 45 estimable Coq networks, a lognormal wins
in two, and 43 are unresolved. All 33 human Lean networks are unresolved between
those two heavy-tailed families.

There is a second representation qualification. Archived CoqAST applications are
variadic and include binder-name children; Lean applications are binary and binder
names are metadata. Native in-degree is therefore not comparable across the two.
After normalizing both to binary root proof values, Coq and Lean positive local arity
is almost deterministic at two (median shares 0.9903 and 0.9976), and every eligible
network rejects both Poisson and a zero-inflated Poisson. The same root-boundary check
leaves out-degree exponents near two but greatly weakens model discrimination: most
power-law-versus-exponential comparisons become inconclusive. See
[`results/normalized_term_arity/`](results/normalized_term_arity/) and
[`results/normalized_outdegree/`](results/normalized_outdegree/).

The old archive resolves the main provenance question. Its production `pl.py`
hard-codes `cutf=10` and calls
`powerlaw.Fit(..., discrete=True, xmin=cutf)`; `convert_final_check.rb` feeds it
the reuse degrees used in the table. Saved figure data record `xmin=10` and recover
the published Four Color and Gödel exponents exactly after rounding. This was an
explicit fitting cutoff, not a plotting convention.

There is one qualification. The four smallest table entries jointly reproduce in
both exponent and standard error at `xmin=5`, not 10, suggesting a small-network
exception in an earlier or uncommitted fitter. The archive search did not recover
that code path. The evidence, fingerprints, and exact refits are recorded in the
[historical provenance note](results/HISTORICAL_POWERLAW_PROVENANCE.md).

Relevant files:

- [`code/repro_xmin.py`](code/repro_xmin.py): fixed-cutoff reconstruction against
  the published table.
- [`results/repro_xmin_best.csv`](results/repro_xmin_best.csv): per-theorem match.
- [`code/coq_lean_confirmation.py`](code/coq_lean_confirmation.py): common modern
  fitting pipeline for recovered Coq and human Lean networks.
- [`results/coq_lean_confirmation_xmin10/`](results/coq_lean_confirmation_xmin10/):
  fixed-\(x_{\min}=10\) model comparisons.

## The new same-theorem comparison

The strongest new design holds the exact Lean statement fixed in 3,630 validated
pairs. AI claims are more numerous but receive fewer explicit references, more often
have zero visible uptake, and draw from a much
smaller effective name vocabulary. After collapsing equivalent binder and
explicit-`forall` syntax, local families occur in 5.60% of human claims and 1.91%
of AI claims; same-theorem presence is human-only in 320 pairs and AI-only in 108.
Within proofs containing both family and instance claims, family claims are more likely to be
adopted and multiply referenced in both tracks. The association survives one-to-one matching to
nearby instance claims within the same proof, ruling out the basic explanation that families merely
occur earlier. The family statistic therefore marks a functional interface form, while its
provenance gap lies in selection frequency.

The temporal result has been opportunity-normalized. Conditional on adoption and on a later claim
being available, both tracks cross at least one boundary about 75% of the time; the raw boundary
count is inflated by the AI track's denser decomposition. Pooled human claims have longer token
exposure and cross a larger fraction of available later boundaries, but these conditional-duration
effects do not survive length or equal-claim-count controls. The stable difference is the extensive
margin—whether an abstraction is taken up—not its lifetime once adopted.

Elaboration narrows the conclusion. Production Lean 4.15 and current Lean encode
the same source `have` with different core node kinds, so the analysis decodes the
semantic construct before aligning it. Across all 7,260 production tasks, AI boundaries
are more often absent from the final term (21.7% versus 9.7%) or multiply represented;
human boundaries more often map one-to-one (58.2% versus 44.2%). Yet aggregate multi-use
is nearly equal (32.1% versus 34.1%); conditional on retention, AI multi-use is higher (43.6%
versus 35.6% human). Within proof sides containing both aligned forms, family
binders are less likely than instance binders to disappear in both tracks. Their multi-use uplift
remains robust for humans (17.8 points) but unresolved for AI (-2.6 points) after matching nearby
binders one-to-one within the same proof. The direct between-track interaction is itself unresolved,
so this does not establish a provenance difference in family-specific term composition. It does
show that the family classifier
predicts compiled retention, while family-specific repeated composition supplies a sharper
provenance asymmetry than aggregate reuse. A stack-safe dynamic program agrees exactly with the
legacy traversal on every one of its 7,186 successful tasks and recovers its 74 timeouts. A typed
zeta-reduction regression also changes a 99-node shared term into a 65,533-node tree
without changing its type. The result is about visible interface allocation under
different workflows, not a universal biological difference or a representation-free
authorship signature.

The sharpest individual example asks for one late value of a simple recurrence. The human script
proves a reusable closed form by induction; the AI script invokes `norm_num [f]`. Their fully expanded
term-tree counts are 278,395 and a 535-digit number, respectively, although Lean shares the AI term
and does not materialize that tree. This is the formula-versus-circuit distinction inside a real
paired proof: it exposes an invariant-versus-unfolding choice without equating tree size with effort.

Across source adoption, family construction, and elaborated binder use, the common pattern is a
**consolidation–composition split**: the large differences concern which intermediate results are
stabilized as visible interfaces, while source duration and kernel compositional use converge or
reverse. This localizes the current divergence to consolidation policy rather than deductive power.

## Re-running the public checks

With Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python code/audit_standalone_paper.py
.venv/bin/python code/test_toolkit.py
```

These commands check the versioned evidence, manuscript macros, archive hashes, and
network-model sanity cases. The full extracted Lean networks and downloaded corpora
are too large for ordinary Git. Their derived tables and ORCHARD provenance bundles
are versioned here; Simon also retains private local and cluster mirrors. The
original Coq inputs can be recovered independently by cloning
`scottviteri/ManipulateProofTrees` at commit `7aeaf156`.

## Questions where Scott's memory would still be valuable

1. Was there a small-network rule that changed `xmin` from 10 to 5? That change
   recovers all four sub-1,000-node entries in both alpha and standard error.
2. Which version of the Python `powerlaw` package was installed for the final run?
3. Does an earlier or uncommitted table script explain the remaining 0.012 difference
   for Triangle Inequality?

The cutoff and edge-orientation questions themselves are now resolved by archived
code. These residual details concern the historical network reconstruction, not the
current amortization-horizon analysis.
