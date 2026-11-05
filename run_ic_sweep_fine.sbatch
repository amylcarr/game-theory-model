#!/bin/bash
# Fine initial-infected sweep around the outbreak threshold (between 2% and 5%):
# 5 lambdas x 7 initial levels x 10 seeds = 350 runs.
# Task id 0..349 -> lambda index = id / 70, init index = (id / 10) % 7, seed = id % 10 + 1.
# Submit from the repo root:  mkdir -p logs results_ic_fine && sbatch run_ic_sweep_fine.sbatch
# Then plot:  python plot_ic_sweep.py --results-dir results_ic_fine --output-dir ic_sweep_fine_plots
#SBATCH --job-name=ic_fine
#SBATCH --partition=main
#SBATCH --time=02:00:00               # adjust after timing one task
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --array=0-349%30              # at most 30 tasks at once
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --account=ua
#SBATCH --qos=main

set -euo pipefail

module load python                    # set to the version that worked, e.g. python/3.11
source .venv/bin/activate

POPULATION=7700
LAMBDAS=(2.5 2.75 3.0 3.25 3.5)
PERCENTS=(2 2.5 3 3.5 4 4.5 5)        # initial infected, % of population
N_SEEDS=10

TASK=$SLURM_ARRAY_TASK_ID
SEED=$((TASK % N_SEEDS + 1))
INIT_INDEX=$(( (TASK / N_SEEDS) % ${#PERCENTS[@]} ))
LAMBDA=${LAMBDAS[$(( TASK / (N_SEEDS * ${#PERCENTS[@]}) ))]}
PERCENT=${PERCENTS[$INIT_INDEX]}
# Round to the nearest whole agent (percent may be fractional, so use python).
NUM_INFECTED=$(python -c "print(round($POPULATION * $PERCENT / 100))")

OUT=results_ic_fine/lambda_${LAMBDA}/init_${PERCENT}
mkdir -p "$OUT"

python simulation_sun_clock.py \
  --num-buildings 100 \
  --population "$POPULATION" \
  --num-infected "$NUM_INFECTED" \
  --duration 5000 \
  --sample-interval 1 \
  --lambda-logit "$LAMBDA" \
  --seed "$SEED" \
  --output-file "$OUT/seed_${SEED}.csv"
