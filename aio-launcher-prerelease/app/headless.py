"""
File: app/headless.py

Purpose
-------
Build a fully wired TFLSessionEngine on a deterministic virtual clock
for tests and automation, with no Tkinter involvement.

Communication / relationships
-----------------------------
- Uses frameworks/TFL config, stimuli, trial_builder, and engine.
- Uses NullSchedulerTimer from engine/timing.py.
- Used by tests/test_merged.py and tests/test_tfl_protocol.py.

Settings / parameters
---------------------
- build_default_engine(config_overrides=None, **engine_kwargs): applies
  the overrides on top of the default configuration, recomputes the run
  mode, forwards on_trial_recorded and on_stage_advanced.

Edge cases
----------
- The engine is returned already started, on the first trial's "cue"
  stage.
- The virtual clock only moves when a test calls timer.advance().

Known limitations
-----------------
- TFL-specific; future frameworks need their own builder.

Examples
--------
- engine, timer = build_default_engine()
- engine, timer = build_default_engine({"enable_response_timer": True})
"""
from __future__ import annotations

from engine.timing import NullSchedulerTimer
from frameworks.TFL.config import get_default_config, update_run_mode
from frameworks.TFL.engine import TFLSessionEngine
from frameworks.TFL.stimuli import apply_stimulus_limit, load_stimuli
from frameworks.TFL.trial_builder import build_trials


def build_default_engine(config_overrides: dict | None = None, **engine_kwargs):
    config = get_default_config()
    config.update(config_overrides or {})
    update_run_mode(config)
    trials = build_trials(config, apply_stimulus_limit(load_stimuli(), config))
    timer = NullSchedulerTimer()
    engine = TFLSessionEngine(config, trials, timer, **engine_kwargs)
    engine.start()
    return engine, timer


__all__ = ["build_default_engine"]
