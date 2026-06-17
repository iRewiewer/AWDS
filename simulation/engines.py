"""Simulation engine selection helpers."""

from __future__ import annotations

from typing import Protocol

from .config import SimulationConfig
from .engine import SimulationEngine
from .mesa_engine import MesaSimulationEngine


ENGINE_CUSTOM = "Custom"
ENGINE_MESA = "Mesa"
ENGINE_ALL = "All engines"
ENGINE_OPTIONS = (ENGINE_CUSTOM, ENGINE_MESA, ENGINE_ALL)
SINGLE_ENGINE_OPTIONS = (ENGINE_CUSTOM, ENGINE_MESA)


class EngineLike(Protocol):
    config: SimulationConfig
    current_day: int

    def step(self) -> dict:
        ...

    def run(self) -> dict:
        ...

    def snapshot(self) -> dict:
        ...

    def result(self) -> dict:
        ...


def selected_engine_names(selection: str) -> tuple[str, ...]:
    if selection == ENGINE_ALL:
        return SINGLE_ENGINE_OPTIONS
    if selection in SINGLE_ENGINE_OPTIONS:
        return (selection,)
    return (ENGINE_CUSTOM,)


def create_engine(config: SimulationConfig, engine_name: str) -> EngineLike:
    if engine_name == ENGINE_MESA:
        return MesaSimulationEngine(config)
    if engine_name == ENGINE_CUSTOM:
        return SimulationEngine(config)
    raise ValueError(f"Unknown simulation engine: {engine_name}")
