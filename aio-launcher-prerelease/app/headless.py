"""
File: app/headless.py

Purpose:
Build a fully wired TFLSessionEngine on a deterministic virtual clock
for tests and any future CLI or CI harness, with zero Tkinter
involvement. This is what keeps the TFL engine provably testable.

Communication / relationships:
- Imports get_default_config from frameworks/TFL/config.py.
- Imports load_stimuli and apply_stimulus_limit from frameworks/TFL/stimuli.py.
- Imports build_trials from frameworks/TFL/trial_builder.py.
- Imports TFLSessionEngine from frameworks/TFL/engine.py.
- Imports NullSchedulerTimer from engine/timing.py.
- Used by tests/test_merged.py.

Settings / parameters:
- build_default_engine(**engine_kwargs) forwards participant_id,
  session_id, on_trial_recorded, and on_stage_advanced straight to
  TFLSessionEngine.
- Always uses the official default TFL configuration: first 20 stimuli,
  probes on, delayed reentry on, perturbations off.

Edge cases:
- The engine is returned with its first trial already started, so the
  active stage is "prediction".
- The virtual clock never advances on its own; timeouts fire only when a
  test calls timer.fire(handle).

Known limitations:
- Only builds the default configuration. Tests that need a modified
  configuration must build the engine directly.
- TFL-specific; future frameworks need their own builder.

Examples:
- engine, timer = build_default_engine()
- engine, timer = build_default_engine(participant_id="P042")
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
