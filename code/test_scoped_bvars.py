"""Regression test: de-Bruijn leaves from distinct scopes must not merge."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    extractor = (ROOT / "code" / "ExtractNetwork.lean").read_text()
    extractor = extractor.replace("import Mathlib", "", 1)
    fixture = """import Mathlib
def scopeFixture : (Nat → Nat) × (Nat → Nat) :=
  (fun x => Nat.succ x, fun y => Nat.pred y)
"""
    with tempfile.TemporaryDirectory(prefix="eptx_scope_") as directory:
        temp = Path(directory)
        work = temp / "ScopedFixture.lean"
        target = temp / "targets.tsv"
        output = temp / "scope.json"
        work.write_text(fixture + extractor)
        target.write_text(f"scopeFixture\t{output}\tterm0\t100000\n")
        env = dict(os.environ, TARGETS=str(target))
        proc = subprocess.run(
            ["lake", "env", "lean", str(work)],
            cwd=ROOT / "mathlib4",
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )
        if proc.returncode:
            raise RuntimeError(proc.stdout + proc.stderr)
        data = json.loads(output.read_text())
        count = data["labels"].count("fvar")
        assert count == 2, f"expected two scope identities, found {count}"
        print({"scope_specific_fvar_nodes": count, "nodes": data["nodes"]})


if __name__ == "__main__":
    main()
