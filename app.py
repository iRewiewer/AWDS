from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from simulation.config import MANAGEMENT_STYLES, WORK_POLICIES, SimulationConfig
from simulation.engine import SimulationEngine
from simulation.exports import save_export_bundle
from simulation.scenarios import PRESET_SCENARIOS, get_scenario_config
from simulation.utils import slugify

try:
    import plotly.express as px
    import plotly.graph_objects as go

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


st.set_page_config(
    page_title="AWDS Prototype",
    layout="wide",
)


def main() -> None:
    st.title("Adaptive Workplace Dynamics Simulator")
    st.caption("Exploratory synthetic agent-based workplace simulation. Outputs are model-generated, not empirical findings.")

    config, run_requested, reset_requested = render_sidebar()
    if reset_requested:
        st.session_state.pop("latest_result", None)
        st.session_state.pop("export_paths", None)
        st.session_state.pop("comparison_result", None)

    run_tab, compare_tab, export_tab, about_tab = st.tabs(
        ["Run Simulation", "Compare Scenarios", "Export Results", "About Model"]
    )

    with run_tab:
        render_run_tab(config, run_requested)

    with compare_tab:
        render_comparison_tab(config)

    with export_tab:
        render_export_tab()

    with about_tab:
        render_about_tab()


def render_sidebar() -> tuple[SimulationConfig, bool, bool]:
    st.sidebar.header("Configuration")
    scenario_names = list(PRESET_SCENARIOS.keys())
    scenario_name = st.sidebar.selectbox(
        "Scenario preset",
        scenario_names,
        index=scenario_names.index("Balanced baseline"),
        help="Pick a preset, then override any parameter below.",
    )
    preset = get_scenario_config(scenario_name)
    key_prefix = slugify(scenario_name)

    with st.sidebar.expander("Simulation controls", expanded=True):
        num_agents = st.number_input("Number of agents", min_value=5, max_value=500, value=preset.num_agents, step=5)
        num_days = st.number_input("Number of days/ticks", min_value=1, max_value=1000, value=preset.num_days, step=10)
        random_seed = st.number_input("Random seed", min_value=0, max_value=2_147_483_647, value=preset.random_seed, step=1)
        refresh_interval = st.slider(
            "Live update speed / refresh interval (seconds)",
            min_value=0.00,
            max_value=1.00,
            value=preset.refresh_interval,
            step=0.01,
        )
        run_live = st.checkbox("Run live", value=preset.run_live)
        collect_per_agent_history = st.checkbox(
            "Collect per-agent history",
            value=preset.collect_per_agent_history,
            help="Useful for raw exports; can make large runs slower.",
        )
        enable_emotional_contagion = st.checkbox(
            "Enable emotional contagion",
            value=preset.enable_emotional_contagion,
        )
        enable_turnover = st.checkbox("Enable turnover", value=preset.enable_turnover)
        replace_after_turnover = st.checkbox(
            "Replace employees after turnover",
            value=preset.replace_after_turnover,
        )
        enable_random_life_events = st.checkbox(
            "Enable random life events",
            value=preset.enable_random_life_events,
        )

    with st.sidebar.expander("Organizational modifiers", expanded=True):
        management_style = st.selectbox(
            "Management style",
            MANAGEMENT_STYLES,
            index=MANAGEMENT_STYLES.index(preset.management_style),
            key=f"{key_prefix}_management_style",
        )
        work_policy = st.selectbox(
            "Work policy",
            WORK_POLICIES,
            index=WORK_POLICIES.index(preset.work_policy),
            key=f"{key_prefix}_work_policy",
        )
        workload_intensity = sidebar_slider("Workload intensity", preset.workload_intensity, key_prefix)
        deadline_pressure = sidebar_slider("Deadline pressure", preset.deadline_pressure, key_prefix)
        autonomy_level = sidebar_slider("Autonomy level", preset.autonomy_level, key_prefix)
        management_support = sidebar_slider("Management support", preset.management_support, key_prefix)
        recognition_level = sidebar_slider("Recognition/reward level", preset.recognition_level, key_prefix)
        role_clarity = sidebar_slider("Role clarity", preset.role_clarity, key_prefix)
        meeting_load = sidebar_slider("Meeting load", preset.meeting_load, key_prefix)
        interruptions = sidebar_slider("Interruptions/context switching", preset.interruptions, key_prefix)
        conflict_level = sidebar_slider("Conflict level", preset.conflict_level, key_prefix)
        psychological_safety = sidebar_slider("Psychological safety", preset.psychological_safety, key_prefix)

    with st.sidebar.expander("Personal/lifestyle modifiers"):
        sleep_quality = sidebar_slider("Average sleep quality", preset.sleep_quality, key_prefix)
        exercise_quality = sidebar_slider("Exercise/habits quality", preset.exercise_quality, key_prefix)
        family_responsibilities_load = sidebar_slider(
            "Family responsibilities load", preset.family_responsibilities_load, key_prefix
        )
        personal_stress_baseline = sidebar_slider("Personal stress baseline", preset.personal_stress_baseline, key_prefix)
        recovery_outside_work = sidebar_slider("Recovery outside work", preset.recovery_outside_work, key_prefix)
        commute_duration_impact = sidebar_slider("Commute duration impact", preset.commute_duration_impact, key_prefix)
        financial_pressure = sidebar_slider("Financial pressure", preset.financial_pressure, key_prefix)
        health_variability = sidebar_slider("Health variability", preset.health_variability, key_prefix)

    with st.sidebar.expander("Social/network modifiers"):
        emotional_contagion_strength = sidebar_slider(
            "Emotional contagion strength", preset.emotional_contagion_strength, key_prefix
        )
        social_support_strength = sidebar_slider("Social support strength", preset.social_support_strength, key_prefix)
        conflict_propagation_strength = sidebar_slider(
            "Conflict propagation strength", preset.conflict_propagation_strength, key_prefix
        )
        network_density = sidebar_slider("Network density", preset.network_density, key_prefix)
        close_colleagues_per_agent = st.number_input(
            "Number of close colleagues per agent",
            min_value=1,
            max_value=max(1, int(num_agents) - 1),
            value=min(preset.close_colleagues_per_agent, max(1, int(num_agents) - 1)),
            step=1,
            key=f"{key_prefix}_close_colleagues",
        )
        team_cohesion = sidebar_slider("Team cohesion", preset.team_cohesion, key_prefix)

    with st.sidebar.expander("Random event modifiers"):
        probability_negative_personal_event = st.slider(
            "Probability of negative personal event per agent/day",
            0.0,
            0.20,
            preset.probability_negative_personal_event,
            0.001,
            key=f"{key_prefix}_negative_event_prob",
        )
        probability_positive_personal_event = st.slider(
            "Probability of positive personal event per agent/day",
            0.0,
            0.20,
            preset.probability_positive_personal_event,
            0.001,
            key=f"{key_prefix}_positive_event_prob",
        )
        probability_organizational_crisis = st.slider(
            "Probability of organizational crisis per day",
            0.0,
            0.20,
            preset.probability_organizational_crisis,
            0.001,
            key=f"{key_prefix}_crisis_prob",
        )
        probability_deadline_crunch = st.slider(
            "Probability of deadline crunch per day",
            0.0,
            0.20,
            preset.probability_deadline_crunch,
            0.001,
            key=f"{key_prefix}_crunch_prob",
        )
        probability_recognition_event = st.slider(
            "Probability of recognition/reward event per day",
            0.0,
            0.20,
            preset.probability_recognition_event,
            0.001,
            key=f"{key_prefix}_recognition_prob",
        )
        event_impact_strength = sidebar_slider("Event impact strength", preset.event_impact_strength, key_prefix)
        event_duration = st.number_input(
            "Event duration",
            min_value=1,
            max_value=30,
            value=preset.event_duration,
            step=1,
            key=f"{key_prefix}_event_duration",
        )
        recovery_decay_rate = st.slider(
            "Recovery decay rate",
            0.05,
            0.98,
            preset.recovery_decay_rate,
            0.01,
            key=f"{key_prefix}_recovery_decay_rate",
        )

    with st.sidebar.expander("Turnover/model modifiers"):
        burnout_threshold = sidebar_slider("Burnout threshold", preset.burnout_threshold, key_prefix)
        stress_threshold = sidebar_slider("Stress threshold", preset.stress_threshold, key_prefix)
        turnover_probability_above_threshold = st.slider(
            "Turnover probability above threshold",
            0.0,
            0.30,
            preset.turnover_probability_above_threshold,
            0.001,
            key=f"{key_prefix}_turnover_probability",
        )
        replacement_delay = st.number_input(
            "Replacement delay",
            min_value=0,
            max_value=90,
            value=preset.replacement_delay,
            step=1,
            key=f"{key_prefix}_replacement_delay",
        )
        new_employee_onboarding_productivity_penalty = sidebar_slider(
            "New employee onboarding productivity penalty",
            preset.new_employee_onboarding_productivity_penalty,
            key_prefix,
        )
        team_disruption_penalty_after_turnover = sidebar_slider(
            "Team disruption penalty after turnover",
            preset.team_disruption_penalty_after_turnover,
            key_prefix,
        )
        stress_scale = st.slider("Stress update scale", 0.01, 0.20, preset.stress_scale, 0.005, key=f"{key_prefix}_stress_scale")
        burnout_accumulation_rate = st.slider(
            "Burnout accumulation rate",
            0.005,
            0.120,
            preset.burnout_accumulation_rate,
            0.001,
            key=f"{key_prefix}_burnout_accumulation",
        )
        burnout_recovery_rate = st.slider(
            "Burnout recovery rate",
            0.001,
            0.080,
            preset.burnout_recovery_rate,
            0.001,
            key=f"{key_prefix}_burnout_recovery",
        )

    run_requested = st.sidebar.button("Run simulation", type="primary", use_container_width=True)
    reset_requested = st.sidebar.button("Stop/reset", use_container_width=True)

    config = SimulationConfig(
        scenario_name=scenario_name,
        num_agents=int(num_agents),
        num_days=int(num_days),
        random_seed=int(random_seed),
        refresh_interval=float(refresh_interval),
        run_live=run_live,
        collect_per_agent_history=collect_per_agent_history,
        enable_emotional_contagion=enable_emotional_contagion,
        enable_turnover=enable_turnover,
        replace_after_turnover=replace_after_turnover,
        enable_random_life_events=enable_random_life_events,
        management_style=management_style,
        work_policy=work_policy,
        workload_intensity=workload_intensity,
        deadline_pressure=deadline_pressure,
        autonomy_level=autonomy_level,
        management_support=management_support,
        recognition_level=recognition_level,
        role_clarity=role_clarity,
        meeting_load=meeting_load,
        interruptions=interruptions,
        conflict_level=conflict_level,
        psychological_safety=psychological_safety,
        sleep_quality=sleep_quality,
        exercise_quality=exercise_quality,
        family_responsibilities_load=family_responsibilities_load,
        personal_stress_baseline=personal_stress_baseline,
        recovery_outside_work=recovery_outside_work,
        commute_duration_impact=commute_duration_impact,
        financial_pressure=financial_pressure,
        health_variability=health_variability,
        emotional_contagion_strength=emotional_contagion_strength,
        social_support_strength=social_support_strength,
        conflict_propagation_strength=conflict_propagation_strength,
        network_density=network_density,
        close_colleagues_per_agent=int(close_colleagues_per_agent),
        team_cohesion=team_cohesion,
        probability_negative_personal_event=probability_negative_personal_event,
        probability_positive_personal_event=probability_positive_personal_event,
        probability_organizational_crisis=probability_organizational_crisis,
        probability_deadline_crunch=probability_deadline_crunch,
        probability_recognition_event=probability_recognition_event,
        event_impact_strength=event_impact_strength,
        event_duration=int(event_duration),
        recovery_decay_rate=recovery_decay_rate,
        burnout_threshold=burnout_threshold,
        stress_threshold=stress_threshold,
        turnover_probability_above_threshold=turnover_probability_above_threshold,
        replacement_delay=int(replacement_delay),
        new_employee_onboarding_productivity_penalty=new_employee_onboarding_productivity_penalty,
        team_disruption_penalty_after_turnover=team_disruption_penalty_after_turnover,
        stress_scale=stress_scale,
        burnout_accumulation_rate=burnout_accumulation_rate,
        burnout_recovery_rate=burnout_recovery_rate,
    )
    return config, run_requested, reset_requested


