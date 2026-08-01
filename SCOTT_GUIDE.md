# A guide for Scott

This repository extends the research program of Scott Viteri and Simon DeDeo,
[*Epistemic phase transitions in mathematical proofs*](https://doi.org/10.1016/j.cognition.2022.105120),
from classical Coq proofs to contemporary human and machine Lean proofs. The main
new thesis is **epistemic decoupling**: human and machine proofs of the same theorem
can support nearly identical theorem-level confidence while organizing the proof's
interior very differently.

## The shortest route through the project

1. Read the standalone paper,
   [*Epistemic Decoupling in Human and Machine Proofs*](output/pdf/epistemic_decoupling_human_ai_proofs.pdf).
2. Inspect the paper's [LaTeX source](report/standalone/main.tex) and its
   machine-readable [claim audit](results/paper_claim_audit.json).
3. For the same-theorem results, compare the
   [source-level summary](results/final_synthesis/paired_source_summary.json),
   [elaborated-term summary](results/final_synthesis/paired_term_summary.json), and
   [belief-model sensitivity run](results/final_synthesis/paired_belief_term0_r32.json).
4. For the historical bridge, inspect the
   [fixed-tail Coq--Lean summary](results/coq_lean_confirmation_xmin10/summary.json)
   and [method note](results/coq_lean_confirmation_xmin10/README.md).
5. [`REVIEW.md`](REVIEW.md) is the longer claim-to-script-to-output map, including
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

The strongest new design holds the theorem fixed and compares a validated human
proof with a validated machine proof.

- Across 2,583 source-level pairs, proof length is similar, while machine proofs use
  fewer distinct library results and more local `have` steps.
- For 312 clean pairs successfully elaborated into both human and machine proof-term
  DAGs, the machine proofs have larger interiors and greater duplication, but the
  Viteri--DeDeo belief dynamics assign nearly the same theorem confidence.
- This separation between interior organization and theorem-level confidence is the
  empirical basis of **epistemic decoupling**.

The paper treats this as a structural result about the present proof corpora, not as
a universal cognitive difference between humans and AI systems.

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
code. These residual details do not alter the fixed-tail human--AI comparisons or
the epistemic-decoupling result.
