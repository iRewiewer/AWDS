# Adaptive Workplace Dynamics Simulator (AWDS)

AWDS is a Python/Streamlit prototype for running exploratory, synthetic agent-based workplace simulations. It models a small organization of employee agents with dynamic stress, burnout, productivity, emotional state, energy, job satisfaction, work-life balance, engagement, and turnover.

The prototype is intended for dissertation/report support. It does not validate real organizational claims and should not be described as empirical evidence or prediction.

## Features

- Streamlit dashboard with sidebar configuration controls
- Factory presets, local user presets, and manual parameter overrides
- Explicit `Apply preset` and `Save as preset` controls
- Advanced slider-range editor with visible min/max bounds
- Deterministic runs from configured random seeds
- Engine selector for the original custom NumPy engine, a Mesa-native engine, or both engines at once
- Sticky run controls with live-run pause/resume
- Scenario comparison mode using the same seed and selected engine mode
- Searchable export history drawers with run IDs, engine labels, JSON, CSV, TXT summary, PNG chart, and ZIP downloads saved under `exports/`
- Optional per-agent history collection for raw data exports

## Setup

Use Python 3.11 or newer.

```bash
pip install -r requirements.txt
```

You can install those dependencies in a virtual environment, a local Python install, or whatever environment you normally use.

## Run

```bash
streamlit run app.py
```

Or use the helper script for your OS:

```bash
./run.sh
```

```bat
run.bat
```

Then open the local Streamlit URL shown in the terminal.

## Project Structure

```text
app.py
run.sh
run.bat
simulation/
  config.py
  agent.py
  engine.py
  mesa_engine.py
  engines.py
  scenarios.py
  metrics.py
  exports.py
  utils.py
exports/
requirements.txt
user_presets.json  # created locally if you save custom presets
```

## Reproducibility

Every simulation uses the configured seed. The same seed, engine, and configuration reproduce the same aggregate time series. The same seed across different engines is not expected to produce identical trajectories because the custom engine and Mesa engine use different execution models.

## Local Presets

Factory presets are built into `simulation/scenarios.py`. User presets saved from the dashboard are stored in `user_presets.json`, which is intentionally ignored by git so local scenario experiments do not accidentally get committed.

## Dashboard Notes

The sidebar has a sticky `Run controls` panel so the run, pause/resume, and clear controls remain reachable while scrolling through parameters. Presets are not applied automatically when selected; choose a factory or user preset, then click `Apply preset`.

The `Simulation engine` selector can run the original custom engine, the Mesa-native engine, or `All engines`. `All engines` runs Custom and Mesa sequentially, stores both completed runs, and shows an overlay chart plus summary table for direct comparison. Live pause/resume is available for single-engine runs; all-engine runs execute in batch mode so the two outputs are generated together.

The `Advanced slider ranges` panel lets you change the visible minimum and maximum for individual sliders. The hard bounds are `0` to `10`, but most model defaults use normalized `0.0` to `1.0` values.

## Exports

Completed runs appear in the export tab as searchable expandable drawers with readable timestamps, run IDs, engine names, seed, simulated day count, agent count, summary metrics, and download buttons. Click `Prepare export files` for a run to generate its JSON, CSV, TXT, PNG, and ZIP files under `exports/`.

## Model Notes

Each simulation step represents one workday by default. On each simulated day, the model applies organizational policies, personal modifiers, social-network influence, random events, agent state updates, and turnover checks. Values are normalized where practical, generally from `0.0` to `1.0`, while emotional state ranges from `-1.0` to `1.0`.

The custom engine is a lightweight local implementation with a fixed hand-written update loop. The Mesa engine implements the same conceptual workplace model with Mesa `Model` and `Agent` objects, a `NetworkGrid`, and shuffled agent activation while preserving comparable output fields.

The central equations are intentionally simple and tunable. They are designed to support transparent scenario exploration rather than realistic causal inference.
