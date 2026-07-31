#!/bin/bash
# run_overnight.sh — unattended continuation of the AI-math EPT project.
# Runs studies sequentially (polite: nice 15, single-threaded numba, one at a
# time) so the shared box stays usable for other jobs. Every stage appends to
# ~/ai_math_ept/results/OVERNIGHT.log and refreshes STATUS.md.

set -u
ROOT=$HOME/ai_math_ept
PY=$ROOT/venv/bin/python
LOG=$ROOT/results/OVERNIGHT.log
export NUMBA_NUM_THREADS=1
export PATH=$HOME/.elan/bin:$PATH
cd $ROOT

stamp() { date "+%Y-%m-%d %H:%M:%S"; }

status() {
cat > $ROOT/results/STATUS.md << EOF
# Overnight run status — updated $(stamp)

| stage | state | output |
|---|---|---|
| study2 comparison (AI vs human proofs) | $( [ -f results/study2_main/proofs.csv ] && echo DONE || echo pending ) | results/study2_main/ |
| study6 ETP provenance (who builds hubs) | $( [ -f results/study6/etp_provenance.json ] && echo DONE || echo pending ) | results/study6/ |
| study7 automation dose-response | $( [ -f results/study7/dose_response.json ] && echo DONE || echo pending ) | results/study7/ |
| study8 source-level cross-project | $( [ -f results/study8/source_graphs.csv ] && echo DONE || echo pending ) | results/study8/ |
| study9 matched-pair EPT sims | $( [ -f results/study9/matched_pairs.csv ] && echo DONE || echo pending ) | results/study9/ |

Tail of log:
\`\`\`
$(tail -25 $LOG 2>/dev/null)
\`\`\`
EOF
}

run() {   # run <name> <command...>
  local name=$1; shift
  echo "=== [$(stamp)] START $name" >> $LOG
  status
  nice -n 15 "$@" >> $LOG 2>&1
  local rc=$?
  echo "=== [$(stamp)] END $name (rc=$rc)" >> $LOG
  status
}

echo "###### overnight run started $(stamp)" >> $LOG

# 0. wait for any in-flight study2 comparison to finish (it was launched earlier)
for i in $(seq 1 240); do
  pgrep -f "compare_corpora.py" > /dev/null || break
  sleep 60
done

# 1. study 2 comparison (re-run only if it did not produce output)
if [ ! -f results/study2_main/proofs.csv ]; then
  run "study2_comparison" $PY code/compare_corpora.py \
    human_compfiles=networks/compfiles_human \
    dsv2_test=networks/dsv2_minif2f_test dsv2_valid=networks/dsv2_minif2f_valid \
    kimina=networks/kimina_minif2f seed_minif2f=networks/seed_minif2f \
    seed_imo25=networks/seed_imo2025 alphaproof_imo24=networks/alphaproof_imo2024 \
    alphaproof_nexus=networks/alphaproof_nexus aristotle_imo25=networks/aristotle_imo2025 \
    --out results/study2_main --parallel 4 --simulate
fi

# 2. ETP provenance: do human-proved implications become the load-bearing hubs?
run "study6_etp_provenance" $PY code/study6_etp_provenance.py

# 3. automation dose-response inside Mathlib
run "study7_dose_response" $PY code/study7_dose_response.py

# 4. source-level cross-project comparison (human vs AI layers)
run "study8_source_graphs" $PY code/study8_source_graphs.py

# 5. matched-pair EPT simulations (same theorem, different author)
run "study9_matched_pairs" $PY code/study9_matched_pairs.py

echo "###### overnight run finished $(stamp)" >> $LOG
status
