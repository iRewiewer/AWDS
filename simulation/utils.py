"""Small utility helpers used across the simulation package."""

from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Clamp a numeric value into a closed interval."""
    return float(max(lower, min(upper, value)))


def safe_mean(values: list[float], default: float = 0.0) -> float:
    """Return a stable mean for possibly empty lists."""
    if not values:
        return default
    return float(sum(values) / len(values))


def serialisable(value: Any) -> Any:
    """Convert dataclasses and pathlib paths into JSON-friendly values."""
    if is_dataclass(value):
        return serialisable(asdict(value))
    if isinstance(value, dict):
        return {str(k): serialisable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialisable(v) for v in value]
    if isinstance(value, tuple):
        return [serialisable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    return value


def slugify(text: str) -> str:
    """Create a filesystem-friendly identifier."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "awds-run"
