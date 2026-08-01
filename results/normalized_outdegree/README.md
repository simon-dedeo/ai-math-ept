# Normalized out-degree sensitivity

This directory asks whether the reuse-tail result survives the same normalized
root-proof boundary used for local arity. Applications are binary, Coq binder
names are removed, and no library declaration is recursively expanded. Fits use
the predeclared tail cutoff `xmin=10` and compare power law with exponential,
lognormal, and stretched-exponential alternatives.

The rough exponent survives: among estimable shared-core roots, median alpha is
2.340 in Coq and 2.489 in human Lean. Model discrimination does not. Only 23/48
Coq and 12/33 Lean roots are estimable; power law beats exponential in 3/23 and
1/12, and most tests are inconclusive. In 251 same-theorem pairs where both sides
are estimable, medians are 2.355 human and 2.381 AI.

This does not invalidate the archived expanded-graph result. It localizes it:
strong evidence for a broad reuse tail is a property of that expanded network
boundary, not a representation-invariant law of a proof's root value.

Files:

- `summary.json`: corpus and paired summaries.
- `per_network.csv`: fixed-tail fits and likelihood-ratio comparisons.
- `run.log`: complete rerun output.

Reproduce with:

```bash
.venv/bin/python code/normalized_outdegree_sensitivity.py
```
