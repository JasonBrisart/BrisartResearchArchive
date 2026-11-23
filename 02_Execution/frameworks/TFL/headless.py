"""
File: frameworks/TFL/headless.py

Purpose
-------
Build a fully wired, started TFLSessionEngine on a deterministic virtual
clock for tests and automation, with no Tkinter involvement.

Communication / relationships
-----------------------------
- Uses frameworks/TFL/config.py, frameworks/TFL/stimuli.py, frameworks/TFL/trial_builder.py,
  frameworks/TFL/engine.py, and NullSchedulerTimer from frameworks/TFL/timing.py.
- Used by tests/test_tfl.py.

Settings / parameters
---------------------
- build_engine(options=None, **engine_kwargs): applies option overrides
  through set_option() (so they are validated exactly as the GUI and CLI
  validate them), resolves the run configuration, and forwards
  on_progress and on_stage_advanced.

Edge cases
----------
- An invalid override raises ValueError with the same message the
  options menus show.
- The engine is returned on the first trial's "cue" stage; the virtual
  clock only moves when the caller calls timer.advance().

Known limitations
-----------------
- Builds trials from the embedded stimuli only.

Examples
--------
- engine, timer = build_engine()
- engine, timer = build_engine({"enable_response_timer": True, "trial_duration_sec": 5})
"""
from __future__ import annotations

from .config import get_default_config, resolve_run_config, set_option
from .engine import TFLSessionEngine
from .stimuli import apply_stimulus_limit, load_stimuli
from .timing import NullSchedulerTimer
from .trial_builder import build_trials


def build_engine(options: dict | None = None, **engine_kwargs):
    config = get_default_config()
    for key, value in (options or {}).items():
        ok, message = set_option(config, key, value)
        if not ok:
            raise ValueError(message)
    run = resolve_run_config(config)
    trials = build_trials(run, apply_stimulus_limit(load_stimuli(), run))
    timer = NullSchedulerTimer()
    engine = TFLSessionEngine(run, trials, timer, **engine_kwargs)
    engine.start()
    return engine, timer


__all__ = ["build_engine"]
