"""Employee agent state and update logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import SimulationConfig
from .utils import clamp


ROLE_PRESSURE = {
    "junior": 0.02,
    "mid": 0.04,
    "senior": 0.06,
    "manager": 0.09,
}

ROLE_PRODUCTIVITY_OFFSET = {
    "junior": -0.04,
    "mid": 0.00,
    "senior": 0.04,
    "manager": 0.02,
}


@dataclass
class EmployeeAgent:
    agent_id: int
    role: str
    stress: float
    burnout: float
    productivity: float
    emotion: float
    energy: float
    satisfaction: float
    work_life_balance: float
    engagement: float
    resilience: float
    ambition: float
    social_support_need: float
    commute_sensitivity: float
    family_load: float
    health_variability: float
    baseline_productivity: float
    stress_sensitivity: float
    recovery_rate: float
    active: bool = True
    left_day: int | None = None
    tenure_days: int = 0
    onboarding_days_remaining: int = 0
    lingering_stress_event: float = 0.0
    lingering_emotion_event: float = 0.0
    lingering_energy_event: float = 0.0

    @classmethod
    def create_random(
        cls,
        agent_id: int,
        rng: np.random.Generator,
        config: SimulationConfig,
        onboarding: bool = False,
    ) -> "EmployeeAgent":
        role = str(rng.choice(["junior", "mid", "senior", "manager"], p=[0.34, 0.36, 0.20, 0.10]))
        context = config.effective_context()

        resilience = clamp(float(rng.beta(4.0, 3.0)))
        ambition = clamp(float(rng.beta(3.0, 3.0)))
        social_support_need = clamp(float(rng.beta(3.0, 3.0)))
        commute_sensitivity = clamp(float(rng.beta(2.2, 3.2)))
        family_load = clamp(float(rng.beta(2.4, 3.4)))
        health_variability = clamp(float(rng.beta(2.0, 5.0)))
        stress_sensitivity = clamp(float(rng.beta(2.4, 2.7)))
        recovery_rate = clamp(float(rng.beta(3.4, 2.6)))

        baseline_productivity = clamp(
            float(rng.uniform(0.42, 0.88)) + ROLE_PRODUCTIVITY_OFFSET[role],
            0.40,
            0.92,
        )
        initial_stress = clamp(
            0.18
            + config.personal_stress_baseline * 0.30
            + family_load * 0.08
            + config.financial_pressure * 0.06
            - resilience * 0.08
            + float(rng.normal(0.0, 0.055))
        )
        initial_burnout = clamp(float(rng.normal(0.08, 0.035)))
        initial_emotion = clamp(
            0.05
            + (context["management_support"] - 0.5) * 0.20
            + (context["psychological_safety"] - 0.5) * 0.18
            - initial_stress * 0.18
            + float(rng.normal(0.0, 0.12)),
            -1.0,
            1.0,
        )
        initial_wlb = clamp(
            0.68
            + context["work_life_balance_bonus"]
            - context["overtime_factor"] * 0.35
            - config.family_responsibilities_load * 0.10
            - config.commute_duration_impact * commute_sensitivity * 0.10
            + float(rng.normal(0.0, 0.05))
        )
        satisfaction = clamp(
            0.54
            + context["management_support"] * 0.12
            + context["recognition_level"] * 0.08
            + initial_wlb * 0.12
            - initial_stress * 0.12
            + float(rng.normal(0.0, 0.05))
        )
        engagement = clamp(0.40 + ambition * 0.25 + satisfaction * 0.25 + float(rng.normal(0.0, 0.05)))
        energy = clamp(0.58 + recovery_rate * 0.22 + config.sleep_quality * 0.10 + float(rng.normal(0.0, 0.06)))

        return cls(
            agent_id=agent_id,
            role=role,
            stress=initial_stress,
            burnout=initial_burnout,
            productivity=baseline_productivity,
            emotion=initial_emotion,
            energy=energy,
            satisfaction=satisfaction,
            work_life_balance=initial_wlb,
            engagement=engagement,
            resilience=resilience,
            ambition=ambition,
            social_support_need=social_support_need,
            commute_sensitivity=commute_sensitivity,
            family_load=family_load,
            health_variability=health_variability,
            baseline_productivity=baseline_productivity,
            stress_sensitivity=stress_sensitivity,
            recovery_rate=recovery_rate,
            onboarding_days_remaining=config.onboarding_period_days if onboarding else 0,
        )

    def apply_life_event(self, event_kind: str, impact: float, rng: np.random.Generator) -> None:
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

    def update(
        self,
        config: SimulationConfig,
        rng: np.random.Generator,
        context: dict[str, float],
        social_context: dict[str, float],
        org_event: dict[str, float],
    ) -> None:
        if not self.active:
            return

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
