# 🍬 Candy-Land  🐍 Python Version  🐍

### Summer REU 2026 Project — University of Alabama

A research project developed as part of the University of Alabama's Summer 2026 Research Experiences for Undergraduates (REU) Program.

---

## What this project does

Candy-Land is a computer simulation of how an epidemic spreads through a population.  
When you run it, the program runs the model, prints a short summary, and opens a plot of the results.

---

## What you need to install first

You only need two things:


| Tool         | Why you need it                    |
| ------------ | ---------------------------------- |
| **Git**      | Downloads this project from GitHub |
| **Python 3** | Runs the simulation and plots      |


Pick your computer below and install anything you are missing.

### Mac

1. Open **Terminal** (press `Command + Space`, type `Terminal`, press Enter).
2. Install Apple’s developer tools (includes Git). Paste this and press Enter:

```bash
xcode-select --install
```

1. Install Python 3 from [python.org/downloads](https://www.python.org/downloads/)
  (or skip this if `python3 --version` already works in Terminal).



### Windows

**Use Windows Subsystem for Linux (WSL)**

1. Open **PowerShell as Administrator** and run:

```powershell
wsl --install
```

1. Restart your computer if asked, then open **Ubuntu** from the Start menu.
2. Inside Ubuntu, install the tools:

```bash
sudo apt update
sudo apt install -y git python3 python3-pip
```

---



## Step 1 — Download the project

> **Before cloning:** Make sure you have an SSH key set up with GitHub.  
> If you have never done this, follow GitHub’s guide: [Connecting to GitHub with SSH](https://docs.github.com/en/authentication/connecting-to-github-with-ssh).  
> Quick check — if this prints an email or key fingerprint (not an error), you are good:
>
> ```bash
> ssh -T git@github.com
> ```
>
> (Type `yes` if it asks whether to continue connecting. A message like “Hi username! You've successfully authenticated…” means it worked.)

Open Terminal (Mac) or Ubuntu / Git Bash (Windows).  
Copy and paste these commands one at a time:

```bash
cd ~
git clone git@github.com:chen-warren/Candy-Land.git
cd Candy-Land
```

That downloads the project into a folder called `Candy-Land` and moves you into it.

---



## Step 2 — Install Python packages

Still inside the `Candy-Land` folder, run:

```bash
python3 -m pip install -r requirements.txt
```

This installs `matplotlib` and `numpy`.

---



## Step 3 — Run the simulation

```bash
python3 plotting.py
```

This one command will:

1. Run the epidemic model
2. Print a short summary in the terminal
3. Write a description file with the date and parameters
4. Save and open a plot image

The first run may take a few minutes — that is normal.

### Files created when it finishes


| File                         | What it is                            |
| ---------------------------- | ------------------------------------- |
| `simulation.csv`             | Raw numbers from the simulation       |
| `simulation_plots.png`       | The plot image (also opens on screen) |
| `simulation_description.txt` | Date and parameters for this run      |


---



## Optional — run only the simulator

If you only want to run the model (no plots):

```bash
python3 simulation.py
```

Useful flags:

```bash
python3 simulation.py --duration=1 --output-file=none
python3 simulation.py --help
```

---



## Optional — change simulation settings

You can pass options to `plotting.py`. Examples:

```bash
# Smaller / faster test run
python3 plotting.py --population 10000 --num-buildings 100 --num-infected 600 --duration 168

# Change the random seed
python3 plotting.py --seed 42
```

Common options:


| Option              | Meaning                            | Default                      |
| ------------------- | ---------------------------------- | ---------------------------- |
| `--population`      | Number of people                   | `1000000`                    |
| `--num-buildings`   | Number of buildings                | `10000`                      |
| `--num-infected`    | Starting infected people           | `60000`                      |
| `--duration`        | Simulation length (hours)          | `1008`                       |
| `--sample-interval` | Hours between CSV samples          | `0.25`                       |
| `--seed`            | Random seed (same seed → same run) | `1`                          |
| `--avg-income`      | Mean income                        | `100000`                     |
| `--std-income`      | Income standard deviation          | `10000`                      |
| `--csv`             | Path for simulation CSV output     | `simulation.csv`             |
| `--plot`            | Path for plot image                | `simulation_plots.png`       |
| `--description`     | Path for description file          | `simulation_description.txt` |


---



## Optional — save a plot to GitHub

After you run the simulation, `plotting.py` writes:

- `simulation_plots.png` — the plot image  
- `simulation_description.txt` — the date and all parameters used for that run

Those two files stay on your computer only (they are listed in `.gitignore`).  
To keep a run on GitHub, add your own comments, then move both files into `saved_simulation_plots/`.

### 1 — Add your comments

Open the description file and replace the placeholder under **Comments**:

```bash
open simulation_description.txt          # Mac
# nano simulation_description.txt        # Linux / WSL
```



### 2 — Move and rename into a folder

Still inside the `Candy-Land` folder, run these commands in the **same Terminal window**.  
Change `my-run` to a short name for this run.

The files are renamed (`plots.png` and `description.txt`) so Git will track them — the original names are ignored by `.gitignore`:

```bash
RUN_NAME=my-run
FOLDER="saved_simulation_plots/$(date +%Y-%m-%d)_${RUN_NAME}"
mkdir -p "$FOLDER"
mv simulation_plots.png "$FOLDER/plots.png"
mv simulation_description.txt "$FOLDER/description.txt"
```

That creates a folder like `saved_simulation_plots/2026-07-27_my-run/` containing `plots.png` and `description.txt`.

### 3 — Upload to GitHub

```bash
git add "$FOLDER"
git commit -m "Save simulation plot: ${RUN_NAME}"
git push
```

Anyone cloning the repo can then open that folder under `saved_simulation_plots/` to see the plot and your notes.

---



## Architecture and design (for contributors) 

### Repository layout


| File / folder             | Role                                                                  |
| ------------------------- | --------------------------------------------------------------------- |
| `simulation.py`           | Core epidemic model (`CandyLand` class), event loop, and CLI          |
| `plotting.py`             | Runs the model, writes a description file, and plots the CSV          |
| `requirements.txt`        | Python dependencies (`numpy`, `matplotlib`)                           |
| `saved_simulation_plots/` | Optional checked-in runs (plots + notes); created when you save a run |
| `.gitignore`              | Ignores local outputs (`simulation.csv`, plot PNG, description txt)   |


### High-level design

Candy-Land is an **agent-based SEIR epidemic model** with movement between home and public buildings, individual compliance decisions, and a reactive government mandate.

Time is continuous. Events are scheduled with Poisson clocks:

1. Compute a rate for each event type from the current state.
2. Draw a waiting time from an exponential distribution with rate = sum of all rates.
3. Pick which event occurs in proportion to its rate.
4. Advance the clock, apply that event, repeat until `duration` hours are reached.

Between events the state does not change, so CSV samples are filled in for every crossed sample time without resimulating.

```
plotting.py
    │
    ├── CandyLand(...).run(...)     → simulation.csv
    ├── read / analyze CSV
    ├── write description file
    └── matplotlib plots            → simulation_plots.png

simulation.py (standalone)
    └── same CandyLand.run(...)     → CSV only (optional)
```



### Disease model (SEIR)

Each agent is in exactly one health state:


| Constant          | Meaning                                       |
| ----------------- | --------------------------------------------- |
| `SUSCEPTIBLE` (0) | Healthy; can become exposed                   |
| `EXPOSED` (1)     | Infected, not yet infectious                  |
| `INFECTIOUS` (2)  | Can transmit to others                        |
| `RECOVERED` (3)   | Temporary immunity; can return to susceptible |


Progression events: `S→E` (contact), `E→I` (incubation), `I→R` (recovery), `R→S` (waning immunity).

Infection only happens in public buildings: a susceptible agent on the floor is paired with a random co-occupant; if that contact is infectious, exposure probability depends on global prevalence, local infected fraction, and whether the susceptible agent is complying (compliance halves the exposure exponent).

### Movement and locations

- Agents are either **at home** (`locations[agent] == -1`) or in one of `num_buildings` public buildings.
- `on_floor` is a partitioned list of agent ids: indices `[0, num_on_floor)` are on the floor; the rest are at home. Swaps keep membership updates O(1).
- Movement events: `floor_to_floor`, `floor_to_home`, `home_to_floor`.
- `sun` swaps the day/night home↔floor movement rates every ~12 hours on average.



### Compliance and government

When an agent enters (or re-enters) a building, `_update_compliance` computes utilities from:

- global infection prevalence
- local infected fraction and peer compliance in that building
- the agent’s income-based financial burden
- fatigue from past compliance
- current `mandate_level` (0–3)

Those utilities become a logit compliance probability; a Bernoulli draw sets the binary `compliant` flag.

The `government` event recomputes `mandate_level` from infection × noncompliance pressure and updates how often policy is reviewed (higher mandate → more frequent reviews).

### Event types

Defined as constants at the top of `simulation.py` (`SUN` … `GOVERNMENT`). Handlers live in `CandyLand.event_handlers` and must stay in the same order as `_event_rates()`.


| Event                             | What it does                                                |
| --------------------------------- | ----------------------------------------------------------- |
| `sun`                             | Swap day/night movement rates                               |
| `floor_to_floor`                  | Move a floor agent to a random building; update compliance  |
| `floor_to_home` / `home_to_floor` | Leave or enter the public floor                             |
| `s_to_e`                          | Possible infection contact for a susceptible-on-floor agent |
| `e_to_i` / `i_to_r` / `r_to_s`    | Disease stage transitions                                   |
| `government`                      | Update mandate level and review rate                        |


Base rates live in `ClockRates` (events per hour). Group rates scale with how many agents are eligible (e.g. `floor_to_floor * num_on_floor`).

### Performance-critical data structures

The simulation targets large populations (default 1e6 agents), so membership updates are designed to be **O(1)** via swap-with-last removal:

- `health_groups[state]` + `health_positions[agent]` — agents by SEIR state
- `buildings[building]` + `building_positions[agent]` — occupants of each building
- `susceptible_floor` + `susceptible_floor_positions[agent]` — susceptibles currently in public buildings
- Aggregates: `building_infected`, `building_compliance_sum`, `_num_compliant`

If you change how agents move or change health, update these indexes the same way existing helpers do (`_add_to_building`, `_remove_from_building`, `_change_health`, etc.). After a run, `validate()` checks that indexes still agree with the raw arrays — call it when debugging structural changes.

### CSV output schema

Written by `CandyLand._record_state`:

```text
time,s,e,i,r,mandate,complying
```

`plotting.py` reads this file, checks population conservation, prints peak stats, and draws a 2×3 figure (S, E, I, R, mandate, complying).

### Where to change what


| Goal                          | Start here                                                                          |
| ----------------------------- | ----------------------------------------------------------------------------------- |
| Default CLI parameters        | `parse_args` in `simulation.py` and `main` in `plotting.py` (keep them in sync)     |
| Biological / movement rates   | `ClockRates` and `_update_government_rate`                                          |
| Infection probability formula | `s_to_e`                                                                            |
| Compliance utility / logit    | `_utilities`, `_update_compliance`                                                  |
| Mandate thresholds            | `government`                                                                        |
| Plot layout or analysis       | `plot_history`, `analyze_history` in `plotting.py`                                  |
| New event type                | Add constant, rate in `_event_rates`, handler method, and entry in `event_handlers` |




### Development tips

- Use a **small population and short duration** while iterating, e.g.  
`python3 plotting.py --population 10000 --num-buildings 100 --num-infected 600 --duration 168`
- Fix the **seed** (`--seed`) for reproducible debugging.
- After structural edits, rely on `validate()` (already called at the end of both entry points).
- Generated files (`simulation.csv`, `simulation_plots.png`, `simulation_description.txt`) are gitignored; use `saved_simulation_plots/` when you want a run in the repo (see above).

