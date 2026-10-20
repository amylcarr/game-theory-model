#!/bin/bash
# Lambda sweep: 11 values (2.5..3.5 step 0.1) x 10 seeds = 110 independent runs.
# Task id 0..109 -> lambda index = id / 10, seed = id % 10 + 1.
# Submit from the repo root:  mkdir -p logs results && sbatch run_sweep.sbatch
#SBATCH --job-name=lambda_sweep
#SBATCH --partition=main
#SBATCH --time=02:00:00               # ~17 s per 200 sim-hours locally => ~7+ min expected; adjust after one task
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --array=0-109%30              # at most 30 tasks at once
#SBATCH --output=logs/%x_%A_%a.out

set -euo pipefail

# module load python                  # uncomment / adjust for UA HPC
source .venv/bin/activate

TASK=$SLURM_ARRAY_TASK_ID
N_SEEDS=10
LAMBDA_INDEX=$((TASK / N_SEEDS))
SEED=$((TASK % N_SEEDS + 1))
# Integer arithmetic avoids floating-point drift in the lambda labels.
LAMBDA=$(python -c "print(f'{2.5 + 0.1 * $LAMBDA_INDEX:.1f}')")

OUT=results/lambda_${LAMBDA}
mkdir -p "$OUT"

python simulation_sun_clock.py \
  --num-buildings 100 \
  --population 7700 \
  --num-infected 100 \
  --duration 5000 \
  --lambda-logit "$LAMBDA" \
  --seed "$SEED" \
  --output-file "$OUT/seed_${SEED}.csv"
