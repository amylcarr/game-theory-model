#!/bin/bash
# Wide lambda sweep: 6 lambdas x 4 initial levels x 10 seeds = 240 runs.
# Task id 0..239 -> lambda index = id / 40, init index = (id / 10) % 4, seed = id % 10 + 1.
# Initial levels bracket the outbreak threshold (~3-5%) plus one well above it.
# Submit from the repo root:  mkdir -p logs results_lambda_wide && sbatch run_lambda_wide.sbatch
# Then plot:  python plot_ic_sweep.py --results-dir results_lambda_wide --output-dir lambda_wide_plots
#SBATCH --job-name=lam_wide
#SBATCH --partition=main
#SBATCH --time=02:00:00               # adjust after timing one task
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --array=0-239%30              # at most 30 tasks at once
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --account=ua
#SBATCH --qos=main

set -euo pipefail

module load python                    # set to the version that worked, e.g. python/3.11
source .venv/bin/activate

POPULATION=7700
LAMBDAS=(0.5 1 2 5 10 20)
PERCENTS=(3 4 5 10)                   # initial infected, % of population
N_SEEDS=10

TASK=$SLURM_ARRAY_TASK_ID
SEED=$((TASK % N_SEEDS + 1))
PERCENT=${PERCENTS[$(( (TASK / N_SEEDS) % ${#PERCENTS[@]} ))]}
LAMBDA=${LAMBDAS[$(( TASK / (N_SEEDS * ${#PERCENTS[@]}) ))]}
NUM_INFECTED=$(python -c "print(round($POPULATION * $PERCENT / 100))")

OUT=results_lambda_wide/lambda_${LAMBDA}/init_${PERCENT}
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