def sidebar_slider(label: str, value: float, key_prefix: str) -> float:
    key = f"{key_prefix}_{slugify(label)}"
    return st.slider(label, 0.0, 1.0, float(value), 0.01, key=key)


def render_run_tab(config: SimulationConfig, run_requested: bool) -> None:
    top_cols = st.columns([2, 1, 1])
    top_cols[0].subheader(config.scenario_name)
    top_cols[1].metric("Seed", config.random_seed)
    top_cols[2].metric("Days", config.num_days)
    st.info("Results shown here are synthetic model outputs for exploratory comparison, not empirical predictions.")

    if run_requested:
        st.session_state.pop("export_paths", None)
        result = execute_run(config)
        st.session_state.latest_result = result

    latest_result = st.session_state.get("latest_result")
    if latest_result:
        render_result_dashboard(latest_result)
    else:
        st.write("Select a preset or adjust parameters in the sidebar, then run the simulation.")


def execute_run(config: SimulationConfig) -> dict[str, Any]:
    engine = SimulationEngine(config)
    if not config.run_live:
        with st.spinner("Running synthetic simulation..."):
            return engine.run()

    progress = st.progress(0, text="Starting simulation")
    metrics_placeholder = st.empty()
    chart_placeholder = st.empty()
    result: dict[str, Any] = engine.snapshot()
    update_every = max(1, config.num_days // 120)

    for snapshot in engine.run_live_generator():
        result = snapshot
        latest_day = int(snapshot["final_summary"].get("final_day", 0))
        if latest_day % update_every == 0 or latest_day == config.num_days:
            progress.progress(
                min(1.0, latest_day / max(1, config.num_days)),
                text=f"Simulating day {latest_day} of {config.num_days}",
            )
            with metrics_placeholder.container():
                render_summary_cards(snapshot)
            with chart_placeholder.container():
                render_primary_chart(snapshot, chart_key=f"live_primary_{latest_day}")
        if latest_day < config.num_days and config.refresh_interval > 0:
            time.sleep(config.refresh_interval)

    progress.progress(1.0, text="Simulation complete")
    return result


def render_result_dashboard(result: dict[str, Any]) -> None:
    render_summary_cards(result)
    render_primary_chart(result, chart_key="latest_primary_chart")

    chart_tabs = st.tabs(["Detailed Time Series", "Counts", "Final Distributions", "Raw Aggregate Data"])
    with chart_tabs[0]:
        render_detail_charts(result)
    with chart_tabs[1]:
        render_count_chart(result)
    with chart_tabs[2]:
        render_distribution_charts(result)
    with chart_tabs[3]:
        st.dataframe(aggregate_df(result), use_container_width=True, hide_index=True)


def render_summary_cards(result: dict[str, Any]) -> None:
    summary = result.get("final_summary", {})
    row = aggregate_df(result).tail(1)
    current_day = int(summary.get("final_day", 0))

    st.caption(f"Current day: {current_day}")
    cols = st.columns(4)
    cols[0].metric("Avg stress", format_metric(summary.get("final_average_stress")))
    cols[1].metric("Avg burnout", format_metric(summary.get("final_average_burnout")))
    cols[2].metric("Avg productivity", format_metric(summary.get("final_average_productivity")))
    cols[3].metric("Avg emotion", format_metric(summary.get("final_average_emotion")))

    cols = st.columns(4)
    cols[0].metric("Burnout threshold count", int(summary.get("burned_out_count", 0)))
    cols[1].metric("Turnover count", int(summary.get("total_turnover", 0)))
    cols[2].metric("Avg work-life balance", format_metric(summary.get("final_average_work_life_balance")))
    cols[3].metric("Avg job satisfaction", format_metric(summary.get("final_average_satisfaction")))

    if not row.empty and row.iloc[0].get("events"):
        st.caption(f"Latest event notes: {row.iloc[0]['events']}")


def render_primary_chart(result: dict[str, Any], chart_key: str) -> None:
    df = aggregate_df(result)
    if df.empty:
        return

    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for column, label, color in [
            ("average_stress", "Stress", "#d95f02"),
            ("average_burnout", "Burnout", "#7570b3"),
            ("average_productivity", "Productivity", "#1b9e77"),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=df["day"],
                    y=df[column],
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=3),
                )
            )
        fig.update_layout(
            title="Stress, burnout, and productivity over time",
            yaxis=dict(range=[0, 1]),
            xaxis_title="Day",
            yaxis_title="Normalized value",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=70, b=20),
        )
        st.plotly_chart(fig, use_container_width=True, key=chart_key)
    else:
        st.line_chart(df.set_index("day")[["average_stress", "average_burnout", "average_productivity"]])


