"""
Headless engine construction helpers.

Lets tests (and any future CLI/CI harness) build a fully wired
TFLSessionEngine with a deterministic virtual clock, with zero Tkinter
involvement. This is what makes the engine provably testable.
"""
from __future__ import annotations

from engine.timing import NullSchedulerTimer
from frameworks.TFL.config import get_default_config
from frameworks.TFL.engine import TFLSessionEngine
from frameworks.TFL.stimuli import apply_stimulus_limit, load_stimuli
from frameworks.TFL.trial_builder import build_trials


def build_default_engine() -> tuple[TFLSessionEngine, NullSchedulerTimer]:
    config = get_default_config()
    stimuli = apply_stimulus_limit(load_stimuli(), config)
    trials = build_trials(config, stimuli)
    timer = NullSchedulerTimer()
    engine = TFLSessionEngine(config, trials, timer)
    engine.start_trial()
    return engine, timer


__all__ = ["build_default_engine"]
