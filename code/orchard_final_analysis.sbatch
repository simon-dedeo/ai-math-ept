#!/bin/bash
#SBATCH --job-name=ept-final
#SBATCH --partition=general
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=/home/sdedeo/ai_math_ept_orchard/slurm-%j.out

set -euo pipefail

WORK=/home/sdedeo/ai_math_ept_orchard
cd "$WORK"

if [[ ! -x venv/bin/python ]]; then
  python3 -m venv venv
  venv/bin/pip install --quiet --disable-pip-version-check \
    numpy==2.2.6 pandas==2.2.3 scipy==1.15.3 matplotlib==3.10.3
fi

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"
venv/bin/python -u code/final_synthesis.py --root "$WORK" --boot 10000 --perm 10000

tar -czf final_synthesis_outputs.tar.gz results/final_synthesis report/final/figures
sha256sum final_synthesis_outputs.tar.gz > final_synthesis_outputs.sha256
