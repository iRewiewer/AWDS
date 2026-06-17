"""Aggregation and summary helpers."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from .utils import safe_mean


class AgentMetricsLike(Protocol):
    active: bool
    stress: float
    burnout: float
    productivity: float
    emotion: float
    energy: float
    satisfaction: float
    work_life_balance: float


def aggregate_agent_metrics(
    agents: Sequence[AgentMetricsLike],
    day: int,
    burnout_threshold: float,
    turnover_count: int,
    cumulative_productivity: float,
    cumulative_burnout: float,
) -> dict[str, Any]:
    active = [agent for agent in agents if agent.active]
    stress_values = [agent.stress for agent in active]
    burnout_values = [agent.burnout for agent in active]
    productivity_values = [agent.productivity for agent in active]
    emotion_values = [agent.emotion for agent in active]
    energy_values = [agent.energy for agent in active]
    satisfaction_values = [agent.satisfaction for agent in active]
    wlb_values = [agent.work_life_balance for agent in active]

    average_productivity = safe_mean(productivity_values)
    average_burnout = safe_mean(burnout_values)

    return {
        "day": day,
        "average_stress": safe_mean(stress_values),
        "average_burnout": average_burnout,
        "average_productivity": average_productivity,
        "average_emotion": safe_mean(emotion_values),
        "average_energy": safe_mean(energy_values),
        "average_satisfaction": safe_mean(satisfaction_values),
        "average_work_life_balance": safe_mean(wlb_values),
        "burned_out_count": sum(1 for agent in active if agent.burnout >= burnout_threshold),
        "turnover_count": turnover_count,
        "active_employee_count": len(active),
        "cumulative_productivity": cumulative_productivity + average_productivity,
        "cumulative_burnout": cumulative_burnout + average_burnout,
    }


def final_summary_from_history(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {}

    final = history[-1]
    productivity_values = [row["average_productivity"] for row in history]
    return {
        "final_day": final["day"],
        "final_average_stress": final["average_stress"],
        "final_average_burnout": final["average_burnout"],
        "final_average_productivity": final["average_productivity"],
        "final_average_emotion": final["average_emotion"],
        "final_average_satisfaction": final["average_satisfaction"],
        "final_average_work_life_balance": final["average_work_life_balance"],
        "burned_out_count": final["burned_out_count"],
        "total_turnover": final["turnover_count"],
        "active_employee_count": final["active_employee_count"],
        "cumulative_burnout": final["cumulative_burnout"],
        "cumulative_productivity": final["cumulative_productivity"],
        "lowest_productivity": min(productivity_values),
    }
