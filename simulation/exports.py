"""Export helpers for report-ready AWDS outputs."""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .utils import serialisable, slugify


EXPORT_DIR = Path("exports")


def aggregate_dataframe(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result.get("aggregate_time_series", []))


def final_agents_dataframe(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result.get("final_agent_states", []))


def export_json(result: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(serialisable(result), handle, indent=2)
    return path


def export_csv(result: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    aggregate_dataframe(result).to_csv(path, index=False)
    return path


def export_txt_summary(result: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    config = result.get("config", {})
    summary = result.get("final_summary", {})
    scenario = result.get("scenario_name", "Unknown scenario")
    engine = result.get("engine", "Custom")
    seed = result.get("seed", config.get("random_seed", "unknown"))

    interpretation = _interpret_result(result)
    lines = [
        "Adaptive Workplace Dynamics Simulator - Synthetic Run Summary",
        "",
        f"Scenario name: {scenario}",
        f"Simulation engine: {engine}",
        f"Seed: {seed}",
        f"Number of agents: {config.get('num_agents')}",
        f"Number of simulated days: {config.get('num_days')}",
        "",
        "Main parameter values:",
        f"- Management style: {config.get('management_style')}",
        f"- Work policy: {config.get('work_policy')}",
        f"- Workload intensity: {config.get('workload_intensity')}",
        f"- Deadline pressure: {config.get('deadline_pressure')}",
        f"- Autonomy level: {config.get('autonomy_level')}",
        f"- Management support: {config.get('management_support')}",
        f"- Recognition/reward level: {config.get('recognition_level')}",
        f"- Psychological safety: {config.get('psychological_safety')}",
        f"- Emotional contagion enabled: {config.get('enable_emotional_contagion')}",
        f"- Turnover enabled: {config.get('enable_turnover')}",
        "",
        "Final metrics:",
        f"- Final average stress: {summary.get('final_average_stress', 0.0):.3f}",
        f"- Final average burnout: {summary.get('final_average_burnout', 0.0):.3f}",
        f"- Final average productivity: {summary.get('final_average_productivity', 0.0):.3f}",
        f"- Final average emotional state: {summary.get('final_average_emotion', 0.0):.3f}",
        f"- Final average job satisfaction: {summary.get('final_average_satisfaction', 0.0):.3f}",
        f"- Turnover count: {summary.get('total_turnover', 0)}",
        f"- Burnout threshold count: {summary.get('burned_out_count', 0)}",
        "",
        "Interpretation:",
        interpretation,
        "",
        "Important limitation:",
        "These outputs are synthetic, parameter-driven model outputs and do not represent empirical validation or real-world organizational findings.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def export_png_charts(result: dict[str, Any], output_dir: Path, filename_prefix: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mpl_config_dir = output_dir / ".matplotlib"
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config_dir))

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Matplotlib is required for PNG exports. Install dependencies from requirements.txt.") from exc

    df = aggregate_dataframe(result)
    final_df = final_agents_dataframe(result)
    paths: list[Path] = []

    timeseries_path = output_dir / f"{filename_prefix}_timeseries.png"
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    engine = result.get("engine", "Custom")
    fig.suptitle(f"{result.get('scenario_name', 'AWDS scenario')} ({engine}) - Synthetic Time Series")

    axes[0, 0].plot(df["day"], df["average_stress"], label="Stress", color="#d95f02")
    axes[0, 0].plot(df["day"], df["average_burnout"], label="Burnout", color="#7570b3")
    axes[0, 0].plot(df["day"], df["average_productivity"], label="Productivity", color="#1b9e77")
    axes[0, 0].set_title("Stress, burnout, and productivity")
    axes[0, 0].set_ylim(0, 1)
    axes[0, 0].legend()

    axes[0, 1].plot(df["day"], df["average_emotion"], label="Emotion", color="#66a61e")
    axes[0, 1].plot(df["day"], df["average_satisfaction"], label="Satisfaction", color="#e7298a")
    axes[0, 1].plot(df["day"], df["average_work_life_balance"], label="Work-life balance", color="#1f78b4")
    axes[0, 1].set_title("Emotion, satisfaction, and work-life balance")
    axes[0, 1].set_ylim(-1, 1)
    axes[0, 1].legend()

    axes[1, 0].plot(df["day"], df["burned_out_count"], label="Burned out count", color="#e31a1c")
    axes[1, 0].plot(df["day"], df["turnover_count"], label="Turnover count", color="#6a3d9a")
    axes[1, 0].plot(df["day"], df["active_employee_count"], label="Active employees", color="#33a02c")
    axes[1, 0].set_title("Counts over time")
    axes[1, 0].legend()

    axes[1, 1].axis("off")
    summary = result.get("final_summary", {})
    summary_text = "\n".join(
        [
            "Final summary",
            f"Stress: {summary.get('final_average_stress', 0.0):.3f}",
            f"Burnout: {summary.get('final_average_burnout', 0.0):.3f}",
            f"Productivity: {summary.get('final_average_productivity', 0.0):.3f}",
            f"Turnover: {summary.get('total_turnover', 0)}",
            "Synthetic simulation output.",
        ]
    )
    axes[1, 1].text(0.05, 0.95, summary_text, va="top", fontsize=12)
    fig.savefig(timeseries_path, dpi=180)
    plt.close(fig)
    paths.append(timeseries_path)

    if not final_df.empty:
        distributions_path = output_dir / f"{filename_prefix}_final_distributions.png"
        fig, axes = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
        fig.suptitle(f"{result.get('scenario_name', 'AWDS scenario')} ({engine}) - Final Agent Distributions")
        for axis, column, title, color in [
            (axes[0], "stress", "Stress", "#d95f02"),
            (axes[1], "burnout", "Burnout", "#7570b3"),
            (axes[2], "productivity", "Productivity", "#1b9e77"),
        ]:
            active_values = final_df.loc[final_df["active"] == True, column]
            axis.hist(active_values, bins=12, range=(0, 1), color=color, alpha=0.82)
            axis.set_title(title)
            axis.set_xlim(0, 1)
            axis.set_xlabel("Value")
            axis.set_ylabel("Employees")
        fig.savefig(distributions_path, dpi=180)
        plt.close(fig)
        paths.append(distributions_path)

    return paths


def export_zip(paths: list[Path], zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in paths:
            if path.exists():
                bundle.write(path, arcname=path.name)
    return zip_path


def save_export_bundle(result: dict[str, Any], export_dir: Path = EXPORT_DIR) -> dict[str, Path | list[Path]]:
    export_dir.mkdir(parents=True, exist_ok=True)
    scenario = slugify(str(result.get("scenario_name", "awds-run")))
    engine = slugify(str(result.get("engine", "custom")))
    seed = result.get("seed", result.get("config", {}).get("random_seed", "seed"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"{scenario}_{engine}_seed-{seed}_{stamp}"

    json_path = export_json(result, export_dir / f"{prefix}.json")
    csv_path = export_csv(result, export_dir / f"{prefix}.csv")
    txt_path = export_txt_summary(result, export_dir / f"{prefix}_summary.txt")
    png_paths = export_png_charts(result, export_dir, prefix)
    zip_path = export_zip([json_path, csv_path, txt_path, *png_paths], export_dir / f"{prefix}.zip")
    return {
        "json": json_path,
        "csv": csv_path,
        "txt": txt_path,
        "png": png_paths,
        "zip": zip_path,
    }


def _interpret_result(result: dict[str, Any]) -> str:
    summary = result.get("final_summary", {})
    stress = float(summary.get("final_average_stress", 0.0))
    burnout = float(summary.get("final_average_burnout", 0.0))
    productivity = float(summary.get("final_average_productivity", 0.0))
    turnover = int(summary.get("total_turnover", 0))
    scenario = result.get("scenario_name", "the selected scenario")

    if burnout >= 0.65 and productivity <= 0.45:
        direction = "produced a progressive increase in average stress and burnout, followed by weaker productivity."
    elif stress <= 0.40 and burnout <= 0.35 and productivity >= 0.60:
        direction = "kept average stress and burnout comparatively low while maintaining stronger productivity."
    elif turnover > 0 and burnout >= 0.50:
        direction = "generated elevated burnout and visible turnover pressure."
    else:
        direction = "produced mixed synthetic dynamics without a single dominant stress-productivity pattern."

    return (
        f"In this synthetic run, {scenario} {direction} "
        "This supports the internal behavior expected from the configured model, "
        "but does not represent empirical validation."
    )
