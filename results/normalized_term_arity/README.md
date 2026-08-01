# Common-schema local arity

This directory contains the comparable Coq--Lean test of the Poisson local-arity
claim. It was added after tracing the native degree-two spike to the extractors:
Lean `Expr.app` is binary, while archived CoqAST `App` is variadic and includes
binder-name fields.

The normalization uses only the root proof value, not its theorem type or
recursively expanded library declarations. Applications are binary in both
systems; binder names are removed while domains and bodies are retained; lets
retain type, value, and body. The primary positive sample is the shared
`App`/`Lam`/`Pi`/`Let` core. A sensitivity analysis retains every normalized
constructor.

Main result: median degree-two shares are 0.9903 for 45 eligible Coq roots and
0.9976 for 29 eligible human Lean roots. They are 0.9981 and 0.9977 in 312
same-theorem human/AI pairs. Every eligible graph rejects zero-truncated Poisson
and zero-inflated Poisson after within-corpus BH correction; CMP and hurdle CMP
win all AIC comparisons. A special zero mass cannot repair a positive component
whose shape is largely fixed by the binary grammar.

Files:

- `summary.json`: schema, exclusions, native parser diagnostics, and corpus results.
- `per_network.csv`: fitted models and goodness-of-fit tests.
- `constructor_counts.csv`: positive nodes by normalized constructor.
- `calibration.csv`: proof-weighted values used in the appendix figure.
- `run.log`: complete deterministic run output.

Reproduce with:

```bash
.venv/bin/python code/test_normalized_term_arity.py
.venv/bin/python code/normalized_term_arity.py
```

This is a syntactic common denominator, not a proof-meaning equivalence: Coq and
Lean elaboration still differ, and moving from expanded graphs to root values
changes the scientific boundary.
