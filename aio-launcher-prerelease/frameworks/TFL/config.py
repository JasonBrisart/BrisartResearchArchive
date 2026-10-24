"""
File: frameworks/TFL/config.py

Purpose
-------
Build TFL run configurations and the run-mode label from
frameworks/TFL/settings.py, following the 02_Execution option rules.

Communication / relationships
-----------------------------
- Reads frameworks/TFL/settings.py.
- Used by options_screen.py, session_gui.py, cli_runner.py,
  app/headless.py, and the tests.

Settings / parameters
---------------------
- get_raw_config(): the reference config.json values plus
  enable_response_timer and trial_duration_sec.
- apply_default_options(config=None): forces the four reference toggles
  and the timer to their defaults and labels the run "default_tfl".
- update_run_mode(config): "default_tfl" only when every toggle and the
  timer match the defaults, otherwise "modified_tfl".

Edge cases
----------
- apply_default_options() copies its input; the caller's dictionary is
  never mutated.
- normalize_timer_seconds() clamps to RESPONSE_TIMER_MIN_SEC..MAX_SEC and
  falls back to TRIAL_DURATION_SEC for unreadable input.

Known limitations
-----------------
- Structural values (blocks, intervals, seed) are not validated here;
  the trial builder uses them as given, as the reference does.

Examples
--------
- config = get_default_config()
- config["enable_perturbations"] = True; update_run_mode(config)
"""
from __future__ import annotations

from . import settings

DEFAULT_BLOCKS = list(settings.BLOCKS)
DEFAULT_PERTURBATION_TYPES = list(settings.PERTURBATION_TYPES)
DEFAULT_FEEDBACK_LEVELS = list(settings.FEEDBACK_LEVELS)
DEFAULT_MODE_DESCRIPTION = list(settings.DEFAULT_MODE_DESCRIPTION)

TOGGLE_KEYS = (
    "enable_extra_stimuli",
    "enable_perturbations",
    "enable_probes",
    "enable_delayed_reentry",
    "enable_response_timer",
)


def get_raw_config() -> dict:
    return {
        "trial_duration_sec": settings.TRIAL_DURATION_SEC,
        "num_trials": settings.NUM_TRIALS,
        "trials_per_block": settings.TRIALS_PER_BLOCK,
        "blocks": list(settings.BLOCKS),
        "affect_scale": list(settings.AFFECT_SCALE),
        "probe_interval": settings.PROBE_INTERVAL,
        "delayed_reentry_interval": settings.DELAYED_REENTRY_INTERVAL,
        "random_seed": settings.RANDOM_SEED,
        "feedback_levels": list(settings.FEEDBACK_LEVELS),
        "perturbation_interval": settings.PERTURBATION_INTERVAL,
        "perturbation_types": list(settings.PERTURBATION_TYPES),
    }


def default_toggles() -> dict:
    return {
        "enable_extra_stimuli": settings.DEFAULT_ENABLE_EXTRA_STIMULI,
        "enable_perturbations": settings.DEFAULT_ENABLE_PERTURBATIONS,
        "enable_probes": settings.DEFAULT_ENABLE_PROBES,
        "enable_delayed_reentry": settings.DEFAULT_ENABLE_DELAYED_REENTRY,
        "enable_response_timer": settings.DEFAULT_ENABLE_RESPONSE_TIMER,
    }


def normalize_timer_seconds(value) -> int:
    try:
        seconds = int(str(value).strip())
    except (TypeError, ValueError):
        return settings.TRIAL_DURATION_SEC
    return max(settings.RESPONSE_TIMER_MIN_SEC, min(seconds, settings.RESPONSE_TIMER_MAX_SEC))


def apply_default_options(config: dict | None = None) -> dict:
    """Reference rule: keep structural values, reset every run option."""
    merged = get_raw_config()
    if config:
        merged.update(dict(config))
    merged.setdefault("blocks", list(settings.BLOCKS))
    merged.setdefault("trials_per_block", settings.TRIALS_PER_BLOCK)
    merged.setdefault("probe_interval", settings.PROBE_INTERVAL)
    merged.setdefault("delayed_reentry_interval", settings.DELAYED_REENTRY_INTERVAL)
    merged.setdefault("perturbation_interval", settings.PERTURBATION_INTERVAL)
    merged.setdefault("perturbation_types", list(settings.PERTURBATION_TYPES))
    merged.update(default_toggles())
    merged["trial_duration_sec"] = settings.TRIAL_DURATION_SEC
    merged["run_mode"] = settings.RUN_MODE
    return merged


def get_default_config() -> dict:
    return apply_default_options()


def is_default_configuration(config: dict) -> bool:
    defaults = default_toggles()
    return all(bool(config.get(key, defaults[key])) is defaults[key] for key in TOGGLE_KEYS)


def update_run_mode(config: dict) -> dict:
    config["run_mode"] = settings.RUN_MODE if is_default_configuration(config) else settings.MODIFIED_RUN_MODE
    return config


def format_run_mode(run_mode: str) -> str:
    return {"default_tfl": "Default TFL", "modified_tfl": "Modified TFL"}.get(run_mode, run_mode)


def total_trials(config: dict) -> int:
    return int(config.get("trials_per_block", 0)) * len(config.get("blocks", []))


def describe_current_options(config: dict) -> list[str]:
    """Shared 'Current Settings' text for the GUI options screen and the CLI."""
    update_run_mode(config)

    def on_off(key):
        return "ON" if config.get(key, False) else "OFF"

    timer = (
        f"ON ({normalize_timer_seconds(config.get('trial_duration_sec'))} s)"
        if config.get("enable_response_timer", False) else "OFF"
    )
    return [
        f"Framework: {settings.FRAMEWORK_NAME}",
        f"Run Configuration: {format_run_mode(config['run_mode'])}",
        f"Extra Stimuli: {on_off('enable_extra_stimuli')}",
        f"Perturbations: {on_off('enable_perturbations')}",
        f"Probes: {on_off('enable_probes')}",
        f"Delayed Reentry: {on_off('enable_delayed_reentry')}",
        f"Response Timer: {timer}",
        f"Trials Per Block: {config.get('trials_per_block', 0)}",
        f"Blocks: {', '.join(config.get('blocks', []))}",
        f"Total Trials: {total_trials(config)}",
    ]
