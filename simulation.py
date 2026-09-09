from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass

import numpy as np

# The four health stages an agent can occupy.
SUSCEPTIBLE = 0       # healthy, can become exposed
EXPOSED = 1           # infected but not yet infectious
INFECTIOUS = 2        # can transmit disease to others
RECOVERED = 3         # recovered; temporary immunity
NUM_HEALTH_STATES = 4 # number of SEIR compartments

# Every simulation event belongs to one of these categories.
SUN = 0               # day/night swap of home/floor movement rates
FLOOR_TO_FLOOR = 1    # agent moves between public buildings
FLOOR_TO_HOME = 2     # agent leaves the floor for home
HOME_TO_FLOOR = 3     # agent leaves home for the floor
S_TO_E = 4            # susceptible → exposed contact event
E_TO_I = 5            # exposed → infectious progression
I_TO_R = 6            # infectious → recovered progression
R_TO_S = 7            # recovered → susceptible (waning immunity)
GOVERNMENT = 8        # policy review / mandate update
NUM_EVENT_TYPES = 9   # total number of event categories


@dataclass
class ClockRates:
    # Rates are measured in events per hour.
    sun: float = 1.0 / 12.0                 # rate of day/night movement swap
    floor_to_floor: float = 1.0 / 9.6       # per-agent rate to change buildings
    floor_to_home: float = 1.0 / 4.5        # per-agent rate to go home from floor
    home_to_floor: float = 1.0 / 19.5       # per-agent rate to leave home for floor
    s_to_e: float = 13.0 / 24.0             # per susceptible-on-floor contact attempt rate
    e_to_i: float = 1.0 / 48.0              # per-exposed incubation completion rate
    i_to_r: float = 1.0 / 216.0             # per-infectious recovery rate
    r_to_s: float = 1.0 / 3600.0            # per-recovered immunity-waning rate
    government: float = 1.0 / (7.0 * 24.0)  # policy review rate (depends on mandate)


