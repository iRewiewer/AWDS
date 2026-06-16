from __future__ import annotations

import json
import time
from dataclasses import fields
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from simulation.config import MANAGEMENT_STYLES, WORK_POLICIES, SimulationConfig
from simulation.engines import ENGINE_ALL, ENGINE_CUSTOM, ENGINE_OPTIONS, EngineLike, create_engine, selected_engine_names
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


CONFIG_PREFIX = "cfg_"
RANGE_PREFIX = "range_"
USER_PRESETS_PATH = Path("user_presets.json")
SLIDER_HARD_MIN = 0.0
SLIDER_HARD_MAX = 10.0

CONFIG_FIELDS = tuple(field.name for field in fields(SimulationConfig))

SLIDER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "refresh_interval": {
        "label": "Live refresh delay in seconds (lower = faster)",
        "min": 0.00,
        "max": 1.00,
        "hard_min": 0.00,
        "hard_max": 5.00,
        "step": 0.01,
        "help": "Delay between live chart updates. Lower values update faster but can make long simulations feel more CPU-heavy.",
    },
    "workload_intensity": {
        "label": "Workload intensity",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Overall amount of work expected from employees. Higher values increase job demands and stress.",
    },
    "deadline_pressure": {
        "label": "Deadline pressure",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How intense and frequent deadlines feel. Higher values increase stress and deadline-crunch effects.",
    },
    "autonomy_level": {
        "label": "Autonomy level",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How much control employees have over how work is done. Higher autonomy acts as a job resource.",
    },
    "management_support": {
        "label": "Management support",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How available and constructive management support is. Higher values reduce stress and improve satisfaction.",
    },
    "recognition_level": {
        "label": "Recognition/reward level",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How often good work is recognized. Higher values improve resources, satisfaction, and engagement.",
    },
    "role_clarity": {
        "label": "Role clarity",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How clear responsibilities and expectations are. Higher values reduce ambiguity-driven stress.",
    },
    "meeting_load": {
        "label": "Meeting load",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Time and attention consumed by meetings. Higher values add to job demands.",
    },
    "interruptions": {
        "label": "Interruptions/context switching",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How often employees are interrupted or forced to switch tasks. Higher values increase stress and reduce focus.",
    },
    "conflict_level": {
        "label": "Conflict level",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Level of interpersonal or organizational conflict. Higher conflict worsens emotion, satisfaction, and stress.",
    },
    "psychological_safety": {
        "label": "Psychological safety",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How safe employees feel raising concerns or making mistakes. Higher values act as a protective resource.",
    },
    "sleep_quality": {
        "label": "Average sleep quality",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Average non-work recovery from sleep. Higher values improve recovery and energy.",
    },
    "exercise_quality": {
        "label": "Exercise/habits quality",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Average health-supporting habits. Higher values improve recovery and resilience against stress.",
    },
    "family_responsibilities_load": {
        "label": "Family responsibilities load",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Non-work caring or household load. Higher values increase personal load.",
    },
    "personal_stress_baseline": {
        "label": "Personal stress baseline",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Background stress unrelated to work. Higher values raise each agent's personal load.",
    },
    "recovery_outside_work": {
        "label": "Recovery outside work",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Quality of time away from work. Higher values lower stress and burnout accumulation.",
    },
    "commute_duration_impact": {
        "label": "Commute duration impact",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How draining the commute is. Higher values add personal load, especially for commute-sensitive agents.",
    },
    "financial_pressure": {
        "label": "Financial pressure",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "External financial stress. Higher values increase personal load and stress.",
    },
    "health_variability": {
        "label": "Health variability",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How much health-related fluctuation agents experience. Higher values add more random personal load.",
    },
    "emotional_contagion_strength": {
        "label": "Emotional contagion strength",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How strongly neighbor emotions pull each agent's emotional state through the social network.",
    },
    "social_support_strength": {
        "label": "Social support strength",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How much positive neighbor emotion can reduce stress through social support.",
    },
    "conflict_propagation_strength": {
        "label": "Conflict propagation strength",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How much conflict pressure is amplified through the organization.",
    },
    "network_density": {
        "label": "Network density",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How connected the employee network is. Higher density gives more social influence paths.",
    },
    "team_cohesion": {
        "label": "Team cohesion",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "How cohesive the team feels. Higher values strengthen positive social support effects.",
    },
    "probability_negative_personal_event": {
        "label": "Probability of negative personal event per employee/day",
        "min": 0.0,
        "max": 0.20,
        "hard_min": 0.0,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "Daily probability that any active employee receives a negative personal event.",
    },
    "probability_positive_personal_event": {
        "label": "Probability of positive personal event per employee/day",
        "min": 0.0,
        "max": 0.20,
        "hard_min": 0.0,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "Daily probability that any active employee receives a positive personal event.",
    },
    "probability_organizational_crisis": {
        "label": "Probability of organizational crisis per day",
        "min": 0.0,
        "max": 0.20,
        "hard_min": 0.0,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "Daily probability of a broad negative organizational event that increases demands and worsens emotion.",
    },
    "probability_deadline_crunch": {
        "label": "Probability of deadline crunch per day",
        "min": 0.0,
        "max": 0.20,
        "hard_min": 0.0,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "Daily probability of a short-term deadline spike.",
    },
    "probability_recognition_event": {
        "label": "Probability of recognition/reward event per day",
        "min": 0.0,
        "max": 0.20,
        "hard_min": 0.0,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "Daily probability of a positive organization-wide recognition event.",
    },
    "event_impact_strength": {
        "label": "Event impact strength",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Magnitude of random personal and organizational events.",
    },
    "recovery_decay_rate": {
        "label": "Recovery decay rate",
        "min": 0.05,
        "max": 0.98,
        "hard_min": 0.01,
        "hard_max": 1.0,
        "step": 0.01,
        "help": "How quickly lingering event effects fade. Lower values fade faster.",
    },
    "burnout_threshold": {
        "label": "Burnout threshold",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Burnout level at which an employee counts as burned out and may become more likely to leave.",
    },
    "stress_threshold": {
        "label": "Stress threshold",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Stress level at which turnover risk can start increasing.",
    },
    "turnover_probability_above_threshold": {
        "label": "Turnover probability above threshold",
        "min": 0.0,
        "max": 0.30,
        "hard_min": 0.0,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "Base daily leaving probability after stress or burnout crosses a configured threshold.",
    },
    "new_employee_onboarding_productivity_penalty": {
        "label": "New employee onboarding productivity penalty",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Temporary productivity reduction for replacement employees while they ramp up.",
    },
    "team_disruption_penalty_after_turnover": {
        "label": "Team disruption penalty after turnover",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "help": "Temporary productivity and emotion penalty after someone leaves.",
    },
    "stress_scale": {
        "label": "Stress update scale",
        "min": 0.01,
        "max": 0.20,
        "hard_min": 0.001,
        "hard_max": 1.0,
        "step": 0.005,
        "help": "How strongly daily stress calculations move the stress state. Higher values create faster trajectories.",
    },
    "burnout_accumulation_rate": {
        "label": "Burnout accumulation rate",
        "min": 0.005,
        "max": 0.120,
        "hard_min": 0.001,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "How quickly high stress accumulates into burnout.",
    },
    "burnout_recovery_rate": {
        "label": "Burnout recovery rate",
        "min": 0.001,
        "max": 0.080,
        "hard_min": 0.0,
        "hard_max": 1.0,
        "step": 0.001,
        "help": "How quickly recovery can reduce burnout.",
    },
}

