#!/bin/bash
cd ~/ai_math_ept/census/human || exit 1
clone() {
  slug="$1"; url="$2"
  if [ -d "$slug/.git" ]; then echo "SKIP $slug"; return; fi
  rm -rf "$slug"
  echo "=== CLONING $slug from $url"
  git clone --depth 1 --quiet "$url" "$slug" 2>&1 | tail -3
  if [ -d "$slug/.git" ]; then
    echo "OK $slug $(du -sh $slug | cut -f1)"
  else
    echo "FAIL $slug"
  fi
}
clone carleson            https://github.com/fpvandoorn/carleson
clone ConNF               https://github.com/leanprover-community/con-nf
clone FLT-regular         https://github.com/leanprover-community/flt-regular
clone lean-matrix-cookbook https://github.com/eric-wieser/lean-matrix-cookbook
clone LeanAPAP            https://github.com/YaelDillies/LeanAPAP
clone ExponentialRamsey   https://github.com/b-mehta/ExponentialRamsey
clone unit-fractions      https://github.com/b-mehta/unit-fractions
clone BonnAnalysis        https://github.com/fpvandoorn/BonnAnalysis
clone sphere-eversion     https://github.com/leanprover-community/sphere-eversion
clone PhysLean            https://github.com/HEPLean/PhysLean
clone SciLean             https://github.com/lecopivo/SciLean
clone mathematics_in_lean https://github.com/leanprover-community/mathematics_in_lean
clone theorem_proving_in_lean4 https://github.com/leanprover/theorem_proving_in_lean4
clone math2001            https://github.com/hrmacbeth/math2001
clone math-classes        https://github.com/coq-community/math-classes
clone corn                https://github.com/coq-community/corn
clone coq-100-theorems    https://github.com/coq-community/coq-100-theorems
clone GeoCoq              https://github.com/GeoCoq/GeoCoq
clone fourcolor           https://github.com/coq-community/fourcolor
clone odd-order           https://github.com/math-comp/odd-order
clone math-comp           https://github.com/math-comp/math-comp
clone hydra-battles       https://github.com/coq-community/hydra-battles
clone coq-stdlib          https://github.com/rocq-prover/stdlib
echo "=== ALL LEAN/COQ DONE"
df -h ~ | tail -1
