#!/bin/bash
# phase2.sh — runs after run_overnight.sh completes: the study-2 corpus
# comparison (skipped earlier due to a stray watchdog), then a final digest.
set -u
ROOT=$HOME/ai_math_ept
PY=$ROOT/venv/bin/python
LOG=$ROOT/results/OVERNIGHT.log
export NUMBA_NUM_THREADS=1
cd $ROOT
# wait for phase 1 to finish
for i in $(seq 1 720); do
  pgrep -f run_overnight.sh > /dev/null || break
  sleep 60
done
echo "=== [$(date "+%F %T")] START study2_comparison (phase2)" >> $LOG
nice -n 15 $PY code/compare_corpora.py \
  human_compfiles=networks/compfiles_human \
  dsv2_test=networks/dsv2_minif2f_test dsv2_valid=networks/dsv2_minif2f_valid \
  kimina=networks/kimina_minif2f seed_minif2f=networks/seed_minif2f \
  seed_imo25=networks/seed_imo2025 alphaproof_imo24=networks/alphaproof_imo2024 \
  alphaproof_nexus=networks/alphaproof_nexus aristotle_imo25=networks/aristotle_imo2025 \
  --out results/study2_main --parallel 3 >> $LOG 2>&1
echo "=== [$(date "+%F %T")] END study2_comparison rc=$? " >> $LOG
{
 echo "# Digest — $(date "+%F %T")"
 for f in results/study6/etp_provenance.json results/study7/dose_response.json \
          results/study8/source_graphs.csv results/study9/paired_tests.json \
          results/study2_main/summary.csv; do
   echo; echo "## $f"; [ -f "$f" ] && head -c 3000 "$f" || echo "(missing)"
 done
} > results/DIGEST.md
echo "=== [$(date "+%F %T")] phase2 complete" >> $LOG
