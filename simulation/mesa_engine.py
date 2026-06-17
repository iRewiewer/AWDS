"""Mesa-native implementation of the AWDS simulation model."""

from __future__ import annotations

from typing import Any

import mesa
import networkx as nx
from mesa.space import NetworkGrid

from .agent import ROLE_PRESSURE, ROLE_PRODUCTIVITY_OFFSET
from .config import SimulationConfig
from .metrics import aggregate_agent_metrics, final_summary_from_history
from .utils import clamp


class MesaEmployeeAgent(mesa.Agent):
    """Mesa agent that owns the workplace state and daily behavior."""

    def __init__(self, model: "MesaWorkplaceModel", agent_id: int, onboarding: bool = False):
        super().__init__(model)
        self.unique_id = agent_id
        self.agent_id = agent_id

        config = model.config
        context = config.effective_context()
        rng = model.rng

        self.role = str(rng.choice(["junior", "mid", "senior", "manager"], p=[0.34, 0.36, 0.20, 0.10]))
        self.resilience = clamp(float(rng.beta(4.0, 3.0)))
        self.ambition = clamp(float(rng.beta(3.0, 3.0)))
        self.social_support_need = clamp(float(rng.beta(3.0, 3.0)))
        self.commute_sensitivity = clamp(float(rng.beta(2.2, 3.2)))
        self.family_load = clamp(float(rng.beta(2.4, 3.4)))
        self.health_variability = clamp(float(rng.beta(2.0, 5.0)))
        self.stress_sensitivity = clamp(float(rng.beta(2.4, 2.7)))
        self.recovery_rate = clamp(float(rng.beta(3.4, 2.6)))

        self.baseline_productivity = clamp(
            float(rng.uniform(0.42, 0.88)) + ROLE_PRODUCTIVITY_OFFSET[self.role],
            0.40,
            0.92,
        )
        self.stress = clamp(
            0.18
            + config.personal_stress_baseline * 0.30
            + self.family_load * 0.08
            + config.financial_pressure * 0.06
            - self.resilience * 0.08
            + float(rng.normal(0.0, 0.055))
        )
        self.burnout = clamp(float(rng.normal(0.08, 0.035)))
        self.emotion = clamp(
            0.05
            + (context["management_support"] - 0.5) * 0.20
            + (context["psychological_safety"] - 0.5) * 0.18
            - self.stress * 0.18
            + float(rng.normal(0.0, 0.12)),
            -1.0,
            1.0,
        )
        self.work_life_balance = clamp(
            0.68
            + context["work_life_balance_bonus"]
            - context["overtime_factor"] * 0.35
            - config.family_responsibilities_load * 0.10
            - config.commute_duration_impact * self.commute_sensitivity * 0.10
            + float(rng.normal(0.0, 0.05))
        )
        self.satisfaction = clamp(
            0.54
            + context["management_support"] * 0.12
            + context["recognition_level"] * 0.08
            + self.work_life_balance * 0.12
            - self.stress * 0.12
            + float(rng.normal(0.0, 0.05))
        )
        self.engagement = clamp(0.40 + self.ambition * 0.25 + self.satisfaction * 0.25 + float(rng.normal(0.0, 0.05)))
        self.energy = clamp(0.58 + self.recovery_rate * 0.22 + config.sleep_quality * 0.10 + float(rng.normal(0.0, 0.06)))
        self.productivity = self.baseline_productivity

        self.active = True
        self.left_day: int | None = None
        self.tenure_days = 0
        self.onboarding_days_remaining = config.onboarding_period_days if onboarding else 0
        self.lingering_stress_event = 0.0
        self.lingering_emotion_event = 0.0
        self.lingering_energy_event = 0.0

    def maybe_apply_personal_events(self) -> tuple[bool, bool]:
        if not self.active:
            return False, False

        config = self.model.config
        if not config.enable_random_life_events:
            return False, False

        negative = False
        positive = False
        if self.model.rng.random() < config.probability_negative_personal_event:
            self.apply_life_event("negative", config.event_impact_strength)
            negative = True
        if self.model.rng.random() < config.probability_positive_personal_event:
            self.apply_life_event("positive", config.event_impact_strength)
            positive = True
        return negative, positive

    def apply_life_event(self, event_kind: str, impact: float) -> None:
        rng = self.model.rng
        multiplier = float(rng.uniform(0.70, 1.25))
        if event_kind == "negative":
            self.lingering_stress_event += impact * multiplier
            self.lingering_emotion_event -= impact * float(rng.uniform(0.45, 1.00))
            self.lingering_energy_event -= impact * float(rng.uniform(0.25, 0.70))
        elif event_kind == "positive":
            self.lingering_stress_event -= impact * float(rng.uniform(0.25, 0.65))
            self.lingering_emotion_event += impact * float(rng.uniform(0.45, 1.00))
            self.lingering_energy_event += impact * float(rng.uniform(0.15, 0.45))
            self.satisfaction = clamp(self.satisfaction + impact * 0.06)

    def step(self) -> None:
        if not self.active:
            return

        social_context = self._social_context()
        self._update_state(
            context=self.model.day_context,
            social_context=social_context,
            org_event=self.model.org_event,
        )

    def _social_context(self) -> dict[str, float]:
        if self.pos is None:
            return {"social_emotion_influence": 0.0, "social_support_effect": 0.0}

        neighbor_emotions = [
            self.model.emotions_before_update[neighbor.agent_id]
            for neighbor in self.model.grid.get_neighbors(self.pos, include_center=False)
            if neighbor.active and neighbor.agent_id in self.model.emotions_before_update
        ]
        if not neighbor_emotions:
            return {"social_emotion_influence": 0.0, "social_support_effect": 0.0}

        average_neighbor_emotion = float(sum(neighbor_emotions) / len(neighbor_emotions))
        contagion = 0.0
        config = self.model.config
        if config.enable_emotional_contagion:
            contagion = (
                (average_neighbor_emotion - self.emotion)
                * config.emotional_contagion_strength
                * (0.6 + config.team_cohesion * 0.4)
            )
        support = (
            max(0.0, average_neighbor_emotion)
            * config.social_support_strength
            * config.team_cohesion
            * (1.0 + self.social_support_need * 0.25)
        )
        return {"social_emotion_influence": contagion, "social_support_effect": support}

    def _update_state(
        self,
        context: dict[str, float],
        social_context: dict[str, float],
        org_event: dict[str, Any],
    ) -> None:
        config = self.model.config
        rng = self.model.rng

        role_pressure = ROLE_PRESSURE[self.role]
        conflict_pressure = context["conflict_level"] * (0.4 + config.conflict_propagation_strength * 0.3)
        job_demands = (
            context["workload_intensity"]
            + context["deadline_pressure"]
            + context["overtime_factor"]
            + context["meeting_load"] * 0.3
            + context["interruptions"] * 0.3
            + conflict_pressure
            + role_pressure
            + org_event.get("demand_extra", 0.0)
        )
        job_resources = (
            context["management_support"]
            + context["autonomy_level"]
            + context["recognition_level"]
            + context["psychological_safety"]
            + context["role_clarity"]
            + social_context.get("social_support_effect", 0.0)
            + org_event.get("resource_extra", 0.0)
        )
        demand_normalized = clamp(job_demands / 3.0)
        resource_normalized = clamp(job_resources / 5.5)

        health_component = max(
            0.0,
            float(rng.normal(config.health_variability * 0.35, 0.08 + self.health_variability * 0.03)),
        )
        family_load = clamp((config.family_responsibilities_load + self.family_load) * 0.5)
        commute_load = clamp(context["commute_duration_impact"] * (0.5 + self.commute_sensitivity * 0.5))
        personal_load = clamp(
            family_load * 0.35
            + commute_load * 0.22
            + config.financial_pressure * 0.22
            + config.personal_stress_baseline * 0.25
            + health_component * 0.22
        )
        recovery = clamp(
            self.recovery_rate * 0.35
            + config.sleep_quality * 0.30
            + config.exercise_quality * 0.20
            + config.recovery_outside_work * 0.30
            + context["flexibility_bonus"] * 0.18
            + self.energy * 0.10
            - max(0.0, self.stress - 0.65) * 0.15
        )

        target_wlb = clamp(
            0.76
            - demand_normalized * 0.34
            - personal_load * 0.25
            - commute_load * 0.18
            + context["work_life_balance_bonus"]
            + config.recovery_outside_work * 0.10
        )
        self.work_life_balance = clamp(
            self.work_life_balance + (target_wlb - self.work_life_balance) * 0.18 + float(rng.normal(0.0, 0.008))
        )

        energy_delta = (
            recovery * 0.10
            - demand_normalized * 0.09
            - self.stress * 0.04
            - self.burnout * 0.05
            + self.lingering_energy_event * 0.08
        )
        self.energy = clamp(self.energy + energy_delta + float(rng.normal(0.0, 0.010)))

        stress_delta = (
            job_demands * self.stress_sensitivity
            + personal_load * 0.40
            - job_resources * 0.35
            - recovery * self.resilience * 0.40
            + self.lingering_stress_event
            + float(rng.normal(0.0, 0.035))
        )
        self.stress = clamp(self.stress + stress_delta * config.stress_scale)

        burnout_delta = (
            max(0.0, self.stress - 0.45) * config.burnout_accumulation_rate
            - recovery * config.burnout_recovery_rate
            - resource_normalized * 0.015
            + max(0.0, demand_normalized - 0.75) * 0.012
        )
        self.burnout = clamp(self.burnout + burnout_delta)

        social_emotion = social_context.get("social_emotion_influence", 0.0)
        emotion_delta = (
            -self.stress * 0.20
            - self.burnout * 0.25
            + resource_normalized * 0.25
            + social_emotion
            + org_event.get("emotion_extra", 0.0)
            + self.lingering_emotion_event
        )
        self.emotion = clamp(self.emotion + emotion_delta * config.emotion_scale, -1.0, 1.0)

        satisfaction_delta = (
            resource_normalized * 0.10
            + context["recognition_level"] * 0.10
            + self.work_life_balance * 0.10
            - self.stress * 0.10
            - self.burnout * 0.15
            - context["conflict_level"] * 0.10
            + org_event.get("satisfaction_extra", 0.0)
        )
        self.satisfaction = clamp(self.satisfaction + satisfaction_delta * 0.12)

        engagement_target = clamp(
            self.satisfaction * 0.45
            + self.ambition * 0.18
            + context["autonomy_level"] * 0.12
            + context["recognition_level"] * 0.12
            + max(0.0, self.emotion) * 0.08
            - self.burnout * 0.30
        )
        self.engagement = clamp(self.engagement + (engagement_target - self.engagement) * 0.12)

        optimal_pressure_bonus = 0.08 if 0.25 <= self.stress <= 0.55 else 0.0
        low_pressure_drag = 0.03 if self.stress < 0.15 else 0.0
        energy_loss_penalty = max(0.0, 0.52 - self.energy) * 0.35
        onboarding_penalty = 0.0
        if self.onboarding_days_remaining > 0:
            onboarding_penalty = (
                config.new_employee_onboarding_productivity_penalty
                * self.onboarding_days_remaining
                / max(1, config.onboarding_period_days)
            )

        self.productivity = clamp(
            self.baseline_productivity
            + self.engagement * 0.20
            + optimal_pressure_bonus
            + self.emotion * 0.10
            - self.burnout * 0.45
            - max(0.0, self.stress - 0.60) * 0.30
            - low_pressure_drag
            - energy_loss_penalty
            - onboarding_penalty
            - org_event.get("productivity_penalty", 0.0)
            + float(rng.normal(0.0, 0.025))
        )

        self.tenure_days += 1
        self.onboarding_days_remaining = max(0, self.onboarding_days_remaining - 1)
        decay = clamp(config.recovery_decay_rate, 0.05, 0.98) ** (1.0 / max(1, config.event_duration))
        self.lingering_stress_event *= decay
        self.lingering_emotion_event *= decay
        self.lingering_energy_event *= decay

    def to_state(self, day: int | None = None) -> dict[str, Any]:
        state = {
            "agent_id": self.agent_id,
            "role": self.role,
            "stress": self.stress,
            "burnout": self.burnout,
            "productivity": self.productivity,
            "emotion": self.emotion,
            "energy": self.energy,
            "satisfaction": self.satisfaction,
            "work_life_balance": self.work_life_balance,
            "engagement": self.engagement,
            "active": self.active,
            "left_day": self.left_day,
            "tenure_days": self.tenure_days,
        }
        if day is not None:
            state["day"] = day
        return state


