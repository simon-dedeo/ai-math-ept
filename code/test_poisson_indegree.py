"""Numerical sanity checks for poisson_indegree_appendix.py."""

import numpy as np

from poisson_indegree_appendix import (
    fit_cmp,
    fit_poisson,
    fit_zip,
    poisson_gof,
    zip_gof,
    ztp_poisson_pmf,
)


rng = np.random.default_rng(731)

# A genuine zero-truncated Poisson should recover lambda and should not be
# systematically rejected by the refitted parametric-bootstrap test.
true_lambda = 3.0
pmf = ztp_poisson_pmf(true_lambda, 30)
pmf /= pmf.sum()
sample = rng.choice(np.arange(1, 31), size=20_000, p=pmf)
poisson = fit_poisson(sample)
cmp_model = fit_cmp(sample)
ks, p = poisson_gof(sample, poisson["lambda"], 90210)
assert abs(poisson["lambda"] - true_lambda) < 0.05
assert 0.7 < cmp_model["cmp_nu"] < 1.4
assert p >= 0.05

# A grammar-like arity distribution concentrated at two is strongly
# underdispersed and should favor COM-Poisson over Poisson by AIC.
underdispersed = rng.choice([1, 2, 3], size=20_000, p=[0.002, 0.996, 0.002])
poisson_u = fit_poisson(underdispersed)
cmp_u = fit_cmp(underdispersed)
assert cmp_u["cmp_nu"] > 2
assert cmp_u["aic"] + 1000 < poisson_u["aic"]

# ZIP should recover a genuine excess-zero mixture.  With fewer zeros than
# the fitted positive Poisson implies, its mixing weight must instead hit zero.
zip_lambda = 2.5
zip_pi = 0.25
raw = rng.poisson(zip_lambda, size=30_000)
structural = rng.random(len(raw)) < zip_pi
raw[structural] = 0
zip_x = raw[raw > 0]
zip_zero_n = int((raw == 0).sum())
zip_model = fit_zip(zip_x, zip_zero_n, fit_poisson(zip_x))
zip_ks, zip_p = zip_gof(zip_x, zip_zero_n, zip_model, 90211)
assert not zip_model["at_boundary"]
assert abs(zip_model["lambda"] - zip_lambda) < 0.08
assert abs(zip_model["zero_inflation"] - zip_pi) < 0.03
assert zip_p >= 0.05

zero_deflated_x = rng.choice(np.arange(1, 31), size=20_000, p=pmf)
zero_deflated = fit_zip(zero_deflated_x, 500, fit_poisson(zero_deflated_x))
assert zero_deflated["at_boundary"]
assert zero_deflated["zero_inflation"] == 0.0

print({
    "synthetic_poisson_lambda": poisson["lambda"],
    "synthetic_poisson_cmp_nu": cmp_model["cmp_nu"],
    "synthetic_poisson_bootstrap_p": p,
    "underdispersed_cmp_nu": cmp_u["cmp_nu"],
    "underdispersed_delta_aic": poisson_u["aic"] - cmp_u["aic"],
    "synthetic_zip_lambda": zip_model["lambda"],
    "synthetic_zip_pi": zip_model["zero_inflation"],
    "synthetic_zip_bootstrap_p": zip_p,
    "zero_deflated_zip_boundary": zero_deflated["at_boundary"],
})
