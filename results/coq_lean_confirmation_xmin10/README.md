# Fixed-tail distribution comparison

All fits use positive integer degree data and hold `xmin=10` fixed:

```python
fit = powerlaw.Fit(degrees, discrete=True, xmin=10, verbose=False)
R, p = fit.distribution_compare("power_law", "lognormal", normalized_ratio=True)
```

Classification uses `p < 0.05`: positive `R` favors the power law, negative `R` favors the
alternative, and larger `p` is inconclusive. A network is estimable only if the tail contains at
least ten observations and at least two distinct values.

| Collection | Estimable | Power law favored | Lognormal favored | Inconclusive |
|---|---:|---:|---:|---:|
| Recovered Coq out-degree | 45/49 | 0 | 2 | 43 |
| Human Lean term out-degree | 33/33 | 0 | 0 | 33 |

As a calibration, power law versus exponential on the same fixed tails favors the power law in
43/45 Coq networks and 33/33 Lean networks. The result therefore supports a heavy reuse tail above
degree 10, while showing that these samples generally do not distinguish a power law from a
lognormal.

Machine-readable results are in `summary.json`; network-level likelihood ratios and p-values are in
`coq_model_comparisons_xmin10.csv` and `lean_model_comparisons_xmin10.csv`.