def render_detail_charts(result: dict[str, Any]) -> None:
    df = aggregate_df(result)
    if df.empty:
        return

    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for column, label in [
            ("average_emotion", "Emotional state"),
            ("average_satisfaction", "Job satisfaction"),
            ("average_work_life_balance", "Work-life balance"),
            ("average_energy", "Energy/recovery"),
        ]:
            fig.add_trace(go.Scatter(x=df["day"], y=df[column], mode="lines", name=label))
        fig.update_layout(
            title="Supporting well-being metrics",
            xaxis_title="Day",
            yaxis_title="Value",
            margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True, key="detail_metrics")
    else:
        st.line_chart(
            df.set_index("day")[
                [
                    "average_emotion",
                    "average_satisfaction",
                    "average_work_life_balance",
                    "average_energy",
                ]
            ]
        )


def render_count_chart(result: dict[str, Any]) -> None:
    df = aggregate_df(result)
    if df.empty:
        return

    columns = ["burned_out_count", "turnover_count", "active_employee_count"]
    if PLOTLY_AVAILABLE:
        fig = go.Figure()
        for column in columns:
            fig.add_trace(go.Scatter(x=df["day"], y=df[column], mode="lines", name=column.replace("_", " ").title()))
        fig.update_layout(title="Burnout, turnover, and active employee counts", xaxis_title="Day")
        st.plotly_chart(fig, use_container_width=True, key="count_metrics")
    else:
        st.line_chart(df.set_index("day")[columns])


