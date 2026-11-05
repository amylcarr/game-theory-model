"""Population-size sweep: peak infectious %, peak time and extinction vs. population.

Reads results_size/pop_<N>/init_<P>/seed_<n>.csv (from run_size_sweep.sbatch).
One line per initial-infected %. Run definitions match plot_ic_sweep.py.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from plot_ic_sweep import stats, summarize_run


def load(results_dir: Path) -> dict:
    data: dict[float, dict[int, list[dict]]] = {}
    for file in results_dir.glob("pop_*/init_*/seed_*.csv"):
        pop = int(file.parent.parent.name.removeprefix("pop_"))
        pct = float(file.parent.name.removeprefix("init_"))
        data.setdefault(pct, {}).setdefault(pop, []).append(
            summarize_run(file, pop)
        )
    return {p: dict(sorted(d.items())) for p, d in sorted(data.items())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results_size"))
    parser.add_argument("--output-dir", type=Path, default=Path("size_sweep_plots"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    data = load(args.results_dir)
    if not data:
        raise SystemExit(f"No results found under {args.results_dir}")

    with (args.output_dir / "summary.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["init_pct", "population", "n_runs", "extinct_frac",
                         "peak_pct_all", "peak_pct_nonextinct", "peak_time_nonextinct"])
        for pct, by_pop in data.items():
            for pop, runs in by_pop.items():
                live = [r for r in runs if not r["extinct"]]
                writer.writerow([
                    pct, pop, len(runs),
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
        for index, (pct, by_pop) in enumerate(data.items()):
            xs, ys, errs = [], [], []
            for pop, runs in by_pop.items():
                runs = [r for r in runs if not r["extinct"]] if live_only else runs
                mean, sem = stats([float(r[key]) for r in runs])
                xs.append(pop); ys.append(mean); errs.append(sem)
            axis.errorbar(xs, ys, yerr=errs, marker="o", capsize=3,
                          color=colormap(index / max(len(data) - 1, 1)),
                          label=f"{pct:g}%")
        axis.set_xscale("log")
        axis.set_ylabel(label)
        axis.grid(alpha=0.3)
    for axis in axes[1]:
        axis.set_xlabel("Population size (log scale)")
    axes[0, 0].legend(title="Initially infected", fontsize=8)
    figure.suptitle("Mean across seeds (error bars: SEM)")
    figure.tight_layout()
    out = args.output_dir / "size_sweep.png"
    figure.savefig(out, dpi=150)
    print(f"Wrote {out} and {args.output_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
