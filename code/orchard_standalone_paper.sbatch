#!/bin/bash
#SBATCH --job-name=ept-standalone
#SBATCH --partition=general
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/home/sdedeo/ai_math_ept_orchard/slurm-standalone-%j.out

set -euo pipefail
WORK=/home/sdedeo/ai_math_ept_orchard
cd "$WORK"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
nice -n 5 venv/bin/python -u code/standalone_paper_analysis.py \
  --root "$WORK" --boot 20000 --seed 20260801
tar -czf standalone_paper_outputs.tar.gz \
  results/standalone_paper report/standalone/figures
sha256sum standalone_paper_outputs.tar.gz > standalone_paper_outputs.sha256
