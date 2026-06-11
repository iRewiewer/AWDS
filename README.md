# Adaptive Workplace Dynamics Simulator (AWDS)

AWDS is a Python/Streamlit prototype for running exploratory, synthetic agent-based workplace simulations. It models a small organization of employee agents with dynamic stress, burnout, productivity, emotional state, energy, job satisfaction, work-life balance, engagement, and turnover.

The prototype is intended for dissertation/report support. It does not validate real organizational claims and should not be described as empirical evidence or prediction.

## Features

- Streamlit dashboard with sidebar configuration controls
- Preset scenarios plus manual parameter overrides
- Deterministic runs from NumPy random seeds
- Live-updating charts for stress, burnout, productivity, emotion, satisfaction, work-life balance, and turnover
- Scenario comparison mode using the same seed
- JSON, CSV, TXT summary, PNG chart, and ZIP exports saved under `exports/`
- Optional per-agent history collection for raw data exports

## Setup

Use Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

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
```

## Reproducibility

Every simulation uses `numpy.random.default_rng(seed)`. The same seed and same configuration produce the same aggregate time series. Changing either the seed or parameters should produce visibly different synthetic trajectories.

## Model Notes

Each tick represents one workday by default. At every tick, the model applies organizational policies, personal modifiers, social-network influence, random events, agent state updates, and turnover checks. Values are normalized where practical, generally from `0.0` to `1.0`, while emotional state ranges from `-1.0` to `1.0`.

The central equations are intentionally simple and tunable. They are designed to support transparent scenario exploration rather than realistic causal inference.