FIELD_HELP: dict[str, str] = {
    "num_agents": "Number of employee agents simulated.",
    "num_days": "Number of simulated workdays. Higher values take longer but let slow burnout dynamics emerge.",
    "random_seed": "Reproducibility seed. Same seed plus same settings gives the same result.",
    "engine_mode": "Choose the custom NumPy engine, the Mesa-backed engine, or run both engines sequentially for comparison.",
    "run_live": "When enabled, the dashboard advances in chunks and updates charts while the run is in progress.",
    "collect_per_agent_history": "Stores every agent state at every day for raw exports. This can get large.",
    "enable_emotional_contagion": "Allows emotion to spread through colleague relationships.",
    "enable_turnover": "Turnover means employees leaving the simulated organization after high stress or burnout risk.",
    "replace_after_turnover": "Hires replacements after employees leave. Replacements have a temporary onboarding productivity penalty.",
    "enable_random_life_events": "Enables random personal and organizational events during the run.",
    "management_style": "Applies built-in adjustments to support, autonomy, conflict, clarity, and pressure.",
    "work_policy": "Applies built-in adjustments for overtime, flexibility, commute impact, and work-life balance.",
    "close_colleagues_per_agent": "Minimum number of close colleague connections for each agent in the social network.",
    "event_duration": "How many days random event effects linger before decaying.",
    "replacement_delay": "Days between an employee leaving and a replacement being hired.",
}


