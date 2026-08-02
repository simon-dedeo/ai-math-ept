"""Publication figures for the proof-horizon analysis."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "horizon" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
HUMAN = "#255f85"
AI = "#d96b4b"
GRAY = "#6c737f"


def save(fig: plt.Figure, name: str) -> None:
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def claim_functions() -> None:
    source = json.loads((ROOT / "results/horizon/source_summary.json").read_text())
    binder = json.loads((ROOT / "results/horizon/binder_summary.json").read_text())
    proofs = pd.read_csv(ROOT / "results/horizon/source_pairs.csv.gz")

    fig, axes = plt.subplots(1, 4, figsize=(11.2, 2.75))
    colors = [HUMAN, AI]
    labels = ["Human", "AI"]

    rates = [
        100 * proofs.h_named_haves.sum() / proofs.h_tokens.sum(),
        100 * proofs.a_named_haves.sum() / proofs.a_tokens.sum(),
    ]
    axes[0].bar(labels, rates, color=colors, width=0.62)
    axes[0].set_ylabel("named claims per 100 tokens")
    axes[0].set_title("A  Local decomposition", loc="left", fontweight="bold")
    axes[0].set_ylim(0, max(rates) * 1.25)
    for i, value in enumerate(rates):
        axes[0].text(i, value + 0.08, f"{value:.2f}", ha="center", fontsize=9)

    fates = ["zero_uptake_share", "one_uptake_share", "multi_uptake_share"]
    fate_labels = ["zero", "one", "multiple"]
    x = np.arange(3)
    for offset, side, label, color in (
        (-0.11, "human", "Human", HUMAN), (0.11, "ai", "AI", AI)
    ):
        values = [source["claim_rates"][side][metric]["estimate"] for metric in fates]
        intervals = [source["claim_rates"][side][metric]["source_cluster_ci"] for metric in fates]
        errors = np.asarray([
            [value - interval[0] for value, interval in zip(values, intervals)],
            [interval[1] - value for value, interval in zip(values, intervals)],
        ])
        axes[1].errorbar(
            x + offset, values, yerr=errors, fmt="o", color=color, capsize=2.5,
            lw=1.2, ms=5, label=label,
        )
    axes[1].set_xticks(x, fate_labels)
    axes[1].set_ylim(0, .62)
    axes[1].set_ylabel("share of named claims")
    axes[1].set_title("B  Explicit uptake", loc="left", fontweight="bold")
    axes[1].legend(frameon=False, fontsize=8, loc="upper right")

    fates_term = ["zero_term_use", "one_term_use", "multi_term_use"]
    for offset, side, color in ((-0.11, "human", HUMAN), (0.11, "ai", AI)):
        values = [binder["claim_rates_complete_pairs"][side][metric]["estimate"] for metric in fates_term]
        intervals = [binder["claim_rates_complete_pairs"][side][metric]["source_cluster_ci"] for metric in fates_term]
        errors = np.asarray([
            [value - interval[0] for value, interval in zip(values, intervals)],
            [interval[1] - value for value, interval in zip(values, intervals)],
        ])
        axes[2].errorbar(
            x + offset, values, yerr=errors, fmt="o", color=color, capsize=2.5,
            lw=1.2, ms=5,
        )
    axes[2].set_xticks(x, fate_labels)
    axes[2].set_ylim(0, .62)
    axes[2].set_ylabel("share of matched binders")
    axes[2].set_title("C  Elaborated-term use", loc="left", fontweight="bold")

    descriptive = [
        1 - source["claim_rates"]["human"]["placeholder_name_share"]["estimate"],
        1 - source["claim_rates"]["ai"]["placeholder_name_share"]["estimate"],
    ]
    adopted = [
        1 - source["claim_rates"]["human"]["zero_uptake_share"]["estimate"],
        1 - source["claim_rates"]["ai"]["zero_uptake_share"]["estimate"],
    ]
    descriptive_intervals = [
        [1 - source["claim_rates"][side]["placeholder_name_share"]["source_cluster_ci"][1],
         1 - source["claim_rates"][side]["placeholder_name_share"]["source_cluster_ci"][0]]
        for side in ("human", "ai")
    ]
    adopted_intervals = [
        [1 - source["claim_rates"][side]["zero_uptake_share"]["source_cluster_ci"][1],
         1 - source["claim_rates"][side]["zero_uptake_share"]["source_cluster_ci"][0]]
        for side in ("human", "ai")
    ]
    generalized = [
        source["claim_rates"]["human"]["generalized_claim_share"]["estimate"],
        source["claim_rates"]["ai"]["generalized_claim_share"]["estimate"],
    ]
    generalized_intervals = [
        source["claim_rates"][side]["generalized_claim_share"]["source_cluster_ci"]
        for side in ("human", "ai")
    ]
    human_values = [descriptive[0], adopted[0], generalized[0]]
    ai_values = [descriptive[1], adopted[1], generalized[1]]
    human_intervals = [descriptive_intervals[0], adopted_intervals[0], generalized_intervals[0]]
    ai_intervals = [descriptive_intervals[1], adopted_intervals[1], generalized_intervals[1]]
    x = np.arange(3)
    width = 0.34
    axes[3].bar(
        x - width / 2, human_values, width,
        color=HUMAN, label="Human", capsize=2.5,
        yerr=np.asarray([
            [value - interval[0] for value, interval in zip(human_values, human_intervals)],
            [interval[1] - value for value, interval in zip(human_values, human_intervals)],
        ]),
    )
    axes[3].bar(
        x + width / 2, ai_values, width,
        color=AI, label="AI", capsize=2.5,
        yerr=np.asarray([
            [value - interval[0] for value, interval in zip(ai_values, ai_intervals)],
            [interval[1] - value for value, interval in zip(ai_values, ai_intervals)],
        ]),
    )
    axes[3].set_xticks(
        x,
        ["outside\nplaceholder list", "explicitly\nadopted", "states a\nlocal family"],
    )
    axes[3].set_ylim(0, 0.90)
    axes[3].set_ylabel("share of named claims")
    axes[3].set_title("D  Interface investment", loc="left", fontweight="bold")
    axes[3].legend(frameon=False, fontsize=8, loc="upper right")

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8)
    fig.subplots_adjust(wspace=0.52)
    save(fig, "claim_functions")


def source_consistency() -> None:
    frame = pd.read_csv(ROOT / "results/horizon/by_source.csv").sort_values(
        "human_explicit_uses_per_claim"
    )
    names = frame.source.str.replace("_", " ")
    use_delta = frame.ai_explicit_uses_per_claim - frame.human_explicit_uses_per_claim
    zero_delta = frame.ai_zero_uptake_share - frame.human_zero_uptake_share
    family_delta = frame.ai_generalized_claim_share - frame.human_generalized_claim_share

    fig, axes = plt.subplots(1, 3, figsize=(9.6, 4.2), sharey=True)
    y = np.arange(len(frame))
    for ax, values, title in zip(
        axes,
        (use_delta, zero_delta, family_delta),
        ("explicit uses / claim", "zero-uptake share", "local-family share"),
    ):
        ax.axvline(0, color="#333333", lw=0.8)
        ax.scatter(values, y, c=np.where(values < 0, HUMAN, AI), s=30, zorder=3)
        ax.set_xlabel("AI minus human")
        ax.set_title(title, fontsize=10)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.grid(axis="x", color="#e5e5e5", lw=0.7)
    axes[0].set_yticks(y, names)
    axes[0].tick_params(axis="y", labelsize=8)
    fig.suptitle("The source-level contrast is not carried by one problem collection", fontsize=11)
    fig.subplots_adjust(wspace=0.25)
    save(fig, "source_consistency")


def surprise_pulse() -> None:
    tokens = pd.read_csv(ROOT / "results/horizon/token_surprisal.tsv", sep="\t")
    claims = pd.read_csv(ROOT / "results/horizon/surprisal_claims_w8.csv.gz")
    curves: list[dict[str, float | str | int]] = []
    token_groups = {name: group.sort_values("token_index").reset_index(drop=True) for name, group in tokens.groupby("document")}
    for row in claims.itertuples(index=False):
        document = f"{row.pair}_{row.side}"
        frame = token_groups[document]
        positions = frame.index[frame.token_index.eq(row.boundary_token_index)].tolist()
        if not positions:
            continue
        boundary = positions[0]
        if boundary < 16 or boundary + 25 >= len(frame):
            continue
        baseline = frame.iloc[boundary - 16 : boundary].nll_nats.mean()
        for offset in range(-16, 25):
            curves.append({
                "pair": row.pair, "side": row.side, "offset": offset,
                "relative_nll": float(frame.iloc[boundary + offset].nll_nats - baseline),
            })
    curve = pd.DataFrame(curves).groupby(["pair", "side", "offset"], as_index=False).relative_nll.mean()

    fig, ax = plt.subplots(figsize=(6.5, 3.25))
    for side, label, color in (("h", "Human", HUMAN), ("a", "AI", AI)):
        group = curve[curve.side.eq(side)]
        stats_frame = group.groupby("offset").relative_nll.agg(["mean", "sem"]).reset_index()
        ax.plot(stats_frame.offset, stats_frame["mean"], color=color, lw=2, label=label)
        ax.fill_between(
            stats_frame.offset,
            stats_frame["mean"] - 1.96 * stats_frame["sem"],
            stats_frame["mean"] + 1.96 * stats_frame["sem"],
            color=color, alpha=0.16, linewidth=0,
        )
    ax.axvline(0, color="#333333", lw=1, ls="--")
    ax.axhline(0, color="#999999", lw=0.7)
    ax.text(0.5, ax.get_ylim()[1] * 0.86, "have", fontsize=9)
    ax.set_xlabel("Gödel-Prover tokens from named-claim boundary")
    ax.set_ylabel("surprisal relative to prior 16 tokens (nats)")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    ax.set_title("Human claim boundaries carry a short information pulse", loc="left", fontsize=11)
    save(fig, "surprise_pulse")


def main() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42})
    claim_functions()
    source_consistency()
    surprise_pulse()
    print(f"wrote figures to {OUT}")


if __name__ == "__main__":
    main()
