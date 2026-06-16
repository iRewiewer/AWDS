"""Mesa-backed implementation of the AWDS simulation engine."""

from __future__ import annotations

from typing import Any

import mesa

from .agent import EmployeeAgent
from .config import SimulationConfig
from .metrics import aggregate_agent_metrics, final_summary_from_history
from .utils import clamp


class MesaEmployeeAgent(mesa.Agent):
    """Mesa agent wrapper around the existing AWDS employee state object."""

    def __init__(self, model: "MesaWorkplaceModel", employee: EmployeeAgent):
        super().__init__(model)
        self.employee = employee


class MesaWorkplaceModel(mesa.Model):
    """Mesa model that follows the same update sequence as the custom engine."""

    engine_name = "Mesa"

    def __init__(self, config: SimulationConfig):
        super().__init__(rng=config.random_seed)
        self.config = config
        self.current_day = 0
        self.next_agent_id = config.num_agents
        self.turnover_count = 0
        self.cumulative_productivity = 0.0
        self.cumulative_burnout = 0.0
        self.replacement_queue: list[tuple[int, int]] = []
        self.disruption_days_remaining = 0
        self.event_log: list[dict[str, Any]] = []
        self.aggregate_history: list[dict[str, Any]] = []
        self.per_agent_history: list[dict[str, Any]] = []

        self.employee_slots = [
            self._create_employee_slot(agent_id=i)
            for i in range(config.num_agents)
        ]
        self.network = self._create_network(config.num_agents)
        self._record_metrics(event_notes=[])

    @property
    def employees(self) -> list[EmployeeAgent]:
        return [slot.employee for slot in self.employee_slots]

    def _create_employee_slot(self, agent_id: int, onboarding: bool = False) -> MesaEmployeeAgent:
        employee = EmployeeAgent.create_random(
            agent_id=agent_id,
            rng=self.rng,
            config=self.config,
            onboarding=onboarding,
        )
        return MesaEmployeeAgent(model=self, employee=employee)

    def _create_network(self, n_agents: int) -> list[set[int]]:
        network = [set() for _ in range(n_agents)]
        if n_agents <= 1:
            return network

        close_count = min(max(1, self.config.close_colleagues_per_agent), n_agents - 1)
        density_count = int(round(clamp(self.config.network_density) * (n_agents - 1) * 0.10))
        target_count = min(n_agents - 1, close_count + density_count)

        for source in range(n_agents):
            candidates = [idx for idx in range(n_agents) if idx != source]
            selected = self.rng.choice(candidates, size=target_count, replace=False)
            for target in selected:
                target_int = int(target)
                network[source].add(target_int)
                network[target_int].add(source)

        extra_probability = clamp(self.config.network_density) * 0.045
        for source in range(n_agents):
            for target in range(source + 1, n_agents):
                if self.rng.random() < extra_probability:
                    network[source].add(target)
                    network[target].add(source)

        return network

    def _record_metrics(self, event_notes: list[str]) -> None:
        row = aggregate_agent_metrics(
            agents=self.employees,
            day=self.current_day,
            burnout_threshold=self.config.burnout_threshold,
            turnover_count=self.turnover_count,
            cumulative_productivity=self.cumulative_productivity,
            cumulative_burnout=self.cumulative_burnout,
        )
        row["events"] = ", ".join(event_notes) if event_notes else ""

        self.cumulative_productivity = row["cumulative_productivity"]
        self.cumulative_burnout = row["cumulative_burnout"]
        self.aggregate_history.append(row)

        if self.config.collect_per_agent_history:
            for employee in self.employees:
                self.per_agent_history.append(employee.to_state(day=self.current_day))

    def _process_replacements(self) -> list[str]:
        notes: list[str] = []
        if not self.config.replace_after_turnover:
            return notes

        remaining: list[tuple[int, int]] = []
        for due_day, seat_index in self.replacement_queue:
            if due_day <= self.current_day and not self.employee_slots[seat_index].employee.active:
                self.employee_slots[seat_index].remove()
                self.employee_slots[seat_index] = self._create_employee_slot(
                    agent_id=self.next_agent_id,
                    onboarding=True,
                )
                self.next_agent_id += 1
                notes.append("replacement hired")
            else:
                remaining.append((due_day, seat_index))
        self.replacement_queue = remaining
        return notes

    def _draw_organizational_events(self) -> dict[str, Any]:
        event = {
            "demand_extra": 0.0,
            "resource_extra": 0.0,
            "emotion_extra": 0.0,
            "satisfaction_extra": 0.0,
            "productivity_penalty": 0.0,
            "notes": [],
        }
        if not self.config.enable_random_life_events:
            return event

        impact = self.config.event_impact_strength
        if self.rng.random() < self.config.probability_organizational_crisis:
            event["demand_extra"] += impact * 0.85
            event["resource_extra"] -= impact * 0.20
            event["emotion_extra"] -= impact * 0.55
            event["productivity_penalty"] += impact * 0.08
            event["notes"].append("organizational crisis")

        if self.rng.random() < self.config.probability_deadline_crunch:
            event["demand_extra"] += impact * 0.65
            event["emotion_extra"] -= impact * 0.22
            event["productivity_penalty"] += impact * 0.04
            event["notes"].append("deadline crunch")

        if self.rng.random() < self.config.probability_recognition_event:
            event["resource_extra"] += impact * 0.55
            event["emotion_extra"] += impact * 0.60
            event["satisfaction_extra"] += impact * 0.32
            event["notes"].append("recognition event")

        return event

    def _apply_personal_events(self) -> list[str]:
        if not self.config.enable_random_life_events:
            return []

        negative_count = 0
        positive_count = 0
        for employee in self.employees:
            if not employee.active:
                continue
            if self.rng.random() < self.config.probability_negative_personal_event:
                employee.apply_life_event("negative", self.config.event_impact_strength, self.rng)
                negative_count += 1
            if self.rng.random() < self.config.probability_positive_personal_event:
                employee.apply_life_event("positive", self.config.event_impact_strength, self.rng)
                positive_count += 1

        notes: list[str] = []
        if negative_count:
            notes.append(f"{negative_count} negative personal event(s)")
        if positive_count:
            notes.append(f"{positive_count} positive personal event(s)")
        return notes

    def _social_context_for(self, seat_index: int, emotions_before_update: list[float | None]) -> dict[str, float]:
        if not self.network[seat_index]:
            return {"social_emotion_influence": 0.0, "social_support_effect": 0.0}

        neighbor_emotions = [
            emotions_before_update[neighbor]
            for neighbor in self.network[seat_index]
            if emotions_before_update[neighbor] is not None
        ]
        if not neighbor_emotions:
            return {"social_emotion_influence": 0.0, "social_support_effect": 0.0}

        employee = self.employee_slots[seat_index].employee
        average_neighbor_emotion = float(sum(neighbor_emotions) / len(neighbor_emotions))
        contagion = 0.0
        if self.config.enable_emotional_contagion:
            contagion = (
                (average_neighbor_emotion - employee.emotion)
                * self.config.emotional_contagion_strength
                * (0.6 + self.config.team_cohesion * 0.4)
            )
        support = (
            max(0.0, average_neighbor_emotion)
            * self.config.social_support_strength
            * self.config.team_cohesion
            * (1.0 + employee.social_support_need * 0.25)
        )
        return {"social_emotion_influence": contagion, "social_support_effect": support}

    def _process_turnover(self) -> list[str]:
        if not self.config.enable_turnover:
            return []

        leavers: list[int] = []
        for seat_index, employee in enumerate(self.employees):
            if not employee.active:
                continue
            burnout_excess = max(0.0, employee.burnout - self.config.burnout_threshold)
            stress_excess = max(0.0, employee.stress - self.config.stress_threshold)
            if burnout_excess <= 0.0 and stress_excess <= 0.0:
                continue

            threshold_probability = self.config.turnover_probability_above_threshold
            if burnout_excess <= 0.0:
                threshold_probability *= 0.35

            probability = (
                self.config.base_turnover_probability
                + threshold_probability
                + burnout_excess * self.config.turnover_sensitivity
                + stress_excess * self.config.stress_turnover_sensitivity
                - employee.satisfaction * 0.04
            )
            if self.rng.random() < clamp(probability, 0.0, 0.80):
                employee.active = False
                employee.left_day = self.current_day
                leavers.append(seat_index)
                self.turnover_count += 1
                if self.config.replace_after_turnover:
                    due_day = self.current_day + max(0, self.config.replacement_delay)
                    self.replacement_queue.append((due_day, seat_index))

        if leavers:
            self.disruption_days_remaining = max(
                self.disruption_days_remaining,
                max(1, self.config.team_disruption_duration),
            )
            return [f"{len(leavers)} employee(s) left"]
        return []

    def step(self) -> None:
        if self.current_day >= self.config.num_days:
            self.running = False
            return

        self.current_day += 1
        event_notes = self._process_replacements()
        context = self.config.effective_context()
        org_event = self._draw_organizational_events()
        event_notes.extend(org_event["notes"])
        event_notes.extend(self._apply_personal_events())

        if self.disruption_days_remaining > 0:
            org_event["productivity_penalty"] += self.config.team_disruption_penalty_after_turnover
            org_event["emotion_extra"] -= self.config.team_disruption_penalty_after_turnover * 0.25
            self.disruption_days_remaining -= 1
            event_notes.append("team disruption after turnover")

        emotions_before_update: list[float | None] = [
            employee.emotion if employee.active else None for employee in self.employees
        ]
        for seat_index, employee in enumerate(self.employees):
            if not employee.active:
                continue
            social_context = self._social_context_for(seat_index, emotions_before_update)
            employee.update(
                config=self.config,
                rng=self.rng,
                context=context,
                social_context=social_context,
                org_event=org_event,
            )

        event_notes.extend(self._process_turnover())
        if event_notes:
            self.event_log.append({"day": self.current_day, "events": event_notes})
        self._record_metrics(event_notes=event_notes)
        if self.current_day >= self.config.num_days:
            self.running = False

    def snapshot(self) -> dict[str, Any]:
        return {
            "project": "Adaptive Workplace Dynamics Simulator",
            "engine": self.engine_name,
            "scenario_name": self.config.scenario_name,
            "seed": self.config.random_seed,
            "config": self.config.to_dict(),
            "aggregate_time_series": list(self.aggregate_history),
            "per_agent_history": list(self.per_agent_history),
            "final_agent_states": [employee.to_state() for employee in self.employees],
            "event_log": list(self.event_log),
            "final_summary": final_summary_from_history(self.aggregate_history),
            "notes": "Synthetic simulation output. Not empirical data.",
        }

    def result(self) -> dict[str, Any]:
        return self.snapshot()


class MesaSimulationEngine:
    """Adapter exposing the same public API as the custom simulation engine."""

    engine_name = "Mesa"

    def __init__(self, config: SimulationConfig):
        self.model = MesaWorkplaceModel(config)

    @property
    def config(self) -> SimulationConfig:
        return self.model.config

    @property
    def current_day(self) -> int:
        return self.model.current_day

    def step(self) -> dict[str, Any]:
        if self.model.current_day < self.model.config.num_days:
            self.model.step()
        return self.snapshot()

    def run(self) -> dict[str, Any]:
        while self.model.current_day < self.model.config.num_days:
            self.step()
        return self.result()

    def run_live_generator(self):
        yield self.snapshot()
        while self.model.current_day < self.model.config.num_days:
            yield self.step()

    def snapshot(self) -> dict[str, Any]:
        return self.model.snapshot()

    def result(self) -> dict[str, Any]:
        return self.model.result()
