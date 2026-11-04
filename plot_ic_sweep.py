"""Peak infectious % and peak time vs. initial infected %, by lambda.

Reads results_ic/lambda_<L>/init_<P>/seed_<n>.csv (from run_ic_sweep.sbatch).
Per run: peak = max of the raw infectious fraction; peak time = when it occurs.
A run is "extinct" if its peak infectious count never exceeds the initially
seeded count (infectious + exposed at t=0), i.e. no transmission-driven growth.
Across seeds we report means over all runs and over non-extinct runs only
(peak time is only meaningful for non-extinct runs).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def summarize_run(csv_file: Path, population: int) -> dict:
    time, i, seeded = [], [], None
    with csv_file.open(newline="") as file:
        for row in csv.DictReader(file):
            time.append(float(row["time"]))
            i.append(float(row["i"]))
            if seeded is None:
                seeded = float(row["i"]) + float(row["e"])
    i = np.array(i)
    k = int(i.argmax())
    return {
        "peak_pct": 100.0 * i[k] / population,
        "peak_time": time[k],
        "extinct": bool(i[k] <= seeded),
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
             "peak_pct_nonextinct", "peak_time_nonextinct"]
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
                ])

    panels = [
        ("peak_pct", False, "Peak infectious (% of population), all runs"),
        ("peak_pct", True, "Peak infectious (%), non-extinct runs"),
        ("peak_time", True, "Peak time (hours), non-extinct runs"),
        ("extinct", False, "Fraction of runs with no outbreak"),
    ]
    colormap = plt.get_cmap("viridis")
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
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
    for axis in axes[1]:
        axis.set_xlabel("Initially infected (% of population)")
    axes[0, 0].legend(title=r"$\lambda$", fontsize=8)
    figure.suptitle("Mean across seeds (error bars: SEM)")
    figure.tight_layout()
    out = args.output_dir / "ic_sweep.png"
    figure.savefig(out, dpi=150)
    print(f"Wrote {out} and {args.output_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
