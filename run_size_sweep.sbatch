#!/bin/bash
# Population-size sweep: 5 sizes x 3 initial levels x 10 seeds = 150 runs.
# Buildings scale with population (77 people per building, as in the 7700 / 100 baseline)
# so local crowding is held fixed and only system size changes.
# Task id 0..149 -> size index = id / 30, init index = (id / 10) % 3, seed = id % 10 + 1.
# Submit from the repo root:  mkdir -p logs results_size && sbatch run_size_sweep.sbatch
# Then plot:  python plot_size_sweep.py
#SBATCH --job-name=size_sweep
#SBATCH --partition=main
#SBATCH --time=08:00:00               # largest size is 4x baseline; time one 30800 task and adjust
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --array=0-149%30              # at most 30 tasks at once
#SBATCH --output=logs/%x_%A_%a.out
#SBATCH --account=ua
#SBATCH --qos=main

set -euo pipefail

module load python                    # set to the version that worked, e.g. python/3.11
source .venv/bin/activate

LAMBDA=3.0                            # lambda showed no effect over 0.5-20
POPULATIONS=(1925 3850 7700 15400 30800)   # 0.25x, 0.5x, 1x, 2x, 4x baseline
PERCENTS=(4 5 10)                     # initial infected, % of population
PEOPLE_PER_BUILDING=77
N_SEEDS=10

TASK=$SLURM_ARRAY_TASK_ID
SEED=$((TASK % N_SEEDS + 1))
PERCENT=${PERCENTS[$(( (TASK / N_SEEDS) % ${#PERCENTS[@]} ))]}
POPULATION=${POPULATIONS[$(( TASK / (N_SEEDS * ${#PERCENTS[@]}) ))]}
NUM_BUILDINGS=$(( POPULATION / PEOPLE_PER_BUILDING ))
NUM_INFECTED=$(python -c "print(round($POPULATION * $PERCENT / 100))")

OUT=results_size/pop_${POPULATION}/init_${PERCENT}
mkdir -p "$OUT"

python simulation_sun_clock.py \
  --num-buildings "$NUM_BUILDINGS" \
  --population "$POPULATION" \
  --num-infected "$NUM_INFECTED" \
  --duration 5000 \
  --sample-interval 1 \
  --lambda-logit "$LAMBDA" \
  --seed "$SEED" \
  --output-file "$OUT/seed_${SEED}.csv"
