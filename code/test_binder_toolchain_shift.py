"""Regression: one source `have` has two toolchain-specific core encodings."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAIR = "pair_064daf4b"
TARGET = "number_theory_165209"


def extract(mathlib: Path, label: str) -> dict:
    source = (ROOT / f"census/paired_numina_exact/human/{PAIR}.lean").read_text()
    template_name = (
        "ExtractBinderUseLegacy.lean.tmpl"
        if label == "mathlib415" else "ExtractBinderUseLinear.lean.tmpl"
    )
    template = (ROOT / "code" / template_name).read_text()
    workdir = ROOT / "tmp/horizon/toolchain_shift"
    workdir.mkdir(parents=True, exist_ok=True)
    lean_path = workdir / f"{label}.lean"
    output_path = workdir / f"{label}.json"
    lean_path.write_text(
        source + "\n\n" + template
        + f'\n#eval Horizon.writeBinderStats `{TARGET} "{output_path}"\n'
    )
    subprocess.run(
        ["lake", "env", "lean", str(lean_path)], cwd=mathlib,
        text=True, capture_output=True, check=True, timeout=300,
    )
    return json.loads(output_path.read_text())


def main() -> None:
    native = extract(ROOT / "mathlib4_v415", "mathlib415")
    current = extract(ROOT / "mathlib4", "mathlib433")
    native_names = [item["name"] for item in native["lets"]]
    current_names = [item["name"] for item in current["lets"]]
    assert native_names == ["h1"], native
    assert current_names == ["h1"], current
    assert native["lets"][0]["kind"] == "have_fun", native
    assert current["lets"][0]["kind"] == "let", current
    print({
        "pair": PAIR,
        "native_binders": [(x["kind"], x["name"], x["uses"]) for x in native["lets"]],
        "current_binders": [(x["kind"], x["name"], x["uses"]) for x in current["lets"]],
        "native_root_nodes": native["root_nodes"],
        "current_root_nodes": current["root_nodes"],
    })


if __name__ == "__main__":
    main()
