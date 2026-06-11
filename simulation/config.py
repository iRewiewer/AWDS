"""Configuration dataclasses and scenario-adjustment helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from .utils import clamp


MANAGEMENT_STYLES = ("supportive", "neutral", "authoritarian", "chaotic")
WORK_POLICIES = (
    "fixed schedule",
    "flexible schedule",
    "overtime-heavy",
    "compressed week",
    "remote/hybrid",
)


MANAGEMENT_STYLE_EFFECTS: dict[str, dict[str, float]] = {
    "supportive": {
        "management_support": 0.16,
        "psychological_safety": 0.12,
        "recognition_level": 0.08,
        "conflict_level": -0.06,
        "role_clarity": 0.06,
    },
    "neutral": {},
    "authoritarian": {
        "management_support": -0.18,
        "psychological_safety": -0.18,
        "autonomy_level": -0.16,
        "conflict_level": 0.12,
        "deadline_pressure": 0.06,
        "recognition_level": -0.06,
    },
    "chaotic": {
        "role_clarity": -0.24,
        "interruptions": 0.16,
        "deadline_pressure": 0.10,
        "conflict_level": 0.10,
        "management_support": -0.08,
    },
}


WORK_POLICY_EFFECTS: dict[str, dict[str, float]] = {
    "fixed schedule": {
        "overtime_factor": 0.05,
        "flexibility_bonus": 0.00,
        "commute_duration_impact": 0.08,
        "work_life_balance_bonus": -0.04,
    },
    "flexible schedule": {
        "overtime_factor": 0.00,
        "flexibility_bonus": 0.18,
        "commute_duration_impact": -0.05,
        "work_life_balance_bonus": 0.16,
    },
    "overtime-heavy": {
        "overtime_factor": 0.34,
        "flexibility_bonus": 0.00,
        "commute_duration_impact": 0.05,
        "work_life_balance_bonus": -0.24,
        "deadline_pressure": 0.08,
    },
    "compressed week": {
        "overtime_factor": 0.14,
        "flexibility_bonus": 0.10,
        "work_life_balance_bonus": 0.06,
    },
    "remote/hybrid": {
        "overtime_factor": 0.03,
        "flexibility_bonus": 0.16,
        "commute_duration_impact": -0.20,
        "meeting_load": 0.07,
        "interruptions": -0.03,
        "work_life_balance_bonus": 0.13,
    },
}


@dataclass
class SimulationConfig:
    """All tunable parameters for one AWDS run."""

    scenario_name: str = "Balanced baseline"
    num_agents: int = 50
    num_days: int = 180
    random_seed: int = 42
    refresh_interval: float = 0.05
    run_live: bool = True
    collect_per_agent_history: bool = False
    enable_emotional_contagion: bool = True
    enable_turnover: bool = True
    replace_after_turnover: bool = True
    enable_random_life_events: bool = True

    management_style: str = "neutral"
    work_policy: str = "fixed schedule"
    workload_intensity: float = 0.55
    deadline_pressure: float = 0.45
    autonomy_level: float = 0.55
    management_support: float = 0.55
    recognition_level: float = 0.50
    role_clarity: float = 0.60
    meeting_load: float = 0.40
    interruptions: float = 0.40
    conflict_level: float = 0.25
    psychological_safety: float = 0.55

    sleep_quality: float = 0.65
    exercise_quality: float = 0.55
    family_responsibilities_load: float = 0.40
    personal_stress_baseline: float = 0.35
    recovery_outside_work: float = 0.55
    commute_duration_impact: float = 0.35
    financial_pressure: float = 0.35
    health_variability: float = 0.25

    emotional_contagion_strength: float = 0.25
    social_support_strength: float = 0.35
    conflict_propagation_strength: float = 0.25
    network_density: float = 0.25
    close_colleagues_per_agent: int = 4
    team_cohesion: float = 0.55

    probability_negative_personal_event: float = 0.015
    probability_positive_personal_event: float = 0.010
    probability_organizational_crisis: float = 0.020
    probability_deadline_crunch: float = 0.030
    probability_recognition_event: float = 0.020
    event_impact_strength: float = 0.25
    event_duration: int = 3
    recovery_decay_rate: float = 0.60

    burnout_threshold: float = 0.72
    stress_threshold: float = 0.78
    turnover_probability_above_threshold: float = 0.012
    replacement_delay: int = 5
    new_employee_onboarding_productivity_penalty: float = 0.22
    team_disruption_penalty_after_turnover: float = 0.08
    base_turnover_probability: float = 0.001
    turnover_sensitivity: float = 0.18
    stress_turnover_sensitivity: float = 0.10
    onboarding_period_days: int = 12
    team_disruption_duration: int = 5

    stress_scale: float = 0.080
    burnout_accumulation_rate: float = 0.045
    burnout_recovery_rate: float = 0.018
    emotion_scale: float = 0.100

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def with_overrides(self, **overrides: Any) -> "SimulationConfig":
        return replace(self, **overrides)

    def effective_context(self) -> dict[str, float]:
        """Return organizational values after management and policy effects."""
        context = {
            "workload_intensity": self.workload_intensity,
            "deadline_pressure": self.deadline_pressure,
            "autonomy_level": self.autonomy_level,
            "management_support": self.management_support,
            "recognition_level": self.recognition_level,
            "role_clarity": self.role_clarity,
            "meeting_load": self.meeting_load,
            "interruptions": self.interruptions,
            "conflict_level": self.conflict_level,
            "psychological_safety": self.psychological_safety,
            "commute_duration_impact": self.commute_duration_impact,
            "overtime_factor": 0.0,
            "flexibility_bonus": 0.0,
            "work_life_balance_bonus": 0.0,
        }

        for key, delta in MANAGEMENT_STYLE_EFFECTS.get(self.management_style, {}).items():
            context[key] = context.get(key, 0.0) + delta

        for key, delta in WORK_POLICY_EFFECTS.get(self.work_policy, {}).items():
            context[key] = context.get(key, 0.0) + delta

        for key in (
            "workload_intensity",
            "deadline_pressure",
            "autonomy_level",
            "management_support",
            "recognition_level",
            "role_clarity",
            "meeting_load",
            "interruptions",
            "conflict_level",
            "psychological_safety",
            "commute_duration_impact",
            "overtime_factor",
            "flexibility_bonus",
            "work_life_balance_bonus",
        ):
            context[key] = clamp(context[key], 0.0, 1.0)

        return context
