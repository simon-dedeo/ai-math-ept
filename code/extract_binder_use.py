"""Batch-run de-Bruijn-aware binder-use extraction on paired Lean files."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DECL = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:private\s+|protected\s+|noncomputable\s+)*"
    r"(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_'.!?«»]*)",
    re.MULTILINE,
)


def _run_one(task: tuple[str, str, str, str, str]) -> dict[str, Any]:
    side, pair, source_path, work_path, output_path = task
    source = Path(source_path).read_text(errors="ignore")
    matches = DECL.findall(source)
    if not matches:
        return {"side": side, "pair": pair, "status": "no_declaration"}
    target = matches[-1]
    template = Path(_run_one.template_path).read_text()
    work = Path(work_path)
    work.write_text(
        source
        + "\n\n"
        + template
        + f'\n#eval Horizon.writeBinderStats `{target} "{output_path}"\n'
    )
    proc = subprocess.run(
        [str(Path(_run_one.lake_path)), "env", "lean", str(work)],
        cwd=_run_one.mathlib_path,
        text=True,
        capture_output=True,
        timeout=_run_one.timeout,
    )
    if proc.returncode != 0 or not Path(output_path).exists():
        return {
            "side": side, "pair": pair, "status": "failed", "returncode": proc.returncode,
            "error": (proc.stdout + "\n" + proc.stderr)[-4000:],
        }
    payload = json.loads(Path(output_path).read_text())
    return {"side": side, "pair": pair, "status": "ok", **payload}


def _init_worker(template_path: str, lake_path: str, mathlib_path: str, timeout: int) -> None:
    _run_one.template_path = template_path
    _run_one.lake_path = lake_path
    _run_one.mathlib_path = mathlib_path
    _run_one.timeout = timeout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--pairs", type=Path, help="optional CSV with a `pair` column")
    parser.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    root = args.root.resolve()
    mathlib = root / "mathlib4"
    candidate = subprocess.run(
        ["bash", "-lc", "command -v lake"], text=True, capture_output=True, check=True
    ).stdout.strip()
    lake = Path(candidate)
    allowed: set[str] | None = None
    if args.pairs:
        import pandas as pd
        allowed = set(pd.read_csv(args.pairs)["pair"].astype(str))

    workdir = mathlib / "eptx_binder_work"
    outdir = root / "results" / "horizon" / "binder_raw"
    workdir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    tasks: list[tuple[str, str, str, str, str]] = []
    for side, folder in (("h", "human"), ("a", "ai")):
        for source in sorted((root / "census" / "paired_numina" / folder).glob("pair_*.lean")):
            pair = source.stem
            if allowed is not None and pair not in allowed:
                continue
            tasks.append((
                side, pair, str(source),
                str(workdir / f"{pair}_{side}.lean"),
                str(outdir / f"{pair}_{side}.json"),
            ))
    if args.max_pairs:
        keep = sorted({task[1] for task in tasks})[: args.max_pairs]
        tasks = [task for task in tasks if task[1] in keep]

    template = root / "code" / "ExtractBinderUse.lean.tmpl"
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(
        max_workers=args.jobs,
        initializer=_init_worker,
        initargs=(str(template), str(lake), str(mathlib), args.timeout),
    ) as pool:
        futures = {pool.submit(_run_one, task): task for task in tasks}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
            except Exception as exc:
                task = futures[future]
                result = {"side": task[0], "pair": task[1], "status": "exception", "error": repr(exc)}
            results.append(result)
            if index % 25 == 0 or result["status"] != "ok":
                print(f"{index}/{len(tasks)} {result['pair']} {result['side']} {result['status']}", flush=True)

    (root / "results" / "horizon" / "binder_extraction.json").write_text(
        json.dumps(sorted(results, key=lambda row: (row["pair"], row["side"])), indent=2)
    )
    counts = {status: sum(row["status"] == status for row in results) for status in sorted({r["status"] for r in results})}
    print(json.dumps({"tasks": len(tasks), "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
