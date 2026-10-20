from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from simulation import CandyLand
from simulation_sun_clock import CandyLand as SunClockCandyLand

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PLOT = PROJECT_DIR / "simulation_plots.png"
DEFAULT_DESCRIPTION = PROJECT_DIR / "simulation_description.txt"
R_COLUMNS = ("r_mean_cases", "r_household_cases", "r_community_cases")


def run_simulation(
    num_buildings: int,
    population: int,
    avg_income: float,
    std_income: float,
    num_infected: int,
    duration: float,
    sample_interval: float,
    seed: int,
    output_file: Path,
    r_bin_hours: float = 24.0,
    lambda_logit: float | None = None,
) -> object:
    model_class = (
        SunClockCandyLand
        if output_file.name == "simulation_sun_clock.csv"
        else CandyLand
    )
    model_arguments = (
        num_buildings,
        population,
        avg_income,
        std_income,
        num_infected,
        seed,
    )
    if model_class is SunClockCandyLand:
        model = model_class(
            *model_arguments, PROJECT_DIR / "sun_clock_leave_probability.csv"
        )
    else:
        model = model_class(*model_arguments)
    if lambda_logit is not None:
        # Overrides the model's default logit sensitivity (read only at run time).
        model.lambda_logit = lambda_logit
    print(f"lambda_logit={model.lambda_logit}")
    start = time.perf_counter()
    model.run(duration, sample_interval, str(output_file))
    stop = time.perf_counter()
    model.validate()
    if hasattr(model, "reproduction_summary"):
        # Appends the reproduction-number columns to the simulation CSV.
        model.reproduction_summary(r_bin_hours, str(output_file))
    counts = model.health_counts()

    print(f"simulation_seconds={stop - start:.6f}")
    print(f"final_counts={counts[0]},{counts[1]},{counts[2]},{counts[3]}")
    print(f"final_complying={model.num_compliant()}")
    if hasattr(model, "num_interactions_total"):
        print(f"total_interactions={model.num_interactions_total()}")
        print(f"infections_from_interactions={model.num_infections_from_interactions()}")
        print(f"infections_from_households={model.num_infections_from_households()}")
    return model


def read_history(csv_file: Path) -> dict[str, list]:
    history: dict[str, list] = {
        "time": [],
        "s": [],
        "e": [],
        "i": [],
        "r": [],
        "mandate": [],
        "complying": [],
        "away_percent": [],
        "floor_complying_percent": [],
    }
    with csv_file.open(newline="") as file:
        reader = csv.DictReader(file)
        has_reproduction = all(key in (reader.fieldnames or []) for key in R_COLUMNS)
        if has_reproduction:
            for key in R_COLUMNS:
                history[key] = []
        for row in reader:
            history["time"].append(float(row["time"]))
            for key in ("s", "e", "i", "r", "mandate", "complying"):
                history[key].append(int(row[key]))
            history["away_percent"].append(float(row["away_percent"]))
            history["floor_complying_percent"].append(
                float(row["floor_complying_percent"])
            )
            if has_reproduction:
                for key in R_COLUMNS:
                    history[key].append(float(row[key]))
    return history


def analyze_history(history: dict[str, list]) -> None:
    population = sum(history[key][0] for key in ("s", "e", "i", "r"))
    for values in zip(history["s"], history["e"], history["i"], history["r"]):
        if sum(values) != population:
            raise RuntimeError("Population was not conserved in the simulation output")

    print(f"population={population}")
    print(f"peak_exposed={max(history['e'])}")
    print(f"peak_infectious={max(history['i'])}")
    print(f"peak_mandate={max(history['mandate'])}")
    print(f"final_complying={history['complying'][-1]}")
    print(f"min_floor_complying_percent={min(history['floor_complying_percent']):.2f}")


def write_description(
    output_file: Path,
    num_buildings: int,
    population: int,
    avg_income: float,
    std_income: float,
    num_infected: int,
    duration: float,
    sample_interval: float,
    seed: int,
    lambda_logit: float,
) -> None:
    content = f"""Date ran: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Parameters:
  --population      {population}
  --num-buildings   {num_buildings}
  --num-infected    {num_infected}
  --duration        {duration}
  --seed            {seed}
  --avg-income      {avg_income}
  --std-income      {std_income}
  --sample-interval {sample_interval}
  --lambda-logit    {lambda_logit}

Comments:
  (Write your notes here. What did you change? What did you notice?)
"""
    output_file.write_text(content)
    print(f"Wrote description file: {output_file}")


