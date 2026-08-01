# Local-arity distribution checks

This directory contains the native-format reanalysis of the Poisson in-degree claim in
Viteri and DeDeo (2022). Under the repository's premise-to-dependent edge
orientation, in-degree is the number of distinct immediate premises of a term:
its local arity.

The archived 2022 histogram removed degree-zero leaves. For exact historical
comparability, `per_network.csv` therefore fits the positive degrees separately
in every graph using zero-truncated Poisson, geometric, negative-binomial, and
Conway--Maxwell--Poisson (CMP) distributions. Absolute Poisson fit is tested by
a discrete KS statistic with 199 parametric-bootstrap samples and parameter
refitting. P-values are Benjamini--Hochberg corrected within each corpus.

The analysis also restores degree zero. It compares ordinary Poisson,
zero-inflated Poisson (ZIP), and hurdle versions of the positive-count models.
ZIP can add an extra point mass at zero, whereas a hurdle model fits the zero
probability freely and then models positive degree. The ZIP fit is additionally
given an absolute parametric-bootstrap KS test.

Native-format result: Poisson is rejected in every one of the 49 Coq, 33 expanded human
Lean, 312 matched-human Lean, and 312 matched-AI Lean networks. ZIP also fails:
Coq usually has excess zeros, but its positive-degree shape is non-Poisson; Lean
usually has fewer zeros than ZIP permits, forcing the inflation weight to zero.
Hurdle CMP wins all Lean AIC comparisons. Coq splits between hurdle CMP (35)
and hurdle negative binomial (14).

Important comparability warning: these rows do not support a direct Coq--Lean
arity contrast. Archived CoqAST `App` nodes are variadic and retain binder-name
children, whereas Lean `Expr.app` is binary and binder names are metadata. This
is why native Lean degree is almost always two. The manuscript now uses
`../normalized_term_arity/` for cross-language inference; this directory remains
the exact historical-format replication and a diagnostic of the parser effect.

Files:

- `summary.json`: corpus and matched-pair summaries.
- `per_network.csv`: all fitted parameters, GOF tests, and AIC values.
- `paired_comparison.csv`: theorem-matched human/AI measurements.
- `calibration.csv`: proof-weighted values used in the appendix figure.

Reproduce from the repository root with:

```bash
.venv/bin/python code/test_poisson_indegree.py
.venv/bin/python code/poisson_indegree_appendix.py
.venv/bin/python code/normalized_term_arity.py
```
