"""Compare extinct vs. non-extinct runs for one (population, initial %) cell.

Reads results_size/pop_<N>/init_<P>/seed_*.csv. Prints t=0 composition and the
state at a few early times for every seed, then plots infectious count, exposed
count and floor-compliance over the first --window hours (extinct = dashed red,
outbreak = solid blue). Extinct means peak infectious <= seeded (i0 + e0).
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


def read(csv_file: Path) -> dict[str, np.ndarray]:
    with csv_file.open(newline="") as file:
        rows = list(csv.DictReader(file))
    keys = ("time", "s", "e", "i", "r", "complying", "floor_complying_percent")
    return {k: np.array([float(r[k]) for r in rows]) for k in keys}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results_size"))
    parser.add_argument("--population", type=int, default=30800)
    parser.add_argument("--init", default="4")
    parser.add_argument("--window", type=float, default=500.0)
    parser.add_argument("--output", type=Path, default=Path("compare_runs.png"))
    args = parser.parse_args()

    folder = args.results_dir / f"pop_{args.population}" / f"init_{args.init}"
    files = sorted(folder.glob("seed_*.csv"), key=lambda f: int(f.stem.split("_")[1]))
    if not files:
        raise SystemExit(f"No runs in {folder}")

    runs = {}
    print(f"{'seed':>4} {'status':>8} {'i0':>6} {'e0':>6} {'peak_i':>7} {'t_peak':>7} | "
          + " ".join(f"i@{t}h" .rjust(7) for t in CHECK_TIMES))
    for file in files:
        d = read(file)
        seeded = d["i"][0] + d["e"][0]
        k = int(d["i"].argmax())
        extinct = d["i"][k] <= seeded
        seed = int(file.stem.split("_")[1])
        runs[seed] = (d, extinct)
        early = [d["i"][np.searchsorted(d["time"], t)] for t in CHECK_TIMES]
        print(f"{seed:>4} {'extinct' if extinct else 'outbreak':>8} {d['i'][0]:>6.0f} "
              f"{d['e'][0]:>6.0f} {d['i'][k]:>7.0f} {d['time'][k]:>7.0f} | "
              + " ".join(f"{v:>7.0f}" for v in early))

    ext = [d for d, x in runs.values() if x]
    out = [d for d, x in runs.values() if not x]
    for name, group in (("extinct", ext), ("outbreak", out)):
        if group:
            print(f"{name}: n={len(group)}  mean i0={np.mean([g['i'][0] for g in group]):.0f}"
                  f"  mean e0={np.mean([g['e'][0] for g in group]):.0f}")

    panels = [("i", "Infectious"), ("e", "Exposed"),
              ("floor_complying_percent", "Floor complying (%)")]
    figure, axes = plt.subplots(1, 3, figsize=(15, 4))
    for axis, (key, label) in zip(axes, panels):
        for d, is_extinct in runs.values():
            mask = d["time"] <= args.window
            axis.plot(d["time"][mask], d[key][mask],
                      color="crimson" if is_extinct else "tab:blue",
                      linestyle="--" if is_extinct else "-", alpha=0.7)
        axis.set_xlabel("Time (hours)")
        axis.set_ylabel(label)
        axis.grid(alpha=0.3)
    axes[0].plot([], [], "--", color="crimson", label="extinct")
    axes[0].plot([], [], "-", color="tab:blue", label="outbreak")
    axes[0].legend()
    figure.suptitle(f"N={args.population}, {args.init}% initially infected")
    figure.tight_layout()
    figure.savefig(args.output, dpi=150)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
