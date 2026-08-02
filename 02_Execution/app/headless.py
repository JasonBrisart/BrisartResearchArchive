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


def build_default_engine(**engine_kwargs) -> tuple[TFLSessionEngine, NullSchedulerTimer]:
    """
    Build a fully wired engine against a virtual clock. Extra keyword
    arguments (participant_id, session_id, on_trial_recorded) pass
    straight through to TFLSessionEngine for tests that need them.
    """
    config = get_default_config()
    stimuli = apply_stimulus_limit(load_stimuli(), config)
    trials = build_trials(config, stimuli)
    timer = NullSchedulerTimer()
    engine = TFLSessionEngine(config, trials, timer, **engine_kwargs)
    engine.start_trial()
    return engine, timer


__all__ = ["build_default_engine"]
