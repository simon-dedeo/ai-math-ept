#!/bin/bash
cd ~/ai_math_ept/census || exit 1
c(){ slug=$1; url=$2;
  if [ -d "$slug/.git" ]; then echo "SKIP $slug"; return; fi
  git clone --depth 1 --quiet "$url" "$slug" 2>&1|tail -2
  if [ -d "$slug/.git" ]; then echo "OK $slug $(du -sh $slug|cut -f1) lean=$(find $slug -name '*.lean'|wc -l)"; else echo "FAIL $slug"; fi
}
c lean-eval-submissions https://github.com/leanprover/lean-eval-submissions
c lean-eval-bench       https://github.com/leanprover/lean-eval
c mcb-minif2f-6provers  https://github.com/MCB-SMART-BOY/minif2f
c agenticsnz-unsorry    https://github.com/agenticsnz/unsorry
c aristotle-putnam25    https://github.com/nanand2/aristotle_putnam25
c plby-lean-proofs      https://github.com/plby/lean-proofs
c apollo-dspv2-o3       https://github.com/handler85/apollo_dspv2_splitprover
c aleph-prover-proofs   https://github.com/logical-intelligence/proofs
c axiomprover-fc        https://github.com/AxiomMath/gdm-formal-conjectures
c archon-firstproof     https://github.com/frenzymath/Archon-FirstProof-Results
c itpeval              https://github.com/lean-dojo/ITPEval
c jayyhk-erdos-lean     https://github.com/Jayyhk/erdos-lean
