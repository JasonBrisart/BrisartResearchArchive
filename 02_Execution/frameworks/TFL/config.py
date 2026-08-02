from __future__ import annotations

DEFAULT_BLOCKS = ["affect", "belief", "contradiction"]
DEFAULT_PERTURBATION_TYPES = [
    "head_turn",
    "posture_shift",
    "scene_shift",
    "breath_reset",
]
DEFAULT_FEEDBACK_LEVELS = [
    "confirmatory",
    "mildly_contradictory",
    "strongly_contradictory",
]
DEFAULT_CONFIG = {
    "trial_duration_sec": 12,
    "num_trials": 120,
    "trials_per_block": 40,
    "blocks": list(DEFAULT_BLOCKS),
    "affect_scale": [0, 100],
    "probe_interval": 4,
    "delayed_reentry_interval": 6,
    "random_seed": 2026,
    "feedback_levels": list(DEFAULT_FEEDBACK_LEVELS),
    "perturbation_interval": 5,
    "perturbation_types": list(DEFAULT_PERTURBATION_TYPES),
}
DEFAULT_MODE_DESCRIPTION = [
    "Default TFL",
    "First 20 stimuli only",
    "Extra stimuli OFF",
    "Perturbations OFF",
    "Probes ON",
    "Delayed reentry ON",
]


def get_raw_config() -> dict:
    config = dict(DEFAULT_CONFIG)
    config["blocks"] = list(DEFAULT_BLOCKS)
    config["feedback_levels"] = list(DEFAULT_FEEDBACK_LEVELS)
    config["perturbation_types"] = list(DEFAULT_PERTURBATION_TYPES)
    return config


def apply_default_options(config: dict | None = None) -> dict:
    """
    Applies official TFL default startup behavior:
    first 20 stimuli only, extra stimuli OFF, perturbations OFF,
    probes ON, delayed reentry ON.
    """
    if config is None:
        config = get_raw_config()
    else:
        merged = get_raw_config()
        merged.update(dict(config))
        config = merged
    config["enable_extra_stimuli"] = False
    config["enable_perturbations"] = False
    config["enable_probes"] = True
    config["enable_delayed_reentry"] = True
    config["run_mode"] = "default_tfl"
    config["mode_description"] = list(DEFAULT_MODE_DESCRIPTION)
    config["blocks"] = list(config.get("blocks", DEFAULT_BLOCKS))
    config["perturbation_types"] = list(config.get("perturbation_types", DEFAULT_PERTURBATION_TYPES))
    return config


def get_default_config() -> dict:
    return apply_default_options(get_raw_config())