def plot_history(
    history: dict[str, list], output_file: Path, reproduction_file: Path
) -> None:
    has_reproduction = "r_mean_cases" in history
    figure = plt.figure(figsize=(15, 8))
    grid = figure.add_gridspec(2, 3)
    axes = []
    for index in range(6):
        axes.append(
            figure.add_subplot(
                grid[index // 3, index % 3], sharex=axes[0] if axes else None
            )
        )
    times = history["time"]
    plots = (
        ("s", "Susceptible", "royalblue"),
        ("e", "Exposed", "darkorange"),
        ("i", "Infectious", "crimson"),
        ("r", "Recovered", "seagreen"),
        ("mandate", "Mandate Level", "purple"),
        ("floor_complying_percent", "Complying on Public Floor (%)", "teal"),
    )

    for axis, (key, title, color) in zip(axes, plots):
        if key == "mandate":
            axis.step(times, history[key], where="post", color=color)
            axis.set_yticks(range(4))
        else:
            axis.plot(times, history[key], color=color)
        axis.ticklabel_format(style="plain", axis="y", useOffset=False)
        axis.set_title(title)
        axis.set_xlabel("Time (hours)")
        axis.set_ylabel(title)
        axis.grid(alpha=0.3)

    figure.suptitle("Candy Land Epidemic Simulation")
    figure.tight_layout()
    figure.savefig(output_file, dpi=150)
    print(f"Wrote plot: {output_file}")

    if has_reproduction:
        # Each point is the mean secondary cases of infectors who became
        # infectious in that time bin, so it is a cohort R rather than a
        # point-in-time value. Bins with no finished infectors are NaN (gaps).
        r_figure, axis = plt.subplots(figsize=(10, 5))
        axis.step(
            times,
            history["r_mean_cases"],
            where="post",
            color="black",
            label="Total R",
        )
        axis.step(
            times,
            history["r_household_cases"],
            where="post",
            color="darkorange",
            label="Household",
        )
        axis.step(
            times,
            history["r_community_cases"],
            where="post",
            color="royalblue",
            label="Community (public floor)",
        )
        axis.axhline(1.0, color="gray", linestyle="--", linewidth=1)
        axis.set_title("Reproduction Number by Infectious Onset Time")
        axis.set_xlabel("Onset time (hours)")
        axis.set_ylabel("Mean secondary cases")
        axis.legend()
        axis.grid(alpha=0.3)
        r_figure.tight_layout()
        r_figure.savefig(reproduction_file, dpi=150)
        print(f"Wrote plot: {reproduction_file}")

    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run and plot the Candy Land epidemic simulation"
    )
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--num-buildings", type=int, default=10_000)
    parser.add_argument("--population", type=int, default=1_000_000)
    parser.add_argument("--avg-income", type=float, default=100_000)
    parser.add_argument("--std-income", type=float, default=10_000)
    parser.add_argument("--num-infected", type=int, default=60_000)
    parser.add_argument("--duration", type=float, default=1_008)
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--lambda-logit",
        type=float,
        default=None,
        help="Logit sensitivity for the compliance choice (default: model's value)",
    )
    parser.add_argument(
        "--r-bin-hours", type=float, default=24.0, help="Onset-time bin width for R"
    )
    parser.add_argument("--plot", type=Path, default=DEFAULT_PLOT)
    parser.add_argument(
        "--r-plot",
        type=Path,
        default=None,
        help="Output for the reproduction-number figure (default: <plot>_reproduction.png)",
    )
    parser.add_argument("--description", type=Path, default=DEFAULT_DESCRIPTION)
    args = parser.parse_args()

    model = run_simulation(
        args.num_buildings,
        args.population,
        args.avg_income,
        args.std_income,
        args.num_infected,
        args.duration,
        args.sample_interval,
        args.seed,
        args.csv,
        args.r_bin_hours,
        args.lambda_logit,
    )
    history = read_history(args.csv)
    analyze_history(history)
    write_description(
        args.description,
        args.num_buildings,
        args.population,
        args.avg_income,
        args.std_income,
        args.num_infected,
        args.duration,
        args.sample_interval,
        args.seed,
        model.lambda_logit,
    )
    r_plot = args.r_plot or args.plot.with_name(
        f"{args.plot.stem}_reproduction{args.plot.suffix}"
    )
    plot_history(history, args.plot, r_plot)


if __name__ == "__main__":
    main()
