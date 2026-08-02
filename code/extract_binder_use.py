"""Batch-run de-Bruijn-aware binder-use extraction on paired Lean files."""
from __future__ import annotations

import argparse
import csv
import hashlib
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


def _run_one(task: tuple[str, str, str, str, str, str]) -> dict[str, Any]:
    side, pair, source_path, work_path, output_path, target_override = task
    source = Path(source_path).read_text(errors="ignore")
    matches = DECL.findall(source)
    if not matches:
        return {"side": side, "pair": pair, "status": "no_declaration"}
    target = target_override or matches[-1]
    template = Path(_run_one.template_path).read_text()
    work = Path(work_path)
    work.write_text(
        source
        + "\n\n"
        + template
        + f'\nset_option maxRecDepth {_run_one.max_rec_depth} in\n'
        + f'#eval Horizon.writeBinderStats `{target} "{output_path}"\n'
    )
    try:
        proc = subprocess.run(
            [str(Path(_run_one.lake_path)), "env", "lean", str(work)],
            cwd=_run_one.mathlib_path,
            text=True,
            capture_output=True,
            timeout=_run_one.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "side": side, "pair": pair, "status": "timeout",
            "timeout_seconds": _run_one.timeout,
            "error": str(exc),
        }
    if proc.returncode != 0 or not Path(output_path).exists():
        return {
            "side": side, "pair": pair, "status": "failed", "returncode": proc.returncode,
            "error": (proc.stdout + "\n" + proc.stderr)[-4000:],
        }
    payload = json.loads(Path(output_path).read_text())
    return {"side": side, "pair": pair, "status": "ok", **payload}


