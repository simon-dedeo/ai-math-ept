#!/bin/bash
#SBATCH --job-name=ept-belief
#SBATCH --partition=general
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=/home/sdedeo/ai_math_ept_orchard/slurm-belief-r32-%j.out

set -euo pipefail
WORK=/home/sdedeo/ai_math_ept_orchard
cd "$WORK"
export NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
venv/bin/pip install --quiet --disable-pip-version-check numba==0.61.2
venv/bin/python -u code/paired_belief_term0.py --root "$WORK" --runs 32 --sweeps 10 \
  --tag paired_belief_term0_r32
tar -czf paired_belief_term0_r32_outputs.tar.gz \
  results/final_synthesis/paired_belief_term0_r32.csv \
  results/final_synthesis/paired_belief_term0_r32.json \
  results/final_synthesis/paired_belief_term0_r32.jsonl
sha256sum paired_belief_term0_r32_outputs.tar.gz > paired_belief_term0_r32_outputs.sha256
