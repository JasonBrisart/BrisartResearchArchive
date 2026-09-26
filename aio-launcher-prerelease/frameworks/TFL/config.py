"""
File: frameworks/TFL/config.py

Purpose:
Assemble the TFL runtime config and the official default startup
options entirely from frameworks/TFL/settings.py. This module holds no
tunable values of its own.

Communication / relationships:
- Reads frameworks/TFL/settings.py.
- frameworks/TFL/session_gui.py calls apply_default_options().
- frameworks/TFL/options_screen.py uses it for Restore Defaults.
- frameworks/TFL/trial_builder.py imports DEFAULT_FEEDBACK_LEVELS and
  DEFAULT_PERTURBATION_TYPES.
- app/headless.py and tests/test_merged.py call get_default_config().
- frameworks/TFL/framework.py exposes lazy wrappers.

Settings / parameters:
- DEFAULT_CONFIG keys: trial_duration_sec, num_trials, trials_per_block,
  blocks, affect_scale, probe_interval, delayed_reentry_interval,
  random_seed, feedback_levels, perturbation_interval,
  perturbation_types.
- apply_default_options() adds enable_extra_stimuli,
  enable_perturbations, enable_probes, enable_delayed_reentry, run_mode,
  and mode_description.

Edge cases:
- apply_default_options(config) merges onto a fresh raw config and then
  overwrites all four toggles with their defaults; toggles already in
  the passed config are not preserved. The options screen applies user
  toggles afterwards.
- Lists are copied, so callers cannot mutate the settings module.

Known limitations:
- No validation happens here; frameworks/TFL/trial_builder.py validates.
- To change behavior, edit frameworks/TFL/settings.py, not this file.

Examples:
- config = get_default_config()
- config["enable_perturbations"] = True
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
