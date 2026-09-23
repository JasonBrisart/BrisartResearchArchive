"""
frameworks/TFL/config.py
Assembles TFL's runtime config dict and the "official default startup"
option set from the single source of truth in frameworks/TFL/settings.py.

This module holds NO tunable literals of its own anymore -- every value
below is read from settings.py, so behavior is edited THERE, not here.
get_raw_config() returns the base experiment parameters;
apply_default_options() layers on the official default run behavior
(first 20 stimuli only, extra stimuli OFF, perturbations OFF, probes ON,
delayed reentry ON) and stamps run_mode/mode_description;
get_default_config() is the convenience combination of the two, and is
what the GUI options screen and the headless engine builder both start
from.
"""
from __future__ import annotations
from . import settings
# Backward-compatible aliases: other modules (e.g. trial_builder.py) still
# import these names from config. They now resolve to the canonical values
# in settings.py, so there is exactly one place to change them.
DEFAULT_BLOCKS = list(settings.BLOCKS)
DEFAULT_PERTURBATION_TYPES = list(settings.PERTURBATION_TYPES)
DEFAULT_FEEDBACK_LEVELS = list(settings.FEEDBACK_LEVELS)
DEFAULT_MODE_DESCRIPTION = list(settings.DEFAULT_MODE_DESCRIPTION)
DEFAULT_CONFIG = {
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
def get_raw_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    config["blocks"] = list(settings.BLOCKS)
    config["feedback_levels"] = list(settings.FEEDBACK_LEVELS)
    config["perturbation_types"] = list(settings.PERTURBATION_TYPES)
    return config
def apply_default_options(config: dict | None = None) -> dict:
    """
    Applies the official TFL default startup behavior, all read from
    settings.py: extra stimuli / perturbations / probes / delayed reentry
    toggles, run_mode, and mode_description.
    """
    if config is None:
        config = get_raw_config()
    else:
        merged = get_raw_config()
        merged.update(dict(config))
        config = merged
    config["enable_extra_stimuli"] = settings.DEFAULT_ENABLE_EXTRA_STIMULI
    config["enable_perturbations"] = settings.DEFAULT_ENABLE_PERTURBATIONS
    config["enable_probes"] = settings.DEFAULT_ENABLE_PROBES
    config["enable_delayed_reentry"] = settings.DEFAULT_ENABLE_DELAYED_REENTRY
    config["run_mode"] = settings.RUN_MODE
    config["mode_description"] = list(settings.DEFAULT_MODE_DESCRIPTION)
    config["blocks"] = list(config.get("blocks", settings.BLOCKS))
    config["perturbation_types"] = list(config.get("perturbation_types", settings.PERTURBATION_TYPES))
    return config
def get_default_config() -> dict:
    return apply_default_options(get_raw_config())
