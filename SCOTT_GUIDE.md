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
table by exact node count. With a fixed discrete tail cutoff near
\(x_{\min}=10\), 40 of those 47 fitted exponents are within 0.010 of the published
values. Reuse is unambiguously heavy relative to an exponential null. The stronger
claim that it is a *pure* power law is not identified: at fixed \(x_{\min}=10\),
a power law beats a lognormal in none of 45 estimable Coq networks, a lognormal wins
in two, and 43 are unresolved. All 33 human Lean networks are unresolved between
those two heavy-tailed families.

The main discrepancy in reported exponents is therefore largely a cutoff issue.
Automatic Clauset--Shalizi--Newman selection often chooses \(x_{\min}\) near 1 for
these networks; the published values are closely recovered near 10. The original
repository imports `powerlaw`, but its checked-in notebook does not contain the
per-theorem fitting code that generated the published table. If Scott remembers the
exact cutoff rule or has the missing analysis cell/script, that would resolve the
remaining provenance question cleanly.

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

## Questions where Scott's memory would be especially valuable

1. Was the published out-degree exponent fitted with an explicit cutoff near 10, or
   by a plotting/range convention outside the checked-in Org notebook?
2. Was “out-degree” in the paper defined in premise-to-dependent orientation, despite
   the constructor-to-children representation used by `ManipulateProofTrees`?
3. Does an uncommitted script, notebook cell, or output table survive that records the
   exact `powerlaw.Fit` call used for the published exponents?

Answers to those questions would sharpen the historical appendix, but they do not
alter the fixed-tail human--AI comparisons or the epistemic-decoupling result.
