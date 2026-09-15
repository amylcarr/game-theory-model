from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from simulation import CandyLand

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PLOT = PROJECT_DIR / "simulation_plots.png"
DEFAULT_DESCRIPTION = PROJECT_DIR / "simulation_description.txt"


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
) -> None:
    model = CandyLand(
        num_buildings,
        population,
        avg_income,
        std_income,
        num_infected,
        seed,
    )
    start = time.perf_counter()
    model.run(duration, sample_interval, str(output_file))
    stop = time.perf_counter()
    model.validate()
    counts = model.health_counts()

    print(f"simulation_seconds={stop - start:.6f}")
    print(f"final_counts={counts[0]},{counts[1]},{counts[2]},{counts[3]}")
    print(f"final_complying={model.num_compliant()}")


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
    }
    with csv_file.open(newline="") as file:
        for row in csv.DictReader(file):
            history["time"].append(float(row["time"]))
            for key in ("s", "e", "i", "r", "mandate", "complying"):
                history[key].append(int(row[key]))
            history["away_percent"].append(float(row["away_percent"]))
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
    print(f"peak_away_percent={max(history['away_percent']):.2f}")


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

Comments:
  (Write your notes here. What did you change? What did you notice?)
"""
    output_file.write_text(content)
    print(f"Wrote description file: {output_file}")


def plot_history(history: dict[str, list], output_file: Path) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(15, 8), sharex=True)
    times = history["time"]
    plots = (
        ("s", "Susceptible", "royalblue"),
        ("e", "Exposed", "darkorange"),
        ("i", "Infectious", "crimson"),
        ("r", "Recovered", "seagreen"),
        ("mandate", "Mandate Level", "purple"),
        ("away_percent", "Away from Home (%)", "teal"),
    )

    for axis, (key, title, color) in zip(axes.flat, plots):
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
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run and plot the Candy Land epidemic simulation"
    )
    parser.add_argument("csv", type=Path)
    parser.add_argument("--num-buildings", type=int, default=10_000)
    parser.add_argument("--population", type=int, default=1_000_000)
    parser.add_argument("--avg-income", type=float, default=100_000)
    parser.add_argument("--std-income", type=float, default=10_000)
    parser.add_argument("--num-infected", type=int, default=60_000)
    parser.add_argument("--duration", type=float, default=1_008)
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--plot", type=Path, default=DEFAULT_PLOT)
    parser.add_argument("--description", type=Path, default=DEFAULT_DESCRIPTION)
    args = parser.parse_args()

    run_simulation(
        args.num_buildings,
        args.population,
        args.avg_income,
        args.std_income,
        args.num_infected,
        args.duration,
        args.sample_interval,
        args.seed,
        args.csv,
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
    )
    plot_history(history, args.plot)


if __name__ == "__main__":
    main()