def main() -> None:
    inject_css()
    initialise_state()

    st.title("Adaptive Workplace Dynamics Simulator")
    st.caption("Exploratory synthetic agent-based workplace simulation. Outputs are model-generated, not empirical findings.")

    config, actions = render_sidebar()
    process_sidebar_actions(config, actions)

    run_tab, compare_tab, export_tab, about_tab = st.tabs(
        ["Run Simulation", "Compare Scenarios", "Export Results", "About Model"]
    )

    with run_tab:
        render_run_tab(config)

    with compare_tab:
        render_comparison_tab(config)

    with export_tab:
        render_export_tab()

    with about_tab:
        render_about_tab()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:has(.awds-sticky-label) {
            position: sticky;
            top: 0.5rem;
            z-index: 1000;
            background: rgba(38, 39, 48, 0.72);
            border: 1px solid rgba(250, 250, 250, 0.14);
            border-radius: 10px;
            padding: 0.65rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
            backdrop-filter: blur(6px);
        }
        .awds-sticky-label {
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            margin-bottom: 0.5rem;
            opacity: 0.82;
            text-transform: uppercase;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialise_state() -> None:
    if "settings_initialised" not in st.session_state:
        apply_config_to_session(get_scenario_config("Balanced baseline"))
        st.session_state.settings_initialised = True
        st.session_state.active_preset_label = "Factory: Balanced baseline"

    st.session_state.setdefault("run_history", [])
    st.session_state.setdefault("export_history", {})
    st.session_state.setdefault("latest_result", None)
    st.session_state.setdefault("latest_result_group", [])
    st.session_state.setdefault("active_engine", None)
    st.session_state.setdefault("active_run_status", "idle")
    st.session_state.setdefault("active_run_id", None)
    st.session_state.setdefault("engine_mode", ENGINE_CUSTOM)

    for field_name, definition in SLIDER_DEFINITIONS.items():
        min_key = slider_range_key(field_name, "min")
        max_key = slider_range_key(field_name, "max")
        st.session_state.setdefault(min_key, float(definition["min"]))
        st.session_state.setdefault(max_key, float(definition["max"]))


def render_sidebar() -> tuple[SimulationConfig, dict[str, bool]]:
    st.sidebar.header("Configuration")
    render_preset_controls()

    actions = render_action_panel()

    with st.sidebar.expander("Simulation controls", expanded=True):
        st.selectbox(
            "Simulation engine",
            ENGINE_OPTIONS,
            key="engine_mode",
            help=FIELD_HELP["engine_mode"],
        )
        number_input_config("Number of agents", "num_agents", min_value=5, step=5, help_text=FIELD_HELP["num_agents"])
        number_input_config("Number of simulated days", "num_days", min_value=1, step=30, help_text=FIELD_HELP["num_days"])
        number_input_config("Random seed", "random_seed", min_value=0, max_value=2_147_483_647, step=1, help_text=FIELD_HELP["random_seed"])
        config_slider("refresh_interval")
        checkbox_config("Run live", "run_live", FIELD_HELP["run_live"])
        if st.session_state.get("engine_mode") == ENGINE_ALL:
            st.caption("All engines mode runs Custom and Mesa sequentially; live pause/resume is disabled for that run.")
        checkbox_config("Collect per-agent history", "collect_per_agent_history", FIELD_HELP["collect_per_agent_history"])
        checkbox_config("Enable emotional contagion", "enable_emotional_contagion", FIELD_HELP["enable_emotional_contagion"])
        checkbox_config("Enable turnover", "enable_turnover", FIELD_HELP["enable_turnover"])
        checkbox_config("Replace employees after turnover", "replace_after_turnover", FIELD_HELP["replace_after_turnover"])
        checkbox_config("Enable random life events", "enable_random_life_events", FIELD_HELP["enable_random_life_events"])

    with st.sidebar.expander("Organizational modifiers", expanded=True):
        selectbox_config("Management style", "management_style", MANAGEMENT_STYLES, FIELD_HELP["management_style"])
        selectbox_config("Work policy", "work_policy", WORK_POLICIES, FIELD_HELP["work_policy"])
        for field_name in (
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
        ):
            config_slider(field_name)

    with st.sidebar.expander("Personal/lifestyle modifiers"):
        for field_name in (
            "sleep_quality",
            "exercise_quality",
            "family_responsibilities_load",
            "personal_stress_baseline",
            "recovery_outside_work",
            "commute_duration_impact",
            "financial_pressure",
            "health_variability",
        ):
            config_slider(field_name)

    with st.sidebar.expander("Social/network modifiers"):
        for field_name in (
            "emotional_contagion_strength",
            "social_support_strength",
            "conflict_propagation_strength",
            "network_density",
        ):
            config_slider(field_name)
        max_colleagues = max(1, int(state_value("num_agents")) - 1)
        current_colleagues = min(int(state_value("close_colleagues_per_agent")), max_colleagues)
        st.session_state[config_key("close_colleagues_per_agent")] = current_colleagues
        number_input_config(
            "Number of close colleagues per agent",
            "close_colleagues_per_agent",
            min_value=1,
            max_value=max_colleagues,
            step=1,
            help_text=FIELD_HELP["close_colleagues_per_agent"],
        )
        config_slider("team_cohesion")

    with st.sidebar.expander("Random event modifiers"):
        for field_name in (
            "probability_negative_personal_event",
            "probability_positive_personal_event",
            "probability_organizational_crisis",
            "probability_deadline_crunch",
            "probability_recognition_event",
            "event_impact_strength",
        ):
            config_slider(field_name)
        number_input_config("Event duration", "event_duration", min_value=1, step=1, help_text=FIELD_HELP["event_duration"])
        config_slider("recovery_decay_rate")

    with st.sidebar.expander("Turnover/model modifiers"):
        st.caption("Turnover means simulated employees leaving after high stress or burnout risk.")
        for field_name in (
            "burnout_threshold",
            "stress_threshold",
            "turnover_probability_above_threshold",
        ):
            config_slider(field_name)
        number_input_config("Replacement delay", "replacement_delay", min_value=0, step=1, help_text=FIELD_HELP["replacement_delay"])
        for field_name in (
            "new_employee_onboarding_productivity_penalty",
            "team_disruption_penalty_after_turnover",
            "stress_scale",
            "burnout_accumulation_rate",
            "burnout_recovery_rate",
        ):
            config_slider(field_name)

    render_slider_range_editor()
    return config_from_session(), actions


def render_preset_controls() -> None:
    user_presets = load_user_presets()
    options = [f"Factory: {name}" for name in PRESET_SCENARIOS] + [f"User: {name}" for name in user_presets]
    current_label = st.session_state.get("active_preset_label", "Factory: Balanced baseline")
    selected_index = options.index(current_label) if current_label in options else 0

    with st.sidebar.expander("Presets", expanded=True):
        selected = st.selectbox(
            "Preset library",
            options,
            index=selected_index,
            help="Selecting a preset only previews it here. Use Apply preset to copy it into the controls below.",
        )
        preset_cols = st.columns(2)
        apply_clicked = preset_cols[0].button("Apply preset", width="stretch")
        delete_clicked = False
        if selected.startswith("User: "):
            delete_clicked = preset_cols[1].button("Delete user preset", width="stretch")
        else:
            preset_cols[1].caption("Factory preset")

        save_name = st.text_input(
            "Save current settings as user preset",
            value="",
            placeholder="Preset name",
            help="Stores the current sidebar settings in user_presets.json.",
        )
        save_clicked = st.button("Save as preset", width="stretch")

        if apply_clicked:
            apply_preset(selected, user_presets)
            st.rerun()
        if delete_clicked:
            delete_user_preset(selected.removeprefix("User: "), user_presets)
            st.rerun()
        if save_clicked:
            if not save_name.strip():
                st.warning("Enter a preset name first.")
            else:
                save_current_user_preset(save_name.strip(), user_presets)
                st.success(f"Saved user preset: {save_name.strip()}")
                st.rerun()

        st.caption(f"Applied preset: {st.session_state.get('active_preset_label', 'Custom settings')}")


def render_action_panel() -> dict[str, bool]:
    status = st.session_state.get("active_run_status", "idle")
    actions = {"run": False, "toggle_pause": False, "clear": False}
    with st.sidebar.container():
        st.markdown('<div class="awds-sticky-label">Run controls</div>', unsafe_allow_html=True)
        actions["run"] = st.button("Run simulation", type="primary", width="stretch")
        if status == "running":
            actions["toggle_pause"] = st.button("Pause live run", width="stretch")
        elif status == "paused":
            actions["toggle_pause"] = st.button("Resume live run", width="stretch")
        else:
            actions["clear"] = st.button("Clear displayed run", width="stretch")
    return actions


def render_slider_range_editor() -> None:
    with st.sidebar.expander("Advanced slider ranges"):
        labels = {definition["label"]: field_name for field_name, definition in SLIDER_DEFINITIONS.items()}
        selected_label = st.selectbox(
            "Slider",
            list(labels.keys()),
        )
        field_name = labels[selected_label]
        definition = SLIDER_DEFINITIONS[field_name]
        hard_min = SLIDER_HARD_MIN
        hard_max = SLIDER_HARD_MAX
        min_key = slider_range_key(field_name, "min")
        max_key = slider_range_key(field_name, "max")
        current_min = float(st.session_state[min_key])
        current_max = float(st.session_state[max_key])
        edited_min = st.number_input("Visible minimum", min_value=hard_min, max_value=hard_max, value=current_min, step=float(definition["step"]), key=f"edit_{min_key}")
        edited_max = st.number_input("Visible maximum", min_value=hard_min, max_value=hard_max, value=current_max, step=float(definition["step"]), key=f"edit_{max_key}")
        cols = st.columns(2)
        if cols[0].button("Apply range", width="stretch"):
            if edited_min >= edited_max:
                st.warning("Minimum must be lower than maximum.")
            else:
                st.session_state[min_key] = float(edited_min)
                st.session_state[max_key] = float(edited_max)
                current_value = float(state_value(field_name))
                st.session_state[config_key(field_name)] = min(max(current_value, float(edited_min)), float(edited_max))
                st.rerun()
        if cols[1].button("Reset range", width="stretch"):
            st.session_state[min_key] = float(definition["min"])
            st.session_state[max_key] = float(definition["max"])
            st.rerun()
        st.caption("Hard bounds: 0 to 10")


def config_slider(field_name: str) -> float:
    definition = SLIDER_DEFINITIONS[field_name]
    min_value = float(st.session_state[slider_range_key(field_name, "min")])
    max_value = float(st.session_state[slider_range_key(field_name, "max")])
    step = float(definition["step"])
    current = float(state_value(field_name))
    current = min(max(current, min_value), max_value)
    st.session_state[config_key(field_name)] = current
    kwargs = keyed_default_kwargs(field_name, current)
    return st.slider(definition["label"], min_value=min_value, max_value=max_value, step=step, key=config_key(field_name), help=definition["help"], **kwargs)


def number_input_config(
    label: str,
    field_name: str,
    min_value: int | None = None,
    max_value: int | None = None,
    step: int = 1,
    help_text: str | None = None,
) -> int:
    kwargs = keyed_default_kwargs(field_name, int(state_value(field_name)))
    return st.number_input(label, min_value=min_value, max_value=max_value, step=step, key=config_key(field_name), help=help_text, **kwargs)


def checkbox_config(label: str, field_name: str, help_text: str) -> bool:
    kwargs = keyed_default_kwargs(field_name, bool(state_value(field_name)))
    return st.checkbox(label, key=config_key(field_name), help=help_text, **kwargs)


def selectbox_config(label: str, field_name: str, options: tuple[str, ...], help_text: str) -> str:
    kwargs: dict[str, Any] = {}
    if config_key(field_name) not in st.session_state:
        kwargs["index"] = options.index(str(state_value(field_name)))
    return st.selectbox(label, options, key=config_key(field_name), help=help_text, **kwargs)


def keyed_default_kwargs(field_name: str, value: Any) -> dict[str, Any]:
    if config_key(field_name) in st.session_state:
        return {}
    return {"value": value}


def process_sidebar_actions(config: SimulationConfig, actions: dict[str, bool]) -> None:
    if actions["run"]:
        st.session_state.export_history = {}
        start_run(config)
    if actions["toggle_pause"]:
        if st.session_state.get("active_run_status") == "running":
            st.session_state.active_run_status = "paused"
        elif st.session_state.get("active_run_status") == "paused":
            st.session_state.active_run_status = "running"
        st.rerun()
    if actions["clear"]:
        st.session_state.latest_result = None
        st.session_state.latest_result_group = []
        st.session_state.export_history = {}


def start_run(config: SimulationConfig) -> None:
    engine_names = selected_engine_names(st.session_state.get("engine_mode", ENGINE_CUSTOM))
    if config.run_live and len(engine_names) == 1:
        engine = create_engine(config, engine_names[0])
        snapshot = engine.snapshot()
        st.session_state.active_engine = engine
        st.session_state.active_run_status = "running"
        st.session_state.active_run_id = make_run_id(snapshot)
        st.session_state.latest_result = snapshot
        st.session_state.latest_result_group = [snapshot]
    else:
        run_config = config.with_overrides(run_live=False) if len(engine_names) > 1 else config
        st.session_state.active_run_id = None
        with st.spinner(run_spinner_text(engine_names)):
            results = [create_engine(run_config, engine_name).run() for engine_name in engine_names]
        for result in results:
            store_completed_run(result, update_latest=False)
        st.session_state.latest_result = results[-1] if results else None
        st.session_state.latest_result_group = results
        st.session_state.active_engine = None
        st.session_state.active_run_status = "idle"
        st.session_state.active_run_id = None


def render_run_tab(config: SimulationConfig) -> None:
    active_engine = st.session_state.get("active_engine")
    if active_engine is not None and st.session_state.get("active_run_status") == "running":
        advance_live_run(active_engine)

    latest_group = latest_results()
    result_for_header = latest_group[0] if latest_group else st.session_state.get("latest_result")
    header_config = result_for_header.get("config", {}) if result_for_header else config.to_dict()
    scenario = result_for_header.get("scenario_name", config.scenario_name) if result_for_header else config.scenario_name
    engine_label = engine_group_label(latest_group) if latest_group else st.session_state.get("engine_mode", ENGINE_CUSTOM)

    top_cols = st.columns([2, 1, 1, 1, 1])
    top_cols[0].subheader(scenario)
    top_cols[1].metric("Seed", header_config.get("random_seed", config.random_seed))
    top_cols[2].metric("Days", header_config.get("num_days", config.num_days))
    top_cols[3].metric("Engine", engine_label)
    top_cols[4].metric("Run status", st.session_state.get("active_run_status", "idle").title())

    latest_result = st.session_state.get("latest_result")
    if len(latest_group) > 1:
        render_engine_group_dashboard(latest_group)
    elif latest_result:
        render_result_dashboard(latest_result)
    else:
        st.write("Apply a preset or adjust parameters in the sidebar, then run the simulation.")

    if active_engine is not None and st.session_state.get("active_run_status") == "running":
        delay = float(active_engine.config.refresh_interval)
        if delay > 0:
            time.sleep(delay)
        st.rerun()


def advance_live_run(engine: EngineLike) -> None:
    days_remaining = max(0, engine.config.num_days - engine.current_day)
    if days_remaining == 0:
        finish_live_run(engine.result())
        return

    steps_per_render = max(1, min(25, engine.config.num_days // 120 or 1))
    for _ in range(min(steps_per_render, days_remaining)):
        snapshot = engine.step()
    st.session_state.latest_result = snapshot
    st.session_state.latest_result_group = [snapshot]
    if engine.current_day >= engine.config.num_days:
        finish_live_run(engine.result())


def finish_live_run(result: dict[str, Any]) -> None:
    store_completed_run(result)
    st.session_state.latest_result_group = [result]
    st.session_state.active_engine = None
    st.session_state.active_run_status = "idle"
    st.session_state.active_run_id = None


def run_spinner_text(engine_names: tuple[str, ...]) -> str:
    if len(engine_names) == 1:
        return f"Running synthetic simulation ({engine_names[0]})..."
    return "Running Custom and Mesa simulations..."


def latest_results() -> list[dict[str, Any]]:
    group = st.session_state.get("latest_result_group") or []
    return [result for result in group if isinstance(result, dict)]


def engine_group_label(results: list[dict[str, Any]]) -> str:
    engines = [result_engine(result) for result in results]
    return " + ".join(engines) if engines else st.session_state.get("engine_mode", ENGINE_CUSTOM)


def result_engine(result: dict[str, Any]) -> str:
    engine = result.get("engine")
    return str(engine) if engine else ENGINE_CUSTOM


def render_engine_group_dashboard(results: list[dict[str, Any]]) -> None:
    st.subheader("Engine comparison")
    rows = []
    for result in results:
        summary = result.get("final_summary", {})
        rows.append(
            {
                "engine": result_engine(result),
                "final_average_stress": summary.get("final_average_stress"),
                "final_average_burnout": summary.get("final_average_burnout"),
                "final_average_productivity": summary.get("final_average_productivity"),
                "total_turnover": summary.get("total_turnover"),
                "lowest_productivity": summary.get("lowest_productivity"),
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    render_engine_overlay_chart(results)

    labels = [f"{result_engine(result)} detail" for result in results]
    if st.session_state.get("latest_engine_detail") not in labels:
        st.session_state.latest_engine_detail = labels[0]
    selected_label = st.selectbox("Detailed result", labels, key="latest_engine_detail")
    selected_result = results[labels.index(selected_label)]
    render_result_dashboard(selected_result)


def render_engine_overlay_chart(results: list[dict[str, Any]]) -> None:
    if not PLOTLY_AVAILABLE:
        return

    fig = go.Figure()
    colors = {
        "average_stress": "#d95f02",
        "average_burnout": "#7570b3",
        "average_productivity": "#1b9e77",
    }
    dashes = ["solid", "dash", "dot", "dashdot"]
    for index, result in enumerate(results):
        df = aggregate_df(result)
        if df.empty:
            continue
        for column, label in [
            ("average_stress", "Stress"),
            ("average_burnout", "Burnout"),
            ("average_productivity", "Productivity"),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=df["day"],
                    y=df[column],
                    mode="lines",
                    name=f"{result_engine(result)} {label}",
                    line=dict(color=colors[column], width=3, dash=dashes[index % len(dashes)]),
                )
            )
    fig.update_layout(
        title="Engine overlay",
        yaxis=dict(range=[0, 1]),
        xaxis_title="Day",
        yaxis_title="Normalized value",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=70, b=20),
    )
    st.plotly_chart(fig, width="stretch", key="engine_overlay_chart")


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
        st.dataframe(aggregate_df(result), width="stretch", hide_index=True)


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
    cols[1].metric("Turnover count", int(summary.get("total_turnover", 0)), help="Turnover is the cumulative number of simulated employees who left after stress or burnout risk became high enough.")
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
        st.plotly_chart(fig, width="stretch", key=chart_key)
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
        st.plotly_chart(fig, width="stretch", key="detail_metrics")
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
        st.plotly_chart(fig, width="stretch", key="count_metrics")
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
                st.plotly_chart(fig, width="stretch", key=f"dist_{metric_name}")
            else:
                st.bar_chart(active_df[metric_name])


def render_comparison_tab(config: SimulationConfig) -> None:
    st.subheader("Scenario comparison")
    engine_names = selected_engine_names(st.session_state.get("engine_mode", ENGINE_CUSTOM))
    st.caption("Comparison uses the same seed, run controls, and selected simulation engine setting for each preset.")
    user_presets = load_user_presets()
    all_options = [f"Factory: {name}" for name in PRESET_SCENARIOS] + [f"User: {name}" for name in user_presets]
    default_scenarios = [
        "Factory: Balanced baseline",
        "Factory: Supportive management + flexible schedule",
        "Factory: Authoritarian management + overtime",
        "Factory: Toxic workplace",
    ]
    selected = st.multiselect(
        "Scenarios to compare",
        all_options,
        default=[name for name in default_scenarios if name in all_options],
    )

    if st.button("Run scenario comparison", type="primary"):
        if not selected:
            st.warning("Select at least one scenario.")
        else:
            comparison_rows = []
            total_runs = len(selected) * len(engine_names)
            completed_runs = 0
            progress = st.progress(0, text="Starting comparison")
            for preset_label in selected:
                scenario_config = config_for_preset_label(preset_label, config, user_presets)
                scenario_config = scenario_config.with_overrides(
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
                for engine_name in engine_names:
                    result = create_engine(scenario_config, engine_name).run()
                    summary = result["final_summary"]
                    comparison_rows.append(
                        {
                            "scenario": preset_label,
                            "engine": result_engine(result),
                            "final_average_burnout": summary["final_average_burnout"],
                            "final_average_stress": summary["final_average_stress"],
                            "final_average_productivity": summary["final_average_productivity"],
                            "total_turnover": summary["total_turnover"],
                            "cumulative_burnout_auc": summary["cumulative_burnout"],
                            "lowest_productivity": summary["lowest_productivity"],
                        }
                    )
                    completed_runs += 1
                    progress.progress(
                        completed_runs / total_runs,
                        text=f"Completed {preset_label} ({engine_name})",
                    )
            comparison_df = pd.DataFrame(comparison_rows)
            st.session_state.comparison_result = comparison_df
            progress.progress(1.0, text="Comparison complete")

    comparison_df = st.session_state.get("comparison_result")
    if comparison_df is not None and not comparison_df.empty:
        st.dataframe(comparison_df, width="stretch", hide_index=True)
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
            fig = px.bar(
                comparison_df,
                x="scenario",
                y=metric,
                color="engine",
                barmode="group",
                title=metric.replace("_", " ").title(),
            )
            fig.update_layout(xaxis_title="", yaxis_title=metric.replace("_", " ").title())
            st.plotly_chart(fig, width="stretch", key="comparison_bar")
        else:
            st.bar_chart(comparison_df.set_index("scenario"))


def render_export_tab() -> None:
    st.subheader("Export runs")
    history = st.session_state.get("run_history", [])
    if not history:
        st.write("Run a simulation first to generate exportable results.")
        return

    st.caption("Completed runs are kept for this session. Open a drawer to prepare or download exports.")
    search_query = st.text_input(
        "Search export runs",
        placeholder="Search scenario, timestamp, seed, day, or run id",
        help="Filters the completed runs shown below.",
    )
    filtered_history = filter_export_history(history, search_query)
    if not filtered_history:
        st.warning("No completed runs match that search.")
        return

    for index, entry in enumerate(filtered_history):
        render_export_run_drawer(entry, expanded=index == 0)


def render_export_run_drawer(entry: dict[str, Any], expanded: bool = False) -> None:
    result = entry["result"]
    summary = result.get("final_summary", {})
    config = result.get("config", {})
    title = export_drawer_title(entry)

    with st.expander(title, expanded=expanded):
        st.caption("Run ID")
        st.code(entry["id"])

        meta_cols = st.columns(5)
        meta_cols[0].metric("Seed", result.get("seed", config.get("random_seed", "n/a")))
        meta_cols[1].metric("Days", summary.get("final_day", config.get("num_days", "n/a")))
        meta_cols[2].metric("Agents", config.get("num_agents", "n/a"))
        meta_cols[3].metric("Engine", result_engine(result))
        meta_cols[4].metric("Scenario", result.get("scenario_name", "AWDS run"))

        cols = st.columns(4)
        cols[0].metric("Final stress", format_metric(summary.get("final_average_stress")))
        cols[1].metric("Final burnout", format_metric(summary.get("final_average_burnout")))
        cols[2].metric("Final productivity", format_metric(summary.get("final_average_productivity")))
        cols[3].metric("Turnover", int(summary.get("total_turnover", 0)))

        export_history = st.session_state.setdefault("export_history", {})
        paths = export_history.get(entry["id"])
        if paths is None:
            if st.button("Prepare export files", type="primary", key=f"prepare_export_{entry['id']}"):
                paths = save_export_bundle(result)
                export_history[entry["id"]] = paths
                st.rerun()
            return

        st.caption("Export files are ready for this run.")
        render_export_menu(paths)


def render_export_menu(paths: dict[str, Any]) -> None:
    st.write("Download formats")
    top_cols = st.columns(4)
    download_path_button(top_cols[0], "JSON data", paths["json"], "application/json")
    download_path_button(top_cols[1], "CSV time series", paths["csv"], "text/csv")
    download_path_button(top_cols[2], "TXT summary", paths["txt"], "text/plain")
    download_path_button(top_cols[3], "ZIP bundle", paths["zip"], "application/zip")

    png_paths = paths.get("png", [])
    if png_paths:
        st.write("PNG charts")
        png_cols = st.columns(len(png_paths))
        for index, path in enumerate(png_paths):
            download_path_button(png_cols[index], path.stem.split("_")[-1].replace("-", " ").title(), path, "image/png")

    with st.expander("Saved file paths"):
        flat_paths = flatten_export_paths(paths)
        for path in flat_paths:
            st.code(str(path))


def download_path_button(column, label: str, path: Path, mime: str) -> None:
    if not path.exists():
        column.warning(f"Missing {path.name}")
        return
    column.download_button(
        label=label,
        data=path.read_bytes(),
        file_name=path.name,
        mime=mime,
        width="stretch",
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
        "Each simulated day applies organizational policies, personal modifiers, social network effects, "
        "and random events to every employee agent. The same seed and same configuration produce the same output."
    )
    st.write(
        "Turnover is the cumulative count of simulated employees who leave after stress or burnout risk crosses "
        "configured thresholds. If replacement is enabled, new employees enter after the replacement delay and "
        "temporarily carry an onboarding productivity penalty."
    )
    st.write(
        "The purpose is to observe comparative dynamics between scenarios and produce report-ready synthetic data. "
        "The output should not be presented as empirical evidence, prediction, or validation of real organizational claims."
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


def config_from_session() -> SimulationConfig:
    values = {}
    defaults = SimulationConfig().to_dict()
    for field_name in CONFIG_FIELDS:
        values[field_name] = st.session_state.get(config_key(field_name), defaults[field_name])
    values["num_agents"] = int(values["num_agents"])
    values["num_days"] = int(values["num_days"])
    values["random_seed"] = int(values["random_seed"])
    values["close_colleagues_per_agent"] = int(values["close_colleagues_per_agent"])
    values["event_duration"] = int(values["event_duration"])
    values["replacement_delay"] = int(values["replacement_delay"])
    return SimulationConfig(**values)


def apply_config_to_session(config: SimulationConfig) -> None:
    for key, value in config.to_dict().items():
        st.session_state[config_key(key)] = value


def config_key(field_name: str) -> str:
    return f"{CONFIG_PREFIX}{field_name}"


def slider_range_key(field_name: str, bound: str) -> str:
    return f"{RANGE_PREFIX}{field_name}_{bound}"


def state_value(field_name: str) -> Any:
    defaults = SimulationConfig().to_dict()
    return st.session_state.get(config_key(field_name), defaults[field_name])


def apply_preset(selected: str, user_presets: dict[str, dict[str, Any]]) -> None:
    config = config_for_preset_label(selected, config_from_session(), user_presets)
    apply_config_to_session(config)
    st.session_state.active_preset_label = selected


def config_for_preset_label(
    selected: str,
    base_config: SimulationConfig,
    user_presets: dict[str, dict[str, Any]],
) -> SimulationConfig:
    if selected.startswith("Factory: "):
        name = selected.removeprefix("Factory: ")
        return get_scenario_config(name, base_config)
    name = selected.removeprefix("User: ")
    raw = user_presets.get(name, {})
    cleaned = {key: raw[key] for key in CONFIG_FIELDS if key in raw}
    cleaned.setdefault("scenario_name", name)
    return base_config.with_overrides(**cleaned)


def load_user_presets() -> dict[str, dict[str, Any]]:
    if not USER_PRESETS_PATH.exists():
        return {}
    try:
        data = json.loads(USER_PRESETS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(name): values
        for name, values in data.items()
        if isinstance(values, dict)
    }


def write_user_presets(user_presets: dict[str, dict[str, Any]]) -> None:
    USER_PRESETS_PATH.write_text(json.dumps(user_presets, indent=2), encoding="utf-8")


def save_current_user_preset(name: str, user_presets: dict[str, dict[str, Any]]) -> None:
    config = config_from_session().with_overrides(scenario_name=name)
    user_presets[name] = config.to_dict()
    write_user_presets(user_presets)
    st.session_state.active_preset_label = f"User: {name}"


def delete_user_preset(name: str, user_presets: dict[str, dict[str, Any]]) -> None:
    user_presets.pop(name, None)
    write_user_presets(user_presets)
    st.session_state.active_preset_label = "Factory: Balanced baseline"


def store_completed_run(result: dict[str, Any], update_latest: bool = True) -> None:
    run_id = st.session_state.get("active_run_id") or make_run_id(result)
    label = make_run_label(result, run_id)
    completed_at = datetime.now().isoformat(timespec="seconds")
    history = [entry for entry in st.session_state.get("run_history", []) if entry["id"] != run_id]
    history.insert(0, {"id": run_id, "label": label, "completed_at": completed_at, "result": result})
    st.session_state.run_history = history[:25]
    if update_latest:
        st.session_state.latest_result = result


def make_run_id(result: dict[str, Any]) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    scenario = slugify(str(result.get("scenario_name", "awds-run")))
    engine = slugify(result_engine(result))
    return f"{scenario}-{engine}-seed-{result.get('seed', 'seed')}-{stamp}"


def make_run_label(result: dict[str, Any], run_id: str) -> str:
    summary = result.get("final_summary", {})
    scenario = result.get("scenario_name", "AWDS run")
    seed = result.get("seed", "seed")
    day = summary.get("final_day", result.get("config", {}).get("num_days", "?"))
    return f"{scenario} | {result_engine(result)} | seed {seed} | day {day}"


def export_drawer_title(entry: dict[str, Any]) -> str:
    result = entry["result"]
    summary = result.get("final_summary", {})
    scenario = result.get("scenario_name", "AWDS run")
    seed = result.get("seed", result.get("config", {}).get("random_seed", "n/a"))
    day = summary.get("final_day", result.get("config", {}).get("num_days", "n/a"))
    timestamp = readable_run_timestamp(entry)
    return f"{scenario} ({result_engine(result)}) - {timestamp} - seed {seed}, day {day}"


def filter_export_history(history: list[dict[str, Any]], search_query: str) -> list[dict[str, Any]]:
    query = search_query.strip().lower()
    if not query:
        return history
    return [
        entry
        for entry in history
        if query in export_entry_search_text(entry)
    ]


def export_entry_search_text(entry: dict[str, Any]) -> str:
    result = entry.get("result", {})
    summary = result.get("final_summary", {})
    config = result.get("config", {})
    parts = [
        str(entry.get("id", "")),
        str(entry.get("label", "")),
        readable_run_timestamp(entry),
        result_engine(result),
        str(result.get("scenario_name", "")),
        str(result.get("seed", "")),
        str(summary.get("final_day", "")),
        str(config.get("num_days", "")),
        str(config.get("num_agents", "")),
    ]
    return " ".join(parts).lower()


def readable_run_timestamp(entry: dict[str, Any]) -> str:
    completed_at = entry.get("completed_at")
    if isinstance(completed_at, str):
        try:
            return datetime.fromisoformat(completed_at).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    run_id = str(entry.get("id", ""))
    raw_stamp = run_id.rsplit("-", 1)[-1]
    try:
        return datetime.strptime(raw_stamp, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "Unknown time"


def flatten_export_paths(paths: dict[str, Any]) -> list[Path]:
    flat_paths: list[Path] = []
    for value in paths.values():
        if isinstance(value, list):
            flat_paths.extend(value)
        else:
            flat_paths.append(value)
    return flat_paths


def aggregate_df(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result.get("aggregate_time_series", []))


def format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


if __name__ == "__main__":
    main()