def render_distribution_charts(result: dict[str, Any]) -> None:
    final_df = pd.DataFrame(result.get("final_agent_states", []))
    if final_df.empty:
        st.write("No final agent states available.")
        return

    active_df = final_df[final_df["active"] == True]
    if active_df.empty:
        st.write("No active employees remain at the end of the run.")
        return

    cols = st.columns(3)
    for col, metric_name in zip(cols, ["stress", "burnout", "productivity"]):
        with col:
            if PLOTLY_AVAILABLE:
                fig = px.histogram(active_df, x=metric_name, nbins=12, range_x=[0, 1], title=metric_name.title())
                fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig, use_container_width=True, key=f"dist_{metric_name}")
            else:
                st.bar_chart(active_df[metric_name])


def render_comparison_tab(config: SimulationConfig) -> None:
    st.subheader("Scenario comparison")
    st.caption("Comparison uses the same seed and run controls for each selected preset.")
    default_scenarios = [
        "Balanced baseline",
        "Supportive management + flexible schedule",
        "Authoritarian management + overtime",
        "Toxic workplace",
    ]
    selected = st.multiselect(
        "Scenarios to compare",
        list(PRESET_SCENARIOS.keys()),
        default=default_scenarios,
    )

    if st.button("Run scenario comparison", type="primary"):
        if not selected:
            st.warning("Select at least one scenario.")
        else:
            comparison_rows = []
            progress = st.progress(0, text="Starting comparison")
            base = SimulationConfig(
                num_agents=config.num_agents,
                num_days=config.num_days,
                random_seed=config.random_seed,
                run_live=False,
                collect_per_agent_history=False,
                enable_emotional_contagion=config.enable_emotional_contagion,
                enable_turnover=config.enable_turnover,
                replace_after_turnover=config.replace_after_turnover,
                enable_random_life_events=config.enable_random_life_events,
            )
            for index, scenario_name in enumerate(selected, start=1):
                scenario_config = get_scenario_config(scenario_name, base)
                result = SimulationEngine(scenario_config).run()
                summary = result["final_summary"]
                comparison_rows.append(
                    {
                        "scenario": scenario_name,
                        "final_average_burnout": summary["final_average_burnout"],
                        "final_average_stress": summary["final_average_stress"],
                        "final_average_productivity": summary["final_average_productivity"],
                        "total_turnover": summary["total_turnover"],
                        "cumulative_burnout_auc": summary["cumulative_burnout"],
                        "lowest_productivity": summary["lowest_productivity"],
                    }
                )
                progress.progress(index / len(selected), text=f"Completed {scenario_name}")
            comparison_df = pd.DataFrame(comparison_rows)
            st.session_state.comparison_result = comparison_df
            progress.progress(1.0, text="Comparison complete")

    comparison_df = st.session_state.get("comparison_result")
    if comparison_df is not None and not comparison_df.empty:
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        if PLOTLY_AVAILABLE:
            metric = st.selectbox(
                "Comparison metric",
                [
                    "final_average_burnout",
                    "final_average_stress",
                    "final_average_productivity",
                    "total_turnover",
                    "cumulative_burnout_auc",
                    "lowest_productivity",
                ],
            )
            fig = px.bar(comparison_df, x="scenario", y=metric, color="scenario", title=metric.replace("_", " ").title())
            fig.update_layout(showlegend=False, xaxis_title="", yaxis_title=metric.replace("_", " ").title())
            st.plotly_chart(fig, use_container_width=True, key="comparison_bar")
        else:
            st.bar_chart(comparison_df.set_index("scenario"))


