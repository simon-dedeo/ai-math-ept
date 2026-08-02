"""Collect window-size sensitivity summaries for the horizon paper."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--windows", type=int, nargs="+", default=[4, 8, 16, 32])
    args = parser.parse_args()
    outdir = args.root.resolve() / "results" / "horizon"
    rows = []
    for window in args.windows:
        path = outdir / f"surprisal_summary_w{window}.json"
        data = json.loads(path.read_text())
        for metric, record in data["paired"].items():
            rows.append({"window": window, "metric": metric, **record})
    fields = [
        "window", "metric", "n_pairs", "human_median", "ai_median",
        "median_paired_difference", "probability_ai_greater", "wilcoxon_p",
    ]
    with (outdir / "surprisal_sensitivity.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
