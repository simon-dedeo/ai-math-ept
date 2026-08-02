"""Regression: a timed-out lake wrapper must not leave its Lean child alive."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from extract_binder_use import _run_one


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    workdir = ROOT / "tmp/horizon/timeout_cleanup"
    workdir.mkdir(parents=True, exist_ok=True)
    source = workdir / "source.lean"
    generated = workdir / "generated.lean"
    output = workdir / "output.json"
    template = workdir / "template.lean"
    wrapper = workdir / "fake_lake"
    child_pid_file = workdir / "child.pid"
    source.write_text("theorem demo : True := by trivial\n")
    template.write_text("")
    wrapper.write_text(
        "#!/bin/sh\n"
        "sleep 60 &\n"
        "child=$!\n"
        "printf '%s' \"$child\" > \"$FAKE_CHILD_PID_FILE\"\n"
        "wait \"$child\"\n"
    )
    wrapper.chmod(0o755)
    child_pid_file.unlink(missing_ok=True)
    os.environ["FAKE_CHILD_PID_FILE"] = str(child_pid_file)
    _run_one.template_path = str(template)
    _run_one.lake_path = str(wrapper)
    _run_one.mathlib_path = str(workdir)
    _run_one.timeout = 1
    _run_one.max_rec_depth = 1000
    result = _run_one((
        "h", "pair_timeout", str(source), str(generated), str(output), "demo"
    ))
    assert result["status"] == "timeout", result
    child_pid = int(child_pid_file.read_text())
    alive = subprocess.run(
        ["ps", "-p", str(child_pid)], capture_output=True, text=True
    ).returncode == 0
    assert not alive, f"orphaned child process {child_pid}"
    print({"status": result["status"], "orphan_survived": alive})


if __name__ == "__main__":
    main()