def _init_worker(
    template_path: str, lake_path: str, mathlib_path: str, timeout: int,
    max_rec_depth: int,
) -> None:
    _run_one.template_path = template_path
    _run_one.lake_path = lake_path
    _run_one.mathlib_path = mathlib_path
    _run_one.timeout = timeout
    _run_one.max_rec_depth = max_rec_depth


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--mathlib-dir", type=Path, default=Path("mathlib4"),
        help="Mathlib checkout used for elaboration (relative to root by default)",
    )
    parser.add_argument(
        "--corpus-dir", type=Path,
        help="paired corpus containing human/ and ai/ (default: census/paired_numina)",
    )
    parser.add_argument("--pairs", type=Path, help="optional CSV with a `pair` column")
    parser.add_argument("--jobs", type=int, default=max(1, min(8, (os.cpu_count() or 2) - 1)))
    parser.add_argument("--max-pairs", type=int)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-rec-depth", type=int, default=100_000)
    parser.add_argument(
        "--tag", default="",
        help="suffix work and result paths so independent toolchain runs can coexist",
    )
    parser.add_argument(
        "--template", type=Path,
        default=Path("code/ExtractBinderUseLinear.lean.tmpl"),
        help="Lean extractor template (relative to root by default)",
    )
    parser.add_argument("--resume", action="store_true", help="reuse existing valid raw JSON")
    args = parser.parse_args()

    root = args.root.resolve()
    mathlib = args.mathlib_dir if args.mathlib_dir.is_absolute() else root / args.mathlib_dir
    mathlib = mathlib.resolve()
    corpus = (args.corpus_dir or (root / "census" / "paired_numina")).resolve()
    candidate = subprocess.run(
        ["bash", "-lc", "command -v lake"], text=True, capture_output=True, check=True
    ).stdout.strip()
    lake = Path(candidate)
    allowed: set[str] | None = None
    if args.pairs:
        import pandas as pd
        allowed = set(pd.read_csv(args.pairs)["pair"].astype(str))

    if args.tag and not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        raise ValueError("--tag may contain only letters, digits, underscore, and hyphen")
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("require --shard-count >= 1 and 0 <= --shard-index < --shard-count")
    suffix = f"_{args.tag}" if args.tag else ""
    workdir = mathlib / f"eptx_binder_work{suffix}"
    outdir = root / "results" / "horizon" / f"binder_raw{suffix}"
    workdir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    extraction_path = root / "results" / "horizon" / f"binder_extraction{suffix}.json"
    partial_path = root / "results" / "horizon" / f"binder_extraction{suffix}.partial.json"
    previous_by_key: dict[str, dict[str, Any]] = {}
    if args.resume:
        previous_rows: list[dict[str, Any]] = []
        for checkpoint in (extraction_path, partial_path):
            if checkpoint.exists():
                previous_rows.extend(json.loads(checkpoint.read_text()))
        previous_by_key = {
            f"{row['pair']}:{row['side']}": row for row in previous_rows
        }
    targets: dict[tuple[str, str], str] = {}
    target_manifest = corpus / "targets.csv"
    if target_manifest.exists():
        with target_manifest.open(newline="") as handle:
            for row in csv.DictReader(handle):
                targets[(row["pair"], "h")] = row["h_target"]
                targets[(row["pair"], "a")] = row["a_target"]
    tasks: list[tuple[str, str, str, str, str, str]] = []
    for side, folder in (("h", "human"), ("a", "ai")):
        for source in sorted((corpus / folder).glob("pair_*.lean")):
            pair = source.stem
            if allowed is not None and pair not in allowed:
                continue
            tasks.append((
                side, pair, str(source),
                str(workdir / f"{pair}_{side}.lean"),
                str(outdir / f"{pair}_{side}.json"),
                targets.get((pair, side), ""),
            ))
    if args.max_pairs:
        keep = sorted({task[1] for task in tasks})[: args.max_pairs]
        tasks = [task for task in tasks if task[1] in keep]
    if args.shard_count > 1:
        pairs = sorted({task[1] for task in tasks})
        lo = len(pairs) * args.shard_index // args.shard_count
        hi = len(pairs) * (args.shard_index + 1) // args.shard_count
        keep = set(pairs[lo:hi])
        tasks = [task for task in tasks if task[1] in keep]

    total_tasks = len(tasks)
    results: list[dict[str, Any]] = []
    pending: list[tuple[str, str, str, str, str, str]] = []
    for task in tasks:
        side, pair, _source, _work, output, _target = task
        previous = previous_by_key.get(f"{pair}:{side}")
        reusable = previous and previous.get("status") in {"failed", "no_declaration"}
        if reusable and previous.get("status") == "failed":
            error = str(previous.get("error", ""))
            if "declaration" in error and "not found" in error:
                reusable = False
        if previous and previous.get("status") == "ok" and Path(output).exists():
            reusable = True
        if reusable:
            results.append({**previous, "cached": True})
        else:
            pending.append(task)

    template = args.template if args.template.is_absolute() else root / args.template
    template = template.resolve()
    lean_version = subprocess.run(
        [str(lake), "env", "lean", "--version"], cwd=mathlib,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    mathlib_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=mathlib,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    provenance_path = (
        root / "results" / "horizon" / f"binder_extraction_provenance{suffix}.json"
    )
    static_provenance = {
        "corpus": str(corpus.relative_to(root) if corpus.is_relative_to(root) else corpus),
        "tasks": total_tasks,
        "lean_version": lean_version,
        "mathlib_commit": mathlib_commit,
        "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "extractor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
    }
    runs: list[dict[str, Any]] = []
    if provenance_path.exists():
        previous_provenance = json.loads(provenance_path.read_text())
        if all(previous_provenance.get(key) == value for key, value in static_provenance.items()):
            if "runs" in previous_provenance:
                runs.extend(previous_provenance["runs"])
            elif "jobs" in previous_provenance:
                runs.append({
                    "jobs": previous_provenance["jobs"],
                    "timeout_seconds": previous_provenance["timeout_seconds"],
                    "resume": None,
                    "reused_tasks": None,
                    "executed_tasks": None,
                })
    runs.append({
        "jobs": args.jobs,
        "timeout_seconds": args.timeout,
        "max_rec_depth": args.max_rec_depth,
        "resume": bool(args.resume),
        "reused_tasks": len(results),
        "executed_tasks": len(pending),
    })
    provenance_path.write_text(json.dumps({**static_provenance, "runs": runs}, indent=2))
    with ProcessPoolExecutor(
        max_workers=args.jobs,
        initializer=_init_worker,
        initargs=(str(template), str(lake), str(mathlib), args.timeout, args.max_rec_depth),
    ) as pool:
        futures = {pool.submit(_run_one, task): task for task in pending}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
            except Exception as exc:
                task = futures[future]
                result = {"side": task[0], "pair": task[1], "status": "exception", "error": repr(exc)}
            results.append(result)
            completed = total_tasks - len(pending) + index
            if index % 25 == 0 or result["status"] != "ok":
                print(f"{completed}/{total_tasks} {result['pair']} {result['side']} {result['status']}", flush=True)
            if index % 25 == 0:
                partial_path.write_text(json.dumps(
                    sorted(results, key=lambda row: (row["pair"], row["side"])), indent=2
                ))

    final_results = [
        {key: value for key, value in row.items() if key != "cached"}
        for row in results
    ]
    extraction_path.write_text(
        json.dumps(sorted(final_results, key=lambda row: (row["pair"], row["side"])), indent=2)
    )
    partial_path.unlink(missing_ok=True)
    counts = {
        status: sum(row["status"] == status for row in final_results)
        for status in sorted({row["status"] for row in final_results})
    }
    print(json.dumps({"tasks": total_tasks, "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