class CandyLand:
    def __init__(
        self,
        num_buildings: int,
        population: int,
        avg_income: float,
        std_income: float,
        num_infected: int,
        seed: int,
    ):
        if num_buildings <= 0 or population <= 0:
            raise ValueError("Buildings and population must be positive")
        if num_infected < 0 or num_infected > population:
            raise ValueError("Initial infected count must be between 0 and population")

        self.time = 0.0                         # scalar: simulated clock time in hours
        self.num_buildings = num_buildings      # scalar: how many public buildings exist
        self.population = population            # scalar: how many agents exist
        self.num_on_floor = 0                   # scalar: count of agents currently on the floor
        self._num_compliant = population        # scalar: count of agents marked compliant
        self.mandate_level = 0                  # scalar: government mandate intensity (0–3)
        self.lambda_logit = 1.0                 # scalar: logit sensitivity for compliance choice
        self.clocks = ClockRates()              # struct of scalar event rates (events per hour)
        self.rng = np.random.default_rng(seed)  # random number generator (not agent/building data)

        # Array/list indexed by agent id, unless noted otherwise.
        # on_floor is partitioned in-place: floor agents first, home agents second.
        self.on_floor = np.arange(population, dtype=int)  # list of agent ids; [:num_on_floor] on floor, rest at home
        self.incomes = np.empty(population, dtype=int)  # array[agent] -> that agent's income
        self.financial_burden = np.zeros(population)  # array[agent] -> that agent's income-quartile burden (0–1)
        self.compliance_prob = np.full(population, 0.5)  # array[agent] -> that agent's continuous compliance probability
        self.compliant = np.ones(population, dtype=np.uint8)  # array[agent] -> 1 if compliant, 0 if not
        self.fatigue = np.zeros(population, dtype=int)  # array[agent] -> that agent's compliance fatigue counter
        self.locations = np.full(population, -1, dtype=int)  # array[agent] -> building id they occupy, or -1 if at home
        self.health = np.full(population, SUSCEPTIBLE, dtype=np.uint8)  # array[agent] -> SEIR health state
        self.buildings = [[] for _ in range(num_buildings)]  # list[building] -> list of agent ids currently inside
        self.building_positions = np.full(population, -1, dtype=int)  # array[agent] -> index of that agent in buildings[location]
        self.health_positions = np.empty(population, dtype=int)  # array[agent] -> index of that agent in health_groups[health]
        self.susceptible_floor: list[int] = []  # list of agent ids who are susceptible and on the floor
        self.susceptible_floor_positions = np.full(population, -1, dtype=int)  # array[agent] -> index in susceptible_floor, or -1
        self.building_infected = np.zeros(num_buildings, dtype=int)  # array[building] -> count of infectious agents inside
        self.building_compliance_sum = np.zeros(num_buildings)  # array[building] -> sum of occupants' compliance_prob
        self.first_time_on_floor = np.zeros(population, dtype=bool)  # array[agent] -> True after first floor visit

        self._initialize_incomes(avg_income, std_income)

        # Start with everyone susceptible, then infect a random initial subset.
        self.health[:num_infected] = INFECTIOUS
        self.rng.shuffle(self.health)

        # list[health_state] -> list of agent ids currently in that SEIR state
        self.health_groups: list[list[int]] = [[] for _ in range(NUM_HEALTH_STATES)]
        for agent in range(population):
            state = int(self.health[agent])
            self.health_positions[agent] = len(self.health_groups[state])
            self.health_groups[state].append(agent)

        self._update_government_rate()

        self.event_handlers = (  # tuple[event_type] -> handler function for that event
            self.sun,
            self.floor_to_floor,
            self.floor_to_home,
            self.home_to_floor,
            self.s_to_e,
            self.e_to_i,
            self.i_to_r,
            self.r_to_s,
            self.government,
        )

    def next_event(self) -> tuple[float, int]:
        rates = self._event_rates()
        total_rate = float(sum(rates))
        if total_rate <= 0.0:
            raise RuntimeError("No events possible")

        # Independent Poisson clocks can be merged into one clock whose rate is
        # their sum. The event type is then selected in proportion to its rate.
        waiting_time = float(self.rng.exponential(1.0 / total_rate))
        event = int(self.rng.choice(NUM_EVENT_TYPES, p=np.asarray(rates) / total_rate))
        return waiting_time, event

    def perform_event(self, event: int) -> None:
        if event < 0 or event >= NUM_EVENT_TYPES:
            raise ValueError("Unknown event")
        self.event_handlers[event]()

    def run(self, duration: float, sample_interval: float, output_file: str) -> None:
        if duration < 0.0 or sample_interval <= 0.0:
            raise ValueError(
                "Duration must be nonnegative and sample interval must be positive"
            )

        write_output = output_file != "none"
        output = None
        if write_output:
            output = open(output_file, "w", encoding="utf-8")
            output.write("time,s,e,i,r,mandate,complying\n")
            self._record_state(output, 0.0)

        next_sample = sample_interval
        last_sample = 0.0
        try:
            while self.time < duration:
                waiting_time, event = self.next_event()
                event_time = self.time + waiting_time

                # State is constant between events, so record every crossed sample time.
                if write_output:
                    while next_sample <= min(event_time, duration):
                        self._record_state(output, next_sample)
                        last_sample = next_sample
                        next_sample += sample_interval

                if event_time > duration:
                    self.time = duration
                    break

                self.time = event_time
                self.perform_event(event)

            if write_output and last_sample < duration:
                self._record_state(output, duration)
        finally:
            if output is not None:
                output.close()

    def health_counts(self) -> tuple[int, int, int, int]:
        return (
            len(self.health_groups[SUSCEPTIBLE]),
            len(self.health_groups[EXPOSED]),
            len(self.health_groups[INFECTIOUS]),
            len(self.health_groups[RECOVERED]),
        )

    def num_compliant(self) -> int:
        return self._num_compliant

    # Confirm that all fast lookup structures still describe the same state.
    def validate(self) -> None:
        seen_health = np.zeros(self.population, dtype=bool)
        health_total = 0
        for state in range(NUM_HEALTH_STATES):
            group = self.health_groups[state]
            health_total += len(group)
            for position, agent in enumerate(group):
                if (
                    seen_health[agent]
                    or self.health[agent] != state
                    or self.health_positions[agent] != position
                ):
                    raise RuntimeError("Health index invariant failed")
                seen_health[agent] = True
        if health_total != self.population:
            raise RuntimeError("Population conservation failed")

        compliant_total = int(np.count_nonzero(self.compliant))
        if compliant_total != self._num_compliant:
            raise RuntimeError("Compliance count invariant failed")

        seen_building = np.zeros(self.population, dtype=bool)
        floor_total = 0
        for building in range(self.num_buildings):
            occupants = self.buildings[building]
            floor_total += len(occupants)
            infected = 0
            compliance_sum = 0.0
            for position, agent in enumerate(occupants):
                if (
                    seen_building[agent]
                    or self.locations[agent] != building
                    or self.building_positions[agent] != position
                ):
                    raise RuntimeError("Building index invariant failed")
                seen_building[agent] = True
                infected += self.health[agent] == INFECTIOUS
                compliance_sum += self.compliance_prob[agent]
            tolerance = 1e-8 * max(1.0, abs(compliance_sum))
            if (
                infected != self.building_infected[building]
                or abs(compliance_sum - self.building_compliance_sum[building]) > tolerance
            ):
                raise RuntimeError("Building aggregate invariant failed")
        if floor_total != self.num_on_floor:
            raise RuntimeError("Floor population invariant failed")
        for agent in range(self.population):
            if (self.locations[agent] != -1) != bool(seen_building[agent]):
                raise RuntimeError("Location invariant failed")

        seen_susceptible_floor = np.zeros(self.population, dtype=bool)
        for position, agent in enumerate(self.susceptible_floor):
            if (
                seen_susceptible_floor[agent]
                or self.health[agent] != SUSCEPTIBLE
                or self.locations[agent] == -1
                or self.susceptible_floor_positions[agent] != position
            ):
                raise RuntimeError("Susceptible-floor index invariant failed")
            seen_susceptible_floor[agent] = True
        for agent in range(self.population):
            eligible = self.health[agent] == SUSCEPTIBLE and self.locations[agent] != -1
            if eligible != bool(seen_susceptible_floor[agent]):
                raise RuntimeError("Susceptible-floor membership invariant failed")

    # ----- Population initialization and random selection -----

    def _initialize_incomes(self, avg_income: float, std_income: float) -> None:
        samples = self.rng.normal(avg_income, std_income, size=self.population)
        self.incomes = np.asarray(np.rint(samples), dtype=int)

        sorted_incomes = np.sort(self.incomes)

        def percentile(q: float) -> float:
            index = q * (self.population - 1)
            lower = int(math.floor(index))
            upper = int(math.ceil(index))
            fraction = index - lower
            return float(
                sorted_incomes[lower]
                + fraction * (sorted_incomes[upper] - sorted_incomes[lower])
            )

        q25 = percentile(0.25)
        q50 = percentile(0.50)
        q75 = percentile(0.75)

        for agent in range(self.population):
            income = self.incomes[agent]
            if income < q25:
                self.financial_burden[agent] = 1.0
            elif income < q50:
                self.financial_burden[agent] = 0.67
            elif income < q75:
                self.financial_burden[agent] = 0.33

    def _uniform_probability(self) -> float:
        return float(self.rng.random())

    def _random_index(self, size: int) -> int:
        return int(self.rng.integers(0, size))

    def _random_member(self, group: list[int]) -> int:
        return group[self._random_index(len(group))]

    def _update_government_rate(self) -> None:
        rates = (
            1.0 / (7.0 * 24.0),
            1.0 / (5.0 * 24.0),
            1.0 / (3.0 * 24.0),
            1.0 / 24.0,
        )
        self.clocks.government = rates[self.mandate_level]

    # ----- O(1) indexed membership updates -----

    def _add_susceptible_floor(self, agent: int) -> None:
        self.susceptible_floor_positions[agent] = len(self.susceptible_floor)
        self.susceptible_floor.append(agent)

    def _remove_susceptible_floor(self, agent: int) -> None:
        position = int(self.susceptible_floor_positions[agent])
        last_agent = self.susceptible_floor[-1]

        # Fill the removed slot with the last element instead of shifting the list.
        self.susceptible_floor[position] = last_agent
        self.susceptible_floor_positions[last_agent] = position
        self.susceptible_floor.pop()
        self.susceptible_floor_positions[agent] = -1

    def _add_to_building(self, agent: int, building: int) -> None:
        self.building_positions[agent] = len(self.buildings[building])
        self.buildings[building].append(agent)
        self.locations[agent] = building
        self.building_compliance_sum[building] += self.compliance_prob[agent]
        if self.health[agent] == INFECTIOUS:
            self.building_infected[building] += 1
        elif self.health[agent] == SUSCEPTIBLE:
            self._add_susceptible_floor(agent)

    def _remove_from_building(self, agent: int) -> None:
        building = int(self.locations[agent])
        occupants = self.buildings[building]
        position = int(self.building_positions[agent])
        last_agent = occupants[-1]

        # Swap-with-last removal keeps deletion constant-time.
        occupants[position] = last_agent
        self.building_positions[last_agent] = position
        occupants.pop()

        self.building_compliance_sum[building] -= self.compliance_prob[agent]
        if self.health[agent] == INFECTIOUS:
            self.building_infected[building] -= 1
        elif self.health[agent] == SUSCEPTIBLE:
            self._remove_susceptible_floor(agent)
        self.building_positions[agent] = -1
        self.locations[agent] = -1

    # Move one agent between disease stages using swap-with-last removal.
    def _change_health(self, agent: int, new_health: int) -> None:
        old_health = int(self.health[agent])
        if old_health == new_health:
            return
        building = int(self.locations[agent])
        if building != -1 and old_health == SUSCEPTIBLE:
            self._remove_susceptible_floor(agent)

        old_group = self.health_groups[old_health]
        old_position = int(self.health_positions[agent])
        last_agent = old_group[-1]
        old_group[old_position] = last_agent
        self.health_positions[last_agent] = old_position
        old_group.pop()

        new_group = self.health_groups[new_health]
        self.health_positions[agent] = len(new_group)
        new_group.append(agent)
        self.health[agent] = new_health

        if building != -1:
            if old_health == INFECTIOUS:
                self.building_infected[building] -= 1
            elif new_health == INFECTIOUS:
                self.building_infected[building] += 1
            if new_health == SUSCEPTIBLE:
                self._add_susceptible_floor(agent)

    # ----- Compliance decisions -----

    def _local_conditions(self, building: int, agent: int) -> tuple[float, float]:
        num_others = len(self.buildings[building]) - 1
        if num_others == 0:
            return 0.0, 0.0

        # Peer conditions exclude the agent who is currently deciding.
        infected = self.building_infected[building] - (self.health[agent] == INFECTIOUS)
        compliance = self.building_compliance_sum[building] - self.compliance_prob[agent]
        return infected / num_others, compliance / num_others

    # Calculate the benefits of complying and not complying for one agent.
    def _utilities(self, agent: int, building: int) -> tuple[float, float]:
        local_exposure, peer_compliance = self._local_conditions(building, agent)
        global_prevalence = len(self.health_groups[INFECTIOUS]) / self.population
        risk = global_prevalence * local_exposure + self.mandate_level
        utility_c = (
            math.log1p(risk) + math.log1p(peer_compliance) - self.financial_burden[agent]
        )
        utility_n = self.fatigue[agent] - risk - peer_compliance
        return utility_c, utility_n

    def _update_compliance(self, agent: int, building: int) -> None:
        utility_c, utility_n = self._utilities(agent, building)

        # Convert the two utilities into a compliance probability. Splitting the
        # formula into two branches prevents overflow for very different utilities.
        utility_difference = self.lambda_logit * (utility_n - utility_c)
        if utility_difference >= 0.0:
            exp_difference = math.exp(-utility_difference)
            probability = exp_difference / (1.0 + exp_difference)
        else:
            exp_difference = math.exp(utility_difference)
            probability = 1.0 / (1.0 + exp_difference)

        old_probability = self.compliance_prob[agent]
        self.compliance_prob[agent] = probability
        self.building_compliance_sum[building] += probability - old_probability

        # The stored probability is continuous; the realized choice is a Bernoulli draw.
        new_compliant = self._uniform_probability() < probability
        if new_compliant != bool(self.compliant[agent]):
            self._num_compliant += 1 if new_compliant else -1
            self.compliant[agent] = new_compliant
        if new_compliant:
            self.fatigue[agent] += 1
        else:
            # Fatigue can decrease but never becomes negative.
            self.fatigue[agent] = max(int(self.fatigue[agent]) - 1, 0)

    # ----- Movement events -----

    def sun(self) -> None:
        self.clocks.floor_to_home, self.clocks.home_to_floor = (
            self.clocks.home_to_floor,
            self.clocks.floor_to_home,
        )

    def floor_to_floor(self) -> None:
        agent = int(self.on_floor[self._random_index(self.num_on_floor)])
        new_building = self._random_index(self.num_buildings)
        self._remove_from_building(agent)
        self._add_to_building(agent, new_building)

        # Entering a public building triggers a new compliance decision.
        self._update_compliance(agent, new_building)

    def home_to_floor(self) -> None:
        agent_index = int(self.rng.integers(self.num_on_floor, self.population))
        agent = int(self.on_floor[agent_index])
        self.on_floor[agent_index], self.on_floor[self.num_on_floor] = (
            self.on_floor[self.num_on_floor],
            self.on_floor[agent_index],
        )
        self.num_on_floor += 1

        building = self._random_index(self.num_buildings)
        self._add_to_building(agent, building)

        if not self.first_time_on_floor[agent]:
            # First visit to the floor: start noncompliant.
            if self.compliant[agent]:
                self.compliant[agent] = False
                self._num_compliant -= 1
            self.first_time_on_floor[agent] = True
        else:
            # Returning to the public floor triggers a compliance decision.
            self._update_compliance(agent, building)

    def floor_to_home(self) -> None:
        agent_index = self._random_index(self.num_on_floor)
        agent = int(self.on_floor[agent_index])
        self.num_on_floor -= 1
        self.on_floor[agent_index], self.on_floor[self.num_on_floor] = (
            self.on_floor[self.num_on_floor],
            self.on_floor[agent_index],
        )

        self._remove_from_building(agent)
        if not self.compliant[agent]:
            # Being at home is treated as compliance.
            self.compliant[agent] = True
            self._num_compliant += 1

    # ----- Disease events -----

    # Only susceptible agents in public buildings can have an infectious contact.
    def s_to_e(self) -> None:
        if not self.susceptible_floor:
            return
        agent = self._random_member(self.susceptible_floor)
        building = int(self.locations[agent])
        occupants = self.buildings[building]
        if len(occupants) <= 1:
            return

        # Select another occupant uniformly without selecting the susceptible agent.
        contact_position = self._random_index(len(occupants) - 1)
        if contact_position >= self.building_positions[agent]:
            contact_position += 1
        contact = occupants[contact_position]
        if self.health[contact] != INFECTIOUS:
            return

        local_exposure, _ = self._local_conditions(building, agent)
        global_prevalence = len(self.health_groups[INFECTIOUS]) / self.population
        exponent = global_prevalence * local_exposure
        if self.compliant[agent]:
            # Protective behavior halves the exposure exponent.
            exponent /= 2.0
        exposure_probability = 1.0 - math.exp(-exponent * 7.0)
        if self._uniform_probability() < exposure_probability:
            self._change_health(agent, EXPOSED)

    def e_to_i(self) -> None:
        if self.health_groups[EXPOSED]:
            # An exposed agent finishes incubation and becomes infectious.
            self._change_health(self._random_member(self.health_groups[EXPOSED]), INFECTIOUS)

    def i_to_r(self) -> None:
        if self.health_groups[INFECTIOUS]:
            # An infectious agent finishes the infectious period and recovers.
            self._change_health(self._random_member(self.health_groups[INFECTIOUS]), RECOVERED)

    def r_to_s(self) -> None:
        if self.health_groups[RECOVERED]:
            # Immunity wanes and the recovered agent becomes susceptible again.
            self._change_health(self._random_member(self.health_groups[RECOVERED]), SUSCEPTIBLE)

    # ----- Government policy event -----

    # Recalculate policy pressure, the mandate level, and the next review rate.
    def government(self) -> None:
        infected = float(len(self.health_groups[INFECTIOUS]))

        # Pressure rises when infection is common and compliance is low.
        pressure = (infected / self.population) * (
            1.0 - self._num_compliant / self.population
        )
        if pressure < 0.25:
            self.mandate_level = 0
        elif pressure < 0.50:
            self.mandate_level = 1
        elif pressure < 0.75:
            self.mandate_level = 2
        else:
            self.mandate_level = 3
        self._update_government_rate()

    # ----- Event scheduling -----

    # Rates follow the same order as perform_event().
    def _event_rates(self) -> tuple[float, ...]:
        # A group of n independent clocks with individual rate r has total rate n*r.
        return (
            self.clocks.sun,
            self.clocks.floor_to_floor * self.num_on_floor,
            self.clocks.floor_to_home * self.num_on_floor,
            self.clocks.home_to_floor * (self.population - self.num_on_floor),
            self.clocks.s_to_e * len(self.susceptible_floor),
            self.clocks.e_to_i * len(self.health_groups[EXPOSED]),
            self.clocks.i_to_r * len(self.health_groups[INFECTIOUS]),
            self.clocks.r_to_s * len(self.health_groups[RECOVERED]),
            self.clocks.government,
        )

    def _record_state(self, output, sample_time: float) -> None:
        # Save only aggregate values needed by the plotting and analysis scripts.
        counts = self.health_counts()
        output.write(
            f"{sample_time:.10g},{counts[SUSCEPTIBLE]},{counts[EXPOSED]},"
            f"{counts[INFECTIOUS]},{counts[RECOVERED]},"
            f"{self.mandate_level},{self._num_compliant}\n"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Candy Land SEIR simulation.")
    parser.add_argument("--num-buildings", type=int, default=10_000)
    parser.add_argument("--population", type=int, default=1_000_000)
    parser.add_argument("--avg-income", type=float, default=100_000.0)
    parser.add_argument("--std-income", type=float, default=10_000.0)
    parser.add_argument("--num-infected", type=int, default=60_000)
    parser.add_argument("--duration", type=float, default=1_008.0,
                        help="Simulation length in hours")
    parser.add_argument("--sample-interval", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output-file", default="simulation.csv",
                        help='CSV path, or "none" to skip writing')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)

        model = CandyLand(
            args.num_buildings,
            args.population,
            args.avg_income,
            args.std_income,
            args.num_infected,
            args.seed,
        )

        start = time.perf_counter()
        model.run(args.duration, args.sample_interval, args.output_file)
        stop = time.perf_counter()
        model.validate()
        counts = model.health_counts()

        print(f"simulation_seconds={stop - start:.6f}")
        print(
            f"final_counts={counts[SUSCEPTIBLE]},{counts[EXPOSED]},"
            f"{counts[INFECTIOUS]},{counts[RECOVERED]}"
        )
        print(f"final_complying={model.num_compliant()}")
        return 0
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
