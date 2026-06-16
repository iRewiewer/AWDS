# Adaptive Workplace Dynamics Simulator (AWDS)

AWDS is a Python/Streamlit prototype for running exploratory, synthetic agent-based workplace simulations. It models a small organization of employee agents with dynamic stress, burnout, productivity, emotional state, energy, job satisfaction, work-life balance, engagement, and turnover.

The prototype is intended for dissertation/report support. It does not validate real organizational claims and should not be described as empirical evidence or prediction.

## Features

- Streamlit dashboard with sidebar configuration controls
- Factory presets, local user presets, and manual parameter overrides
- Explicit `Apply preset` and `Save as preset` controls
- Advanced slider-range editor with visible min/max bounds
- Deterministic runs from NumPy random seeds
- Sticky run controls with live-run pause/resume
- Scenario comparison mode using the same seed
- Export history drawers with JSON, CSV, TXT summary, PNG chart, and ZIP downloads saved under `exports/`
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

Then open the local Streamlit URL shown in the terminal.

## Project Structure

```text
app.py
simulation/
  config.py
  agent.py
  engine.py
  scenarios.py
  metrics.py
  exports.py
  utils.py
exports/
requirements.txt
user_presets.json  # created locally if you save custom presets
```

## Reproducibility

Every simulation uses `numpy.random.default_rng(seed)`. The same seed and same configuration produce the same aggregate time series. Changing either the seed or parameters should produce visibly different synthetic trajectories.

## Local Presets

Factory presets are built into `simulation/scenarios.py`. User presets saved from the dashboard are stored in `user_presets.json`, which is intentionally ignored by git so local scenario experiments do not accidentally get committed.

## Dashboard Notes

The sidebar has a sticky `Run controls` panel so the run, pause/resume, and clear controls remain reachable while scrolling through parameters. Presets are not applied automatically when selected; choose a factory or user preset, then click `Apply preset`.

The `Advanced slider ranges` panel lets you change the visible minimum and maximum for individual sliders. The hard bounds are `0` to `10`, but most model defaults use normalized `0.0` to `1.0` values.

## Exports

Completed runs appear in the export tab as expandable drawers with readable timestamps, seed, simulated day count, agent count, summary metrics, and download buttons. Click `Prepare export files` for a run to generate its JSON, CSV, TXT, PNG, and ZIP files under `exports/`.

## Model Notes

Each simulation step represents one workday by default. On each simulated day, the model applies organizational policies, personal modifiers, social-network influence, random events, agent state updates, and turnover checks. Values are normalized where practical, generally from `0.0` to `1.0`, while emotional state ranges from `-1.0` to `1.0`.

The central equations are intentionally simple and tunable. They are designed to support transparent scenario exploration rather than realistic causal inference.
