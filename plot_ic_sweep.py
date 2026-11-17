"""Peak infectious % and peak time vs. initial infected %, by lambda.

Reads results_ic/lambda_<L>/init_<P>/seed_<n>.csv (from run_ic_sweep.sbatch).
Per run: peak = max of the raw infectious fraction; peak time = when it occurs.
A run "takes off" if its infectious peak reaches TAKEOFF_PCT of the population
(runs that stall at a low plateau never do). Time to take-off is the first time
the infectious fraction crosses that level. Across seeds we report means over
all runs and over take-off runs only (peak/take-off times need a take-off).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


TAKEOFF_PCT = 5.0  # infectious peak (% of population) that counts as an outbreak


def summarize_run(
    csv_file: Path, population: int | None = None, takeoff_pct: float = TAKEOFF_PCT
) -> dict:
    """population defaults to s+e+i+r at t=0, so runs of different sizes mix safely."""
    time, i = [], []
    with csv_file.open(newline="") as file:
        for row in csv.DictReader(file):
            time.append(float(row["time"]))
            i.append(float(row["i"]))
            if population is None:
                population = round(sum(float(row[k]) for k in "seir"))
    i = np.array(i)
    k = int(i.argmax())
    peak_pct = 100.0 * i[k] / population
    crossed = np.nonzero(100.0 * i / population >= takeoff_pct)[0]
    return {
        "peak_pct": peak_pct,
        "peak_time": time[k],
        "extinct": bool(peak_pct < takeoff_pct),  # i.e. no take-off
        "takeoff_time": time[int(crossed[0])] if len(crossed) else float("nan"),
    }


def load(results_dir: Path, population: int) -> dict:
    data: dict[float, dict[float, list[dict]]] = {}
    for file in results_dir.glob("lambda_*/init_*/seed_*.csv"):
        lam = float(file.parent.parent.name.removeprefix("lambda_"))
        pct = float(file.parent.name.removeprefix("init_"))
        data.setdefault(lam, {}).setdefault(pct, []).append(
            summarize_run(file, population)
        )
    return {lam: dict(sorted(d.items())) for lam, d in sorted(data.items())}


def stats(values: list[float]) -> tuple[float, float]:
    if not values:
        return np.nan, np.nan
    arr = np.array(values)
    sem = arr.std(ddof=1) / np.sqrt(len(arr)) if len(arr) > 1 else np.nan
    return arr.mean(), sem


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results_ic"))
    parser.add_argument("--output-dir", type=Path, default=Path("ic_sweep_plots"))
    parser.add_argument("--population", type=int, default=7700)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    data = load(args.results_dir, args.population)
    if not data:
        raise SystemExit(f"No results found under {args.results_dir}")

    # Summary table (one row per lambda x initial %).
    with (args.output_dir / "summary.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["lambda", "init_pct", "n_runs", "extinct_frac", "peak_pct_all",
             "peak_pct_nonextinct", "peak_time_nonextinct", "takeoff_time"]
        )
        for lam, by_pct in data.items():
            for pct, runs in by_pct.items():
                live = [r for r in runs if not r["extinct"]]
                writer.writerow([
                    lam, pct, len(runs),
                    sum(r["extinct"] for r in runs) / len(runs),
                    stats([r["peak_pct"] for r in runs])[0],
                    stats([r["peak_pct"] for r in live])[0],
                    stats([r["peak_time"] for r in live])[0],
                    stats([r["takeoff_time"] for r in live])[0],
                ])

    panels = [
        ("peak_pct", False, "Peak infectious (% of population), all runs"),
        ("peak_pct", True, "Peak infectious (%), take-off runs"),
        ("peak_time", True, "Peak time (hours), take-off runs"),
        ("extinct", False, "Fraction of runs with no take-off"),
        ("takeoff_time", True, "Time to take-off (hours), take-off runs"),
    ]
    colormap = plt.get_cmap("viridis")
    figure, axes = plt.subplots(2, 3, figsize=(17, 8), sharex=True)
    for axis, (key, live_only, label) in zip(axes.ravel(), panels):
        for index, (lam, by_pct) in enumerate(data.items()):
            xs, ys, errs = [], [], []
            for pct, runs in by_pct.items():
                runs = [r for r in runs if not r["extinct"]] if live_only else runs
                mean, sem = stats([float(r[key]) for r in runs])
                xs.append(pct); ys.append(mean); errs.append(sem)
            axis.errorbar(
                xs, ys, yerr=errs, marker="o", capsize=3,
                color=colormap(index / max(len(data) - 1, 1)), label=f"{lam:g}",
            )
        axis.set_ylabel(label)
        axis.grid(alpha=0.3)
    axes[1, 2].set_visible(False)
    for axis in axes[1, :2]:
        axis.set_xlabel("Initially infected (% of population)")
    axes[0, 0].legend(title=r"$\lambda$", fontsize=8)
    figure.suptitle("Mean across seeds (error bars: SEM)")
    figure.tight_layout()
    out = args.output_dir / "ic_sweep.png"
    figure.savefig(out, dpi=150)
    print(f"Wrote {out} and {args.output_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
