"""Test the Viteri--DeDeo Poisson in-degree claim in native graph formats.

The repository uses premise -> dependent edges, so in-degree is the number of
distinct immediate premises of an expression: its local arity.  The historical
plot discarded degree-zero leaves.  We retain that positive-degree conditioning
for direct comparability and fit the corresponding zero-truncated models.  We
also restore the leaves and compare ordinary Poisson, zero-inflated Poisson,
and hurdle models on the full degree distribution.

CoqAST applications are variadic while Lean Expr applications are binary, so
the cross-language rows produced here are diagnostics and must not be compared
as though local arity had the same atomic meaning.  The comparable reanalysis
is ``normalized_term_arity.py``.

Outputs:
  results/poisson_indegree/per_network.csv
  results/poisson_indegree/paired_comparison.csv
  results/poisson_indegree/calibration.csv
  results/poisson_indegree/summary.json
  report/standalone/poisson_numbers.tex
  report/standalone/figures/indegree_poisson_check.{pdf,png}
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.special import gammaln, logsumexp


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "poisson_indegree"
FIG = ROOT / "report" / "standalone" / "figures"
SEED = 20260801
N_BOOT_GOF = 199
N_BOOT_PAIRED = 20_000


def positive_arities_json(path: Path) -> tuple[np.ndarray, int, int]:
    d = json.loads(path.read_text())
    n = int(d["nodes"])
    degree = np.zeros(n, dtype=np.int64)
    edges = set(map(tuple, d["edges"]))
    for _, target in edges:
        target = int(target)
        if 0 <= target < n:
            degree[target] += 1
    return degree[degree > 0], n, int((degree == 0).sum())


def positive_arities_edges(path: Path) -> tuple[np.ndarray, int, int]:
    graph = nx.DiGraph()
    with path.open() as stream:
        for line in stream:
            fields = line.split()
            if len(fields) >= 2:
                graph.add_edge(fields[0], fields[1])
    degree = np.fromiter((d for _, d in graph.in_degree()), dtype=np.int64)
    return degree[degree > 0], graph.number_of_nodes(), int((degree == 0).sum())


def ztp_lambda(sample_mean: float) -> float:
    """MLE lambda solving E[X | X>0] = sample_mean."""
    if sample_mean <= 1.0 + 1e-12:
        return 1e-10

    def equation(lam: float) -> float:
        return lam / (-math.expm1(-lam)) - sample_mean

    return float(optimize.brentq(equation, 1e-10, max(50.0, 2 * sample_mean + 10)))


def log_one_minus_exp(log_x: float) -> float:
    """log(1-exp(log_x)) for log_x <= 0."""
    if log_x < -math.log(2):
        return math.log1p(-math.exp(log_x))
    return math.log(-math.expm1(log_x))


def fit_poisson(x: np.ndarray) -> dict:
    lam = ztp_lambda(float(x.mean()))
    ll = float(np.sum(x * math.log(lam) - lam - gammaln(x + 1))
               - len(x) * math.log1p(-math.exp(-lam)))
    return {"model": "poisson", "ll": ll, "aic": 2 - 2 * ll,
            "bic": math.log(len(x)) - 2 * ll, "lambda": lam, "npar": 1}


def fit_ordinary_poisson(x: np.ndarray, zero_n: int) -> dict:
    """Fit an ordinary Poisson to zeros and positive observations together."""
    n = len(x) + zero_n
    lam = float(x.sum() / n)
    ll = float(np.sum(x * math.log(lam) - gammaln(x + 1)) - n * lam)
    return {"model": "ordinary_poisson", "ll": ll, "aic": 2 - 2 * ll,
            "bic": math.log(n) - 2 * ll, "lambda": lam, "npar": 1}


def fit_hurdle(model: dict, zero_n: int, positive_n: int) -> dict:
    """Add a freely fitted Bernoulli zero mass to a positive-count model."""
    n = zero_n + positive_n
    q = zero_n / n
    bernoulli_ll = zero_n * math.log(q) if zero_n else 0.0
    bernoulli_ll += positive_n * math.log1p(-q) if positive_n else 0.0
    ll = float(model["ll"] + bernoulli_ll)
    npar = model["npar"] + 1
    return {"model": f"hurdle_{model['model']}", "ll": ll,
            "aic": 2 * npar - 2 * ll, "bic": npar * math.log(n) - 2 * ll,
            "zero_probability": q, "npar": npar}


def fit_zip(x: np.ndarray, zero_n: int, positive_poisson: dict) -> dict:
    """Fit a zero-inflated Poisson, whose point mass can only add zeros.

    At an interior optimum, positive observations identify lambda through their
    zero-truncated distribution and the observed zero fraction identifies the
    inflation weight.  If that weight would be negative, ZIP collapses to an
    ordinary Poisson at the boundary pi=0.
    """
    n = len(x) + zero_n
    q = zero_n / n
    lam = positive_poisson["lambda"]
    poisson_zero = math.exp(-lam)
    pi = (q - poisson_zero) / (1 - poisson_zero)
    if pi >= 0:
        hurdle = fit_hurdle(positive_poisson, zero_n, len(x))
        return {"model": "zip", "ll": hurdle["ll"], "aic": hurdle["aic"],
                "bic": hurdle["bic"], "lambda": lam, "zero_inflation": pi,
                "at_boundary": False, "zero_probability": q, "npar": 2}
    ordinary = fit_ordinary_poisson(x, zero_n)
    return {"model": "zip", "ll": ordinary["ll"],
            "aic": 4 - 2 * ordinary["ll"],
            "bic": 2 * math.log(n) - 2 * ordinary["ll"],
            "lambda": ordinary["lambda"], "zero_inflation": 0.0,
            "at_boundary": True,
            "zero_probability": math.exp(-ordinary["lambda"]), "npar": 2}


def fit_geometric(x: np.ndarray) -> dict:
    p = 1.0 / float(x.mean())
    ll = float(len(x) * math.log(p) + np.sum(x - 1) * math.log1p(-p))
    return {"model": "geometric", "ll": ll, "aic": 2 - 2 * ll,
            "bic": math.log(len(x)) - 2 * ll, "p": p, "npar": 1}


def fit_negative_binomial(x: np.ndarray) -> dict:
    """Zero-truncated NB2, parameterized by untruncated mean and size."""
    n = len(x)

    def nll(params: np.ndarray) -> float:
        mean, size = np.exp(params)
        prob = size / (size + mean)
        logp0 = size * math.log(prob)
        normalizer = log_one_minus_exp(logp0)
        ll = (gammaln(x + size) - gammaln(size) - gammaln(x + 1)
              + size * math.log(prob) + x * math.log1p(-prob))
        return float(-np.sum(ll) + n * normalizer)

    starts = [(math.log(max(float(x.mean()) - 0.5, 0.2)), math.log(r))
              for r in (0.5, 2.0, 20.0, 1000.0)]
    fits = [optimize.minimize(nll, start, method="L-BFGS-B",
                             bounds=[(-8, 8), (-6, 16)]) for start in starts]
    fit = min(fits, key=lambda item: item.fun)
    mean, size = np.exp(fit.x)
    ll = -float(fit.fun)
    return {"model": "negative_binomial", "ll": ll, "aic": 4 - 2 * ll,
            "bic": 2 * math.log(n) - 2 * ll, "nb_mean": float(mean),
            "nb_size": float(size), "npar": 2}


def cmp_logweights(theta: float, log_nu: float, max_observed: int) -> tuple[np.ndarray, np.ndarray]:
    """Positive-support COM-Poisson log weights.

    theta = log(lambda)/nu, so exp(theta) is approximately the mode and the
    optimization remains stable for the highly underdispersed Lean graphs.
    """
    nu = math.exp(log_nu)
    upper = max(120, 2 * max_observed + 50)
    while True:
        k = np.arange(1, upper + 1, dtype=float)
        logw = nu * (k * theta - gammaln(k + 1))
        if upper >= 20_000 or logw[-1] < np.max(logw) - 45:
            return k, logw
        upper *= 2


def fit_cmp(x: np.ndarray) -> dict:
    """Fit a zero-truncated Conway--Maxwell--Poisson distribution."""
    n = len(x)
    max_x = int(x.max())
    sum_logfac = float(np.sum(gammaln(x + 1)))
    sum_x = float(np.sum(x))

    def nll(params: np.ndarray) -> float:
        theta, log_nu = map(float, params)
        nu = math.exp(log_nu)
        _, logw = cmp_logweights(theta, log_nu, max_x)
        logz = float(logsumexp(logw))
        ll = nu * (theta * sum_x - sum_logfac) - n * logz
        return -ll

    center = math.log(max(float(np.median(x)), 1.0))
    starts = [(center, value) for value in (0.0, 1.0, 3.0, 6.0)]
    bounds = [(-6.0, math.log(max_x + 2.0) + 2.0), (-4.0, 9.0)]
    fits = [optimize.minimize(nll, start, method="L-BFGS-B", bounds=bounds)
            for start in starts]
    fit = min(fits, key=lambda item: item.fun)
    theta, log_nu = map(float, fit.x)
    ll = -float(fit.fun)
    return {"model": "cmp", "ll": ll, "aic": 4 - 2 * ll,
            "bic": 2 * math.log(n) - 2 * ll, "cmp_theta": theta,
            "cmp_nu": math.exp(log_nu), "cmp_at_bound": log_nu > 8.99,
            "npar": 2}


def ztp_poisson_pmf(lam: float, upper: int) -> np.ndarray:
    k = np.arange(1, upper + 1)
    logp = k * math.log(lam) - lam - gammaln(k + 1) - math.log1p(-math.exp(-lam))
    return np.exp(logp)


def cmp_pmf(model: dict, upper: int) -> np.ndarray:
    k, logw = cmp_logweights(model["cmp_theta"], math.log(model["cmp_nu"]), upper)
    p = np.exp(logw - logsumexp(logw))
    if len(p) < upper:
        p = np.pad(p, (0, upper - len(p)))
    return p[:upper]


def ks_statistic_from_counts(counts: np.ndarray, lam: float) -> float:
    pmf = ztp_poisson_pmf(lam, len(counts))
    pmf[-1] += max(0.0, 1.0 - pmf.sum())
    return float(np.max(np.abs(np.cumsum(counts / counts.sum()) - np.cumsum(pmf))))


def poisson_gof(x: np.ndarray, lam: float, seed: int) -> tuple[float, float]:
    upper = max(int(x.max()), int(stats.poisson.ppf(1 - 1e-12, lam)))
    pmf = ztp_poisson_pmf(lam, upper)
    pmf[-1] += max(0.0, 1.0 - pmf.sum())
    pmf /= pmf.sum()
    counts = np.bincount(x, minlength=upper + 1)[1:upper + 1]
    observed = ks_statistic_from_counts(counts, lam)
    rng = np.random.default_rng(seed)
    simulated = rng.multinomial(len(x), pmf, size=N_BOOT_GOF)
    null_stats = np.empty(N_BOOT_GOF)
    values = np.arange(1, upper + 1)
    for i, draw in enumerate(simulated):
        fitted = ztp_lambda(float(np.dot(draw, values) / draw.sum()))
        null_stats[i] = ks_statistic_from_counts(draw, fitted)
    p = (1 + int(np.sum(null_stats >= observed))) / (N_BOOT_GOF + 1)
    return observed, float(p)


def zip_pmf(model: dict, upper: int) -> np.ndarray:
    """ZIP probabilities on 0..upper, with the residual tail in upper."""
    if model["at_boundary"]:
        pmf = stats.poisson.pmf(np.arange(upper + 1), model["lambda"])
    else:
        pmf = np.zeros(upper + 1)
        q = model["zero_probability"]
        pmf[0] = q
        pmf[1:] = (1 - q) * ztp_poisson_pmf(model["lambda"], upper)
    pmf[-1] += max(0.0, 1.0 - pmf.sum())
    return pmf / pmf.sum()


def fit_zip_counts(counts: np.ndarray) -> dict:
    """Refit ZIP from category counts for the parametric bootstrap."""
    n = int(counts.sum())
    positive_n = n - int(counts[0])
    values = np.arange(len(counts))
    positive_mean = float(np.dot(counts, values) / positive_n)
    positive_lambda = ztp_lambda(positive_mean)
    q = float(counts[0] / n)
    poisson_zero = math.exp(-positive_lambda)
    pi = (q - poisson_zero) / (1 - poisson_zero)
    if pi >= 0:
        return {"lambda": positive_lambda, "zero_inflation": pi,
                "zero_probability": q, "at_boundary": False}
    lam = float(np.dot(counts, values) / n)
    return {"lambda": lam, "zero_inflation": 0.0,
            "zero_probability": math.exp(-lam), "at_boundary": True}


def zip_ks_from_counts(counts: np.ndarray, model: dict) -> float:
    expected = zip_pmf(model, len(counts) - 1)
    observed = counts / counts.sum()
    return float(np.max(np.abs(np.cumsum(observed) - np.cumsum(expected))))


def zip_gof(x: np.ndarray, zero_n: int, model: dict, seed: int) -> tuple[float, float]:
    """Absolute-fit test for ZIP, including its fitted special-zero term."""
    upper = max(int(x.max()), int(stats.poisson.ppf(1 - 1e-12, model["lambda"])))
    counts = np.bincount(np.r_[np.zeros(zero_n, dtype=int), x], minlength=upper + 1)
    pmf = zip_pmf(model, upper)
    observed = zip_ks_from_counts(counts, model)
    rng = np.random.default_rng(seed)
    simulated = rng.multinomial(len(x) + zero_n, pmf, size=N_BOOT_GOF)
    null_stats = np.empty(N_BOOT_GOF)
    for i, draw in enumerate(simulated):
        fitted = fit_zip_counts(draw)
        null_stats[i] = zip_ks_from_counts(draw, fitted)
    p = (1 + int(np.sum(null_stats >= observed))) / (N_BOOT_GOF + 1)
    return observed, float(p)


def analyse_graph(label: str, name: str, x: np.ndarray, total_n: int,
                  zero_n: int, seed: int) -> tuple[dict, dict]:
    if len(x) < 20:
        raise ValueError(f"{name}: fewer than 20 positive-arity nodes")
    models = [fit_poisson(x), fit_geometric(x), fit_negative_binomial(x), fit_cmp(x)]
    by_name = {m["model"]: m for m in models}
    winner = min(models, key=lambda m: m["aic"])["model"]
    poisson = by_name["poisson"]
    cmp_model = by_name["cmp"]
    ordinary = fit_ordinary_poisson(x, zero_n)
    zip_model = fit_zip(x, zero_n, poisson)
    hurdle_models = {name: fit_hurdle(model, zero_n, len(x))
                     for name, model in by_name.items()}
    mixed_aics = {
        "ordinary_poisson": ordinary["aic"],
        "zero_inflated_poisson": zip_model["aic"],
        "hurdle_poisson": hurdle_models["poisson"]["aic"],
        "hurdle_geometric": hurdle_models["geometric"]["aic"],
        "hurdle_negative_binomial": hurdle_models["negative_binomial"]["aic"],
        "hurdle_cmp": hurdle_models["cmp"]["aic"],
    }
    mixed_winner = min(mixed_aics, key=mixed_aics.get)
    ks, p = poisson_gof(x, poisson["lambda"], seed)
    zip_ks, zip_p = zip_gof(x, zero_n, zip_model, seed + 1_000_000)
    lam = poisson["lambda"]
    ztp_mean = lam / (-math.expm1(-lam))
    ztp_var = ztp_mean * (1 + lam - ztp_mean)
    row = {
        "corpus": label, "name": name, "nodes": total_n,
        "positive_nodes": len(x), "zero_fraction": zero_n / total_n,
        "positive_mean": float(x.mean()), "positive_variance": float(x.var()),
        "variance_ratio_to_ztp": float(x.var() / ztp_var),
        "fraction_degree_1": float(np.mean(x == 1)),
        "fraction_degree_2": float(np.mean(x == 2)),
        "fraction_degree_3": float(np.mean(x == 3)),
        "max_degree": int(x.max()), "poisson_lambda": lam,
        "poisson_ks": ks, "poisson_bootstrap_p": p,
        "poisson_aic": poisson["aic"], "geometric_aic": by_name["geometric"]["aic"],
        "negative_binomial_aic": by_name["negative_binomial"]["aic"],
        "cmp_aic": cmp_model["aic"], "cmp_nu": cmp_model["cmp_nu"],
        "cmp_at_bound": cmp_model["cmp_at_bound"], "aic_winner": winner,
        "delta_aic_poisson_cmp": poisson["aic"] - cmp_model["aic"],
        "delta_aic_poisson_cmp_per_positive_node":
            (poisson["aic"] - cmp_model["aic"]) / len(x),
        "ordinary_poisson_aic_all": ordinary["aic"],
        "zero_inflated_poisson_aic_all": zip_model["aic"],
        "zip_lambda": zip_model["lambda"],
        "zip_pi": zip_model["zero_inflation"],
        "zip_at_zero_boundary": zip_model["at_boundary"],
        "zip_ks": zip_ks, "zip_bootstrap_p": zip_p,
        "hurdle_poisson_aic_all": hurdle_models["poisson"]["aic"],
        "hurdle_geometric_aic_all": hurdle_models["geometric"]["aic"],
        "hurdle_negative_binomial_aic_all": hurdle_models["negative_binomial"]["aic"],
        "hurdle_cmp_aic_all": hurdle_models["cmp"]["aic"],
        "mixed_model_aic_winner": mixed_winner,
        "delta_aic_zip_hurdle_cmp": zip_model["aic"] - hurdle_models["cmp"]["aic"],
        "delta_aic_zip_best_full_model": zip_model["aic"] - min(mixed_aics.values()),
        "delta_aic_hurdle_poisson_cmp":
            hurdle_models["poisson"]["aic"] - hurdle_models["cmp"]["aic"],
    }
    return row, {"x": x, "poisson": poisson, "cmp": cmp_model}


def bh_rejections(values: pd.Series, alpha: float = 0.05) -> int:
    p = np.sort(values.dropna().to_numpy(float))
    if len(p) == 0:
        return 0
    passing = np.flatnonzero(p <= alpha * np.arange(1, len(p) + 1) / len(p))
    return int(passing[-1] + 1) if len(passing) else 0


def corpus_summary(frame: pd.DataFrame) -> dict:
    winners = frame.aic_winner.value_counts().to_dict()
    mixed_winners = frame.mixed_model_aic_winner.value_counts().to_dict()
    return {
        "n_networks": int(len(frame)),
        "median_nodes": float(frame.nodes.median()),
        "median_positive_nodes": float(frame.positive_nodes.median()),
        "median_zero_fraction": float(frame.zero_fraction.median()),
        "median_positive_mean": float(frame.positive_mean.median()),
        "median_positive_variance": float(frame.positive_variance.median()),
        "median_variance_ratio_to_ztp": float(frame.variance_ratio_to_ztp.median()),
        "median_fraction_degree_2": float(frame.fraction_degree_2.median()),
        "median_poisson_ks": float(frame.poisson_ks.median()),
        "poisson_rejected_p_lt_0_05": int((frame.poisson_bootstrap_p < 0.05).sum()),
        "poisson_rejected_bh_0_05": bh_rejections(frame.poisson_bootstrap_p),
        "zip_rejected_p_lt_0_05": int((frame.zip_bootstrap_p < 0.05).sum()),
        "zip_rejected_bh_0_05": bh_rejections(frame.zip_bootstrap_p),
        "aic_winners": {str(k): int(v) for k, v in winners.items()},
        "median_delta_aic_poisson_cmp": float(frame.delta_aic_poisson_cmp.median()),
        "median_delta_aic_poisson_cmp_per_positive_node":
            float(frame.delta_aic_poisson_cmp_per_positive_node.median()),
        "cmp_upper_bound_n": int(frame.cmp_at_bound.sum()),
        "zip_at_zero_boundary_n": int(frame.zip_at_zero_boundary.sum()),
        "zip_positive_mixing_weight_n": int((~frame.zip_at_zero_boundary).sum()),
        "mixed_model_aic_winners": {str(k): int(v) for k, v in mixed_winners.items()},
        "median_zip_zero_inflation": float(frame.zip_pi.median()),
        "median_zip_ks": float(frame.zip_ks.median()),
        "median_delta_aic_zip_hurdle_cmp": float(frame.delta_aic_zip_hurdle_cmp.median()),
        "median_delta_aic_zip_best_full_model":
            float(frame.delta_aic_zip_best_full_model.median()),
        "median_delta_aic_hurdle_poisson_cmp":
            float(frame.delta_aic_hurdle_poisson_cmp.median()),
    }


def bootstrap_median_difference(x: np.ndarray, y: np.ndarray, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    delta = y - x
    indices = rng.integers(0, len(delta), size=(N_BOOT_PAIRED, len(delta)))
    values = np.median(delta[indices], axis=1)
    return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def paired_summary(paired: pd.DataFrame) -> dict:
    metrics = ["positive_mean", "variance_ratio_to_ztp", "fraction_degree_2",
               "poisson_ks", "zip_ks", "zip_pi",
               "delta_aic_poisson_cmp_per_positive_node"]
    out = {"n_pairs": int(len(paired)), "metrics": {}}
    for i, metric in enumerate(metrics):
        h = paired[f"human_{metric}"].to_numpy(float)
        a = paired[f"ai_{metric}"].to_numpy(float)
        try:
            p = float(stats.wilcoxon(h, a).pvalue)
        except ValueError:
            p = 1.0
        out["metrics"][metric] = {
            "human_median": float(np.median(h)), "ai_median": float(np.median(a)),
            "median_ai_minus_human": float(np.median(a - h)),
            "paired_bootstrap_ci": bootstrap_median_difference(h, a, SEED + i),
            "wilcoxon_p": p,
        }
    return out


def calibration_rows(records: dict[str, list[dict]], upper: int = 7) -> pd.DataFrame:
    rows = []
    for corpus, items in records.items():
        empirical, poisson, cmp_values = [], [], []
        for item in items:
            x = item["x"]
            emp = np.array([np.mean(x == k) for k in range(1, upper + 1)]
                           + [np.mean(x > upper)])
            pp = ztp_poisson_pmf(item["poisson"]["lambda"], upper)
            pp = np.r_[pp, max(0.0, 1 - pp.sum())]
            cp = cmp_pmf(item["cmp"], upper)
            cp = np.r_[cp, max(0.0, 1 - cp.sum())]
            empirical.append(emp)
            poisson.append(pp)
            cmp_values.append(cp)
        for model, matrix in [("empirical", empirical), ("poisson", poisson),
                              ("cmp", cmp_values)]:
            average = np.mean(np.vstack(matrix), axis=0)
            for k, value in enumerate(average, start=1):
                rows.append({"corpus": corpus, "model": model,
                             "degree": str(k) if k <= upper else f">{upper}",
                             "probability": float(value)})
    return pd.DataFrame(rows)


def make_figure(calibration: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8})
    corpora = ["Coq expanded terms", "Human Lean expanded terms",
               "Matched human Lean term0", "Matched AI Lean term0"]
    colors = {"empirical": "#222222", "poisson": "#B24C3D", "cmp": "#294C60"}
    labels = {"empirical": "observed", "poisson": "Poisson", "cmp": "COM-Poisson"}
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.8), sharex=True)
    for ax, corpus in zip(axes.flat, corpora):
        data = calibration[calibration.corpus == corpus]
        degrees = list(data[data.model == "empirical"].degree)
        xpos = np.arange(len(degrees))
        for model in ("empirical", "poisson", "cmp"):
            values = data[data.model == model].probability.to_numpy()
            ax.plot(xpos, values, marker="o", ms=3, lw=1.2,
                    color=colors[model], label=labels[model])
        ax.set_title(corpus)
        ax.set_xticks(xpos, degrees)
        ax.set_yscale("log")
        ax.set_ylim(1e-5, 1.2)
        ax.grid(alpha=.18, lw=.5)
    axes[0, 0].set_ylabel("mean probability per network")
    axes[1, 0].set_ylabel("mean probability per network")
    axes[1, 0].set_xlabel("positive in-degree (local arity)")
    axes[1, 1].set_xlabel("positive in-degree (local arity)")
    axes[0, 0].legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(1.08, 1.02))
    fig.tight_layout(rect=(0, 0, 1, .96))
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "indegree_poisson_check.pdf", bbox_inches="tight")
    fig.savefig(FIG / "indegree_poisson_check.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_macros(summary: dict) -> None:
    groups = summary["corpora"]
    pair = summary["matched_human_ai"]["metrics"]
    text = (
        "% Generated by code/poisson_indegree_appendix.py\n"
        f"\\newcommand{{\\PoissonCoqReject}}{{{groups['Coq expanded terms']['poisson_rejected_bh_0_05']}/49}}\n"
        f"\\newcommand{{\\PoissonLeanReject}}{{{groups['Human Lean expanded terms']['poisson_rejected_bh_0_05']}/33}}\n"
        f"\\newcommand{{\\PoissonHumanReject}}{{{groups['Matched human Lean term0']['poisson_rejected_bh_0_05']}/312}}\n"
        f"\\newcommand{{\\PoissonAIReject}}{{{groups['Matched AI Lean term0']['poisson_rejected_bh_0_05']}/312}}\n"
        f"\\newcommand{{\\ZIPCoqReject}}{{{groups['Coq expanded terms']['zip_rejected_bh_0_05']}/49}}\n"
        f"\\newcommand{{\\ZIPLeanReject}}{{{groups['Human Lean expanded terms']['zip_rejected_bh_0_05']}/33}}\n"
        f"\\newcommand{{\\ZIPHumanReject}}{{{groups['Matched human Lean term0']['zip_rejected_bh_0_05']}/312}}\n"
        f"\\newcommand{{\\ZIPAIReject}}{{{groups['Matched AI Lean term0']['zip_rejected_bh_0_05']}/312}}\n"
        f"\\newcommand{{\\CoqDispersionRatio}}{{{groups['Coq expanded terms']['median_variance_ratio_to_ztp']:.3f}}}\n"
        f"\\newcommand{{\\LeanDispersionRatio}}{{{groups['Human Lean expanded terms']['median_variance_ratio_to_ztp']:.3f}}}\n"
        f"\\newcommand{{\\HumanDegreeTwo}}{{{pair['fraction_degree_2']['human_median']:.4f}}}\n"
        f"\\newcommand{{\\AIDegreeTwo}}{{{pair['fraction_degree_2']['ai_median']:.4f}}}\n"
        f"\\newcommand{{\\DegreeTwoPairP}}{{{pair['fraction_degree_2']['wilcoxon_p']:.3g}}}\n"
        f"\\newcommand{{\\CoqCMPWins}}{{{groups['Coq expanded terms']['aic_winners'].get('cmp', 0)}/49}}\n"
        f"\\newcommand{{\\LeanCMPWins}}{{{groups['Human Lean expanded terms']['aic_winners'].get('cmp', 0)}/33}}\n"
        f"\\newcommand{{\\HumanCMPWins}}{{{groups['Matched human Lean term0']['aic_winners'].get('cmp', 0)}/312}}\n"
        f"\\newcommand{{\\AICMPWins}}{{{groups['Matched AI Lean term0']['aic_winners'].get('cmp', 0)}/312}}\n"
        f"\\newcommand{{\\ZIPCoqBoundary}}{{{groups['Coq expanded terms']['zip_at_zero_boundary_n']}/49}}\n"
        f"\\newcommand{{\\ZIPLeanBoundary}}{{{groups['Human Lean expanded terms']['zip_at_zero_boundary_n']}/33}}\n"
        f"\\newcommand{{\\ZIPHumanBoundary}}{{{groups['Matched human Lean term0']['zip_at_zero_boundary_n']}/312}}\n"
        f"\\newcommand{{\\ZIPAIBoundary}}{{{groups['Matched AI Lean term0']['zip_at_zero_boundary_n']}/312}}\n"
        f"\\newcommand{{\\CoqZIPPi}}{{{groups['Coq expanded terms']['median_zip_zero_inflation']:.3f}}}\n"
    )
    (ROOT / "report" / "standalone" / "poisson_numbers.tex").write_text(text)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records: dict[str, list[dict]] = {
        "Coq expanded terms": [], "Human Lean expanded terms": [],
        "Matched human Lean term0": [], "Matched AI Lean term0": []}
    rows = []
    counter = 0

    for path in sorted((ROOT / "networks" / "coq2022_edges").glob("*.edges")):
        x, n, z = positive_arities_edges(path)
        row, record = analyse_graph("Coq expanded terms", path.stem, x, n, z,
                                    SEED + counter)
        rows.append(row); records[row["corpus"]].append(record); counter += 1

    study1 = pd.read_csv(ROOT / "results" / "study1" / "results.csv")
    for name in sorted(study1.loc[study1.name.str.endswith("_term"), "name"]):
        path = ROOT / "networks" / "batch1" / f"{name}.json"
        x, n, z = positive_arities_json(path)
        row, record = analyse_graph("Human Lean expanded terms", name, x, n, z,
                                    SEED + counter)
        rows.append(row); records[row["corpus"]].append(record); counter += 1

    pair_ids = pd.read_csv(ROOT / "results" / "final_synthesis" /
                           "paired_belief_term0.csv").pair.tolist()
    pair_rows = []
    for pair_id in pair_ids:
        combined = {"pair": pair_id}
        for side, corpus in [("human", "Matched human Lean term0"),
                             ("ai", "Matched AI Lean term0")]:
            path = ROOT / "networks" / f"paired_{side}" / f"{pair_id}_term0.json"
            x, n, z = positive_arities_json(path)
            row, record = analyse_graph(corpus, pair_id, x, n, z, SEED + counter)
            rows.append(row); records[corpus].append(record); counter += 1
            for key, value in row.items():
                if key not in ("corpus", "name"):
                    combined[f"{side}_{key}"] = value
        pair_rows.append(combined)
        if len(pair_rows) % 50 == 0:
            print(f"analysed {len(pair_rows)}/{len(pair_ids)} matched pairs", flush=True)

    frame = pd.DataFrame(rows)
    paired = pd.DataFrame(pair_rows)
    calibration = calibration_rows(records)
    summary = {
        "definition": "in-degree under premise-to-dependent orientation; distinct immediate premises",
        "conditioning": "degree > 0, matching the historical histogram",
        "models": ["zero-truncated Poisson", "positive geometric",
                   "zero-truncated negative binomial", "zero-truncated COM-Poisson"],
        "zero_sensitivity_models": ["ordinary Poisson", "zero-inflated Poisson",
                                    "hurdle Poisson", "hurdle geometric",
                                    "hurdle negative binomial",
                                    "hurdle COM-Poisson"],
        "poisson_gof": {"statistic": "discrete KS with parameter refit",
                        "bootstrap_replicates": N_BOOT_GOF, "seed": SEED,
                        "multiple_testing": "Benjamini-Hochberg within corpus at q=0.05"},
        "corpora": {name: corpus_summary(frame[frame.corpus == name]) for name in records},
        "matched_human_ai": paired_summary(paired),
    }

    frame.to_csv(OUT / "per_network.csv", index=False)
    paired.to_csv(OUT / "paired_comparison.csv", index=False)
    calibration.to_csv(OUT / "calibration.csv", index=False)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    make_figure(calibration)
    write_macros(summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