class MesaWorkplaceModel(mesa.Model):
    """Mesa model using a network space and shuffled agent activation."""

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
        self.day_context = config.effective_context()
        self.org_event: dict[str, Any] = {}
        self.emotions_before_update: dict[int, float] = {}
        self.running = True

        self.graph = self._create_network_graph(config.num_agents)
        self.grid = NetworkGrid(self.graph)
        self.employee_slots = [
            self._create_employee_slot(agent_id=i, seat_index=i)
            for i in range(config.num_agents)
        ]
        self._record_metrics(event_notes=[])

    @property
    def employees(self) -> list[MesaEmployeeAgent]:
        return self.employee_slots

    def _create_employee_slot(self, agent_id: int, seat_index: int, onboarding: bool = False) -> MesaEmployeeAgent:
        employee = MesaEmployeeAgent(model=self, agent_id=agent_id, onboarding=onboarding)
        self.grid.place_agent(employee, seat_index)
        return employee

    def _create_network_graph(self, n_agents: int) -> nx.Graph:
        graph = nx.Graph()
        graph.add_nodes_from(range(n_agents))
        if n_agents <= 1:
            return graph

        close_count = min(max(1, self.config.close_colleagues_per_agent), n_agents - 1)
        density_count = int(round(clamp(self.config.network_density) * (n_agents - 1) * 0.10))
        target_count = min(n_agents - 1, close_count + density_count)

        for source in range(n_agents):
            candidates = [idx for idx in range(n_agents) if idx != source]
            selected = self.rng.choice(candidates, size=target_count, replace=False)
            for target in selected:
                graph.add_edge(source, int(target))

        extra_probability = clamp(self.config.network_density) * 0.045
        for source in range(n_agents):
            for target in range(source + 1, n_agents):
                if self.rng.random() < extra_probability:
                    graph.add_edge(source, target)

        return graph

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
            employee = self.employee_slots[seat_index]
            if due_day <= self.current_day and not employee.active:
                if employee.pos is not None:
                    self.grid.remove_agent(employee)
                employee.remove()
                self.employee_slots[seat_index] = self._create_employee_slot(
                    agent_id=self.next_agent_id,
                    seat_index=seat_index,
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
        for employee in self.agents.shuffle():
            if not isinstance(employee, MesaEmployeeAgent):
                continue
            negative, positive = employee.maybe_apply_personal_events()
            negative_count += int(negative)
            positive_count += int(positive)

        notes: list[str] = []
        if negative_count:
            notes.append(f"{negative_count} negative personal event(s)")
        if positive_count:
            notes.append(f"{positive_count} positive personal event(s)")
        return notes

    def _process_turnover(self) -> list[str]:
        if not self.config.enable_turnover:
            return []

        leavers: list[MesaEmployeeAgent] = []
        for employee in self.agents.shuffle():
            if not isinstance(employee, MesaEmployeeAgent) or not employee.active:
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
                leavers.append(employee)
                self.turnover_count += 1
                if self.config.replace_after_turnover and employee.pos is not None:
                    due_day = self.current_day + max(0, self.config.replacement_delay)
                    self.replacement_queue.append((due_day, int(employee.pos)))

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
        self.day_context = self.config.effective_context()
        self.org_event = self._draw_organizational_events()
        event_notes.extend(self.org_event["notes"])
        event_notes.extend(self._apply_personal_events())

        if self.disruption_days_remaining > 0:
            self.org_event["productivity_penalty"] += self.config.team_disruption_penalty_after_turnover
            self.org_event["emotion_extra"] -= self.config.team_disruption_penalty_after_turnover * 0.25
            self.disruption_days_remaining -= 1
            event_notes.append("team disruption after turnover")

        self.emotions_before_update = {
            employee.agent_id: employee.emotion
            for employee in self.employees
            if employee.active
        }
        self.agents.shuffle_do("step")

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
    """Adapter exposing the Mesa model through the dashboard engine API."""

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
