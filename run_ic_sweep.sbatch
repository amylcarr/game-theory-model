#!/bin/bash
# Initial-condition sweep: 5 lambdas x 5 initial-infected levels x 10 seeds = 250 runs.
# Task id 0..249 -> lambda index = id / 50, init index = (id / 10) % 5, seed = id % 10 + 1.
# Submit from the repo root:  mkdir -p logs results_ic && sbatch run_ic_sweep.sbatch
#SBATCH --job-name=ic_sweep
#SBATCH --partition=main
#SBATCH --time=02:00:00               # adjust after timing one task
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --array=0-249%30              # at most 30 tasks at once
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --account=ua
#SBATCH --qos=main

set -euo pipefail

# module load python                  # uncomment / adjust for UA HPC
source .venv/bin/activate

POPULATION=7700
LAMBDAS=(2.5 2.75 3.0 3.25 3.5)
PERCENTS=(1 2 5 10 20)                # initial infected, % of population
N_SEEDS=10

TASK=$SLURM_ARRAY_TASK_ID
SEED=$((TASK % N_SEEDS + 1))
PERCENT=${PERCENTS[$(( (TASK / N_SEEDS) % ${#PERCENTS[@]} ))]}
LAMBDA=${LAMBDAS[$(( TASK / (N_SEEDS * ${#PERCENTS[@]}) ))]}
NUM_INFECTED=$(( POPULATION * PERCENT / 100 ))

OUT=results_ic/lambda_${LAMBDA}/init_${PERCENT}
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
