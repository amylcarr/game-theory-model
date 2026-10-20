"""Plot disease dynamics from the lambda sweep written by run_sweep.sbatch.

Expects results/lambda_<value>/seed_<n>.csv. Draws one panel per lambda with
every seed as a faint line and the across-seed mean as a bold line, plus a
summary figure of the mean curves for all lambdas on shared axes.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless nodes; figures are saved, never shown
import matplotlib.pyplot as plt
import numpy as np

COMPARTMENTS = (
    ("s", "Susceptible"),
    ("e", "Exposed"),
    ("i", "Infectious"),
    ("r", "Recovered"),
)


def read_series(csv_file: Path, key: str) -> tuple[np.ndarray, np.ndarray]:
    times, values = [], []
    with csv_file.open(newline="") as file:
        for row in csv.DictReader(file):
            times.append(float(row["time"]))
            values.append(float(row[key]))
    return np.array(times), np.array(values)


def load_sweep(results_dir: Path, key: str) -> dict[float, tuple[np.ndarray, np.ndarray]]:
    """Returns {lambda: (times, runs)} with runs shaped (n_seeds, n_times)."""
    sweep = {}
    for lambda_dir in results_dir.glob("lambda_*"):
        match = re.fullmatch(r"lambda_(.+)", lambda_dir.name)
        files = sorted(lambda_dir.glob("seed_*.csv"))
        if not match or not files:
            continue
        times, runs = None, []
        for file in files:
            run_times, values = read_series(file, key)
            if times is None:
                times = run_times
            if len(run_times) != len(times):
                print(f"Skipping {file}: {len(run_times)} samples, expected {len(times)}")
                continue
            runs.append(values)
        sweep[float(match.group(1))] = (times, np.vstack(runs))
    return dict(sorted(sweep.items()))


def plot_per_lambda(results_dir: Path, key: str, label: str, output: Path) -> None:
    sweep = load_sweep(results_dir, key)
    if not sweep:
        raise SystemExit(f"No results found under {results_dir}")
    columns = 4
    rows = -(-len(sweep) // columns)
    figure, axes = plt.subplots(
        rows, columns, figsize=(4 * columns, 3 * rows), sharex=True, sharey=True
    )
    axes = np.atleast_1d(axes).ravel()
    for axis, (lam, (times, runs)) in zip(axes, sweep.items()):
        axis.plot(times, runs.T, color="gray", alpha=0.3, linewidth=0.7)
        axis.plot(times, runs.mean(axis=0), color="crimson", linewidth=1.8)
        axis.set_title(f"$\\lambda$ = {lam:.1f}  (n={len(runs)})")
        axis.grid(alpha=0.3)
    for axis in axes[len(sweep):]:
        axis.set_visible(False)
    figure.supxlabel("Time (hours)")
    figure.supylabel(label)
    figure.suptitle(f"{label}: all seeds (gray) and mean (red) by lambda")
    figure.tight_layout()
    figure.savefig(output, dpi=150)
    plt.close(figure)
    print(f"Wrote plot: {output}")


def plot_mean_by_lambda(results_dir: Path, output: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    colormap = plt.get_cmap("viridis")
    for axis, (key, label) in zip(axes.ravel(), COMPARTMENTS):
        sweep = load_sweep(results_dir, key)
        for index, (lam, (times, runs)) in enumerate(sweep.items()):
            axis.plot(
                times,
                runs.mean(axis=0),
                color=colormap(index / max(len(sweep) - 1, 1)),
                label=f"{lam:.1f}",
            )
        axis.set_title(label)
        axis.set_xlabel("Time (hours)")
        axis.set_ylabel(label)
        axis.grid(alpha=0.3)
    axes[0, 0].legend(title="$\\lambda$", fontsize=8, ncol=2)
    figure.suptitle("Mean across seeds by lambda")
    figure.tight_layout()
    figure.savefig(output, dpi=150)
    plt.close(figure)
    print(f"Wrote plot: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot the lambda sweep results")
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--output-dir", type=Path, default=Path("sweep_plots"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for key, label in COMPARTMENTS:
        plot_per_lambda(
            args.results_dir, key, label, args.output_dir / f"{key}_by_lambda.png"
        )
    plot_mean_by_lambda(args.results_dir, args.output_dir / "mean_by_lambda.png")


if __name__ == "__main__":
    main()
