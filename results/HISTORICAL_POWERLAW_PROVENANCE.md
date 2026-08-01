# Historical provenance of the 2022 power-law fits

This note records what survives in Simon DeDeo's older research archive at
`/Users/simon/Desktop/OLDER_RESEARCH_ARCHIVE/SCOTT`. The archive resolves the
main cutoff question: the reported large-network fits came from an explicit
fitting cutoff, not merely from the range shown in a plot. It also reveals a
small-network exception that the surviving production script does not explain.

## Surviving production path

The operative lines of `pl.py` are:

```python
cutf=10
fit=powerlaw.Fit(data[0][1:], discrete=True,
                 xmax=data[0][0], xmin=cutf)
```

`convert_final_check.rb` writes the node count followed by the reuse-degree
sample to `TEMP/data.dat`, invokes `./pl.py`, and prints `alpha` and `sigma` for
the manuscript table. Here reuse is `rev[i].length`: `stats.rb` constructs
`rev[child]` as the list of parent expressions that use that child. This is the
paper's “out-degree” (number of later nodes that employ a result), despite the
opposite orientation of the stored constructor-to-children dictionaries.

The depth convention is also explicit. `exportDAGs` in
`ManipulateProofTrees.org` exports increasing depths only while the preceding
network has fewer than 10,000 nodes. The maximum saved depth is therefore the
first expansion above 10,000 nodes, or the deepest available network if the
proof never crosses that threshold. This reconciles the manuscript caption with
the table script's use of the maximum saved depth.

Two saved figure-data records independently preserve the fitted parameters:

| network | nodes | stored `xmin` | stored alpha | published alpha |
|---|---:|---:|---:|---:|
| Four Color Theorem | 12,407 | 10 | 1.9665734753 | 1.97 |
| Gödel's First Incompleteness Theorem | 28,984 | 10 | 1.9832092518 | 1.98 |

These records are in `four_color_hist.dat`; `hist_deg.pro` reads their saved
cutoff and exponent when drawing the published degree-distribution figure.

## Important qualification: four small networks used a lower cutoff

The fixed-10 call reproduces the large-network table exceptionally closely. In
a compatibility rerun using `powerlaw==1.4.6` and the recovered DAGs, 42 of 47
node-matched table entries round exactly to the published exponent at
`xmin=10`. This package version is a compatibility test, not evidence that it
was the version installed in 2020; the archive does not pin the old environment.

Four of the five nonmatching rows are the four smallest networks. Their
published exponent *and standard error* are recovered together by the same
discrete fitter at `xmin=5`:

| network | nodes | refit at `xmin=5` | published |
|---|---:|---:|---:|
| Powerset Theorem | 282 | 2.4146 ± 0.3245 | 2.41 ± 0.32 |
| Triangle Angles | 739 | 2.3808 ± 0.1934 | 2.38 ± 0.19 |
| Prime Squares | 250 | 2.2504 ± 0.2869 | 2.25 ± 0.29 |
| Pascal's Hexagon | 150 | 2.3239 ± 0.3418 | 2.32 ± 0.34 |

No surviving script found in either archive contains this fixed-5 table path.
The most likely interpretation is that a small-network exception was applied by
an earlier or uncommitted version of the fitter. This is an inference from the
joint alpha/error reproduction, not direct code provenance. The fifth mismatch,
Triangle Inequality, is small: the surviving fixed-10 call gives 2.1424 ± 0.0554,
while the table reports 2.13 ± 0.06.

Thus the defensible historical conclusion is:

- The main published power-law analysis used an explicit discrete tail cutoff;
  it was not a plotting-range convention.
- The surviving production script fixes `xmin=10`, and saved outputs verify that
  convention for the featured large networks.
- The table appears to use `xmin=5` for four very small networks. The exact rule
  or missing script that made this exception remains unresolved.

The modern audit imposes a minimum of ten tail observations. Under that rule,
44 of the 47 node-matched networks are estimable at `xmin=10`; 40 are within
0.01 and 43 within 0.02 of the published alpha. This is why some repository
summaries use a denominator of 44 rather than 47.

## Archive file fingerprints

These hashes identify the files inspected:

| archive file | SHA-256 |
|---|---|
| `pl.py` | `206122a335506252c8e271e3e4f41c7cdbd9d400b377c664fca2a468ab07e3bb` |
| `convert.rb` | `f858495a016511fe0c8a480f5cd5921a61e8709c51ae5b3bec9a36a06f3e3f93` |
| `convert_final_check.rb` | `5862ef28c97850c9164ffb1912ea61fa7769ac0b40b08735cf72ab8d768bb8b4` |
| `histogram.rb` | `8336c746070a8793e2278e11d787e02ab5bbe3dda0e468d147d2b7c2f44deb2e` |
| `hist_deg.pro` | `9666d4e809b65eef228f090ba43e9f90a5c91fde837c38ad3e5e5ccb35f3beaf` |