def render_export_tab() -> None:
    st.subheader("Export latest run")
    result = st.session_state.get("latest_result")
    if not result:
        st.write("Run a simulation first to generate exportable results.")
        return

    summary = result.get("final_summary", {})
    st.write(
        f"Latest run: {result.get('scenario_name')} | seed {result.get('seed')} | "
        f"final burnout {summary.get('final_average_burnout', 0.0):.3f}"
    )

    if st.button("Generate export files", type="primary"):
        paths = save_export_bundle(result)
        st.session_state.export_paths = paths
        st.success("Exports saved to /exports.")

    paths = st.session_state.get("export_paths")
    if paths:
        render_download_buttons(paths)


def render_download_buttons(paths: dict[str, Any]) -> None:
    flat_paths: list[Path] = []
    for value in paths.values():
        if isinstance(value, list):
            flat_paths.extend(value)
        else:
            flat_paths.append(value)

    st.write("Saved files:")
    for path in flat_paths:
        st.code(str(path))

    columns = st.columns(4)
    mime_by_suffix = {
        ".json": "application/json",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".png": "image/png",
        ".zip": "application/zip",
    }
    for index, path in enumerate(flat_paths):
        if not path.exists():
            continue
        with columns[index % len(columns)]:
            st.download_button(
                label=f"Download {path.suffix.upper().strip('.')}",
                data=path.read_bytes(),
                file_name=path.name,
                mime=mime_by_suffix.get(path.suffix, "application/octet-stream"),
                key=f"download_{path.name}",
            )


def render_about_tab() -> None:
    st.subheader("Model framing")
    st.write(
        "AWDS is an exploratory, parameter-driven agent-based simulation. "
        "It creates synthetic trajectories for stress, burnout, productivity, emotion, "
        "recovery, job satisfaction, work-life balance, engagement, and turnover."
    )
    st.write(
        "Each tick represents one workday by default. Organizational policies, personal modifiers, "
        "social network effects, and random events update each employee agent. The same seed and "
        "same configuration produce the same output."
    )
    st.write(
        "The purpose is to observe comparative dynamics between scenarios and produce report-ready "
        "synthetic data. The output should not be presented as empirical evidence, prediction, or "
        "validation of real organizational claims."
    )

    st.markdown(
        """
        **Core update sequence**

        1. Organizational demand and resource modifiers are applied.
        2. Personal load and recovery are calculated for each employee.
        3. Neighbor emotional influence and social support are applied through a static network.
        4. Random personal or organizational events may affect the day.
        5. Stress, burnout, emotion, energy, productivity, satisfaction, and work-life balance are updated.
        6. Turnover is evaluated when stress or burnout crosses configured thresholds.
        """
    )


def aggregate_df(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result.get("aggregate_time_series", []))


def format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


if __name__ == "__main__":
    main()
