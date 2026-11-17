"""Compare stalled vs. take-off runs for one (population, initial %) cell.

Reads results_size/pop_<N>/init_<P>/seed_*.csv. A run "takes off" if its infectious
peak reaches --takeoff-pct of the population (default 5%); otherwise it is "stalled".
Prints t=0 composition, early infectious counts, time to take-off, and the effective
reproduction number R (mean secondary cases per infectious episode, by onset day,
from the r_* columns the simulation appends) in a few time windows. Plots infectious,
exposed, floor compliance and R over the first --window hours.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CHECK_TIMES = (0, 24, 72, 168, 336)
R_WINDOWS = ((0, 100), (100, 300), (300, 500))
BIN_HOURS = 24.0  # simulation's --r-bin-hours default


def read(csv_file: Path) -> dict[str, np.ndarray]:
    with csv_file.open(newline="") as file:
        rows = list(csv.DictReader(file))
    keys = ("time", "s", "e", "i", "r", "floor_complying_percent",
            "r_mean_cases", "r_onset_finished")
    return {k: np.array([float(r[k]) for r in rows]) for k in keys}


def r_by_bin(d: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One (bin start time, R, finished-episode count) per onset bin."""
    bins = np.floor(d["time"] / BIN_HOURS).astype(int)
    _, first = np.unique(bins, return_index=True)
    return bins[first] * BIN_HOURS, d["r_mean_cases"][first], d["r_onset_finished"][first]


def window_r(starts, r, count, lo, hi) -> float:
    """Episode-weighted mean R over onset bins starting in [lo, hi)."""
    m = (starts >= lo) & (starts < hi) & ~np.isnan(r) & (count > 0)
    return float((r[m] * count[m]).sum() / count[m].sum()) if m.any() else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results_size"))
    parser.add_argument("--population", type=int, default=30800)
    parser.add_argument("--init", default="4")
    parser.add_argument("--takeoff-pct", type=float, default=5.0)
    parser.add_argument("--window", type=float, default=500.0)
    parser.add_argument("--output", type=Path, default=Path("compare_runs.png"))
    args = parser.parse_args()

    folder = args.results_dir / f"pop_{args.population}" / f"init_{args.init}"
    files = sorted(folder.glob("seed_*.csv"), key=lambda f: int(f.stem.split("_")[1]))
    if not files:
        raise SystemExit(f"No runs in {folder}")

    runs = {}
    print(f"{'seed':>4} {'status':>9} {'peak_%':>7} {'t_takeoff':>9} | "
          + " ".join(f"i@{t}h".rjust(7) for t in CHECK_TIMES) + " | "
          + " ".join(f"R{lo}-{hi}h".rjust(9) for lo, hi in R_WINDOWS))
    for file in files:
        d = read(file)
        pop = round(d["s"][0] + d["e"][0] + d["i"][0] + d["r"][0])
        pct = 100.0 * d["i"] / pop
        crossed = np.nonzero(pct >= args.takeoff_pct)[0]
        took_off = len(crossed) > 0
        t_off = d["time"][crossed[0]] if took_off else float("nan")
        seed = int(file.stem.split("_")[1])
        starts, r, count = r_by_bin(d)
        runs[seed] = (d, took_off, (starts, r, count))
        early = [d["i"][np.searchsorted(d["time"], t)] for t in CHECK_TIMES]
        rw = [window_r(starts, r, count, lo, hi) for lo, hi in R_WINDOWS]
        print(f"{seed:>4} {'take-off' if took_off else 'stalled':>9} {pct.max():>7.2f} "
              f"{t_off:>9.0f} | " + " ".join(f"{v:>7.0f}" for v in early) + " | "
              + " ".join(f"{v:>9.3f}" for v in rw))

    for name, flag in (("stalled", False), ("take-off", True)):
        group = [v for v in runs.values() if v[1] == flag]
        if group:
            rw = [np.nanmean([window_r(*g[2], lo, hi) for g in group]) for lo, hi in R_WINDOWS]
            print(f"{name}: n={len(group)}  mean R by window "
                  + ", ".join(f"{lo}-{hi}h: {v:.3f}" for (lo, hi), v in zip(R_WINDOWS, rw)))

    figure, axes = plt.subplots(1, 4, figsize=(20, 4))
    for key, axis, label in zip(("i", "e", "floor_complying_percent"), axes,
                                ("Infectious", "Exposed", "Floor complying (%)")):
        for d, took_off, _ in runs.values():
            m = d["time"] <= args.window
            axis.plot(d["time"][m], d[key][m], color="tab:blue" if took_off else "crimson",
                      linestyle="-" if took_off else "--", alpha=0.7)
        axis.set_ylabel(label)
    for _, took_off, (starts, r, count) in runs.values():
        m = starts <= args.window
        axes[3].plot(starts[m], r[m], marker=".", color="tab:blue" if took_off else "crimson",
                     linestyle="-" if took_off else "--", alpha=0.7)
    axes[3].axhline(1.0, color="black", linewidth=0.8)
    axes[3].set_ylabel("R (secondary cases per episode, by onset day)")
    for axis in axes:
        axis.set_xlabel("Time (hours)")
        axis.grid(alpha=0.3)
    axes[0].plot([], [], "--", color="crimson", label="stalled")
    axes[0].plot([], [], "-", color="tab:blue", label="take-off")
    axes[0].legend()
    figure.suptitle(f"N={args.population}, {args.init}% initially infected")
    figure.tight_layout()
    figure.savefig(args.output, dpi=150)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
