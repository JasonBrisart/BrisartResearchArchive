"""
File: frameworks/TFL/config.py

Purpose
-------
Define every TFL run option once (OPTION_SPECS) and provide the rules for
defaults, validation, run-mode labelling, settings summaries, and
resolving a configuration into the exact values a run will use. The GUI
options screen and the CLI options menu are both generated from this
table, so the two front ends cannot drift apart.

Communication / relationships
-----------------------------
- Reads defaults and limits from frameworks/TFL/settings.py.
- frameworks/TFL/gui_options.py builds widgets from OPTION_SPECS and calls
  set_option().
- frameworks/TFL/cli_runner.py builds its numbered menu from OPTION_SPECS and calls
  set_option().
- frameworks/TFL/trial_builder.py, frameworks/TFL/engine.py, and frameworks/TFL/headless.py consume the
  dictionary returned by resolve_run_config().

Settings / parameters
---------------------
- Option kinds: "toggle" (bool), "int" (bounded whole number), "blocks"
  (non-empty subset of affect/belief/contradiction, kept in reference
  order), "seed" (whole number or "random"), "text" (session label).
- requires: an option that only applies while another toggle is on
  (for example the timer seconds need the response timer).
- affects_mode: options that change the protocol. Any of them differing
  from its default labels the run modified_tfl. The session label is
  metadata only and never changes the mode.

Edge cases
----------
- set_option() never raises; it returns (False, reason) for invalid
  input and leaves the configuration unchanged.
- A seed of "random" (or "r") is resolved to a fresh number per run by
  resolve_run_config(), and that number is recorded in every CSV row.
- Session labels are reduced to letters, digits, "-" and "_" so they are
  always safe inside a file name; a label that cleans to nothing is
  rejected.
- An option whose "requires" toggle is off still keeps its value; it is
  simply not used and still counts toward the run mode only if changed.

Known limitations
-----------------
- Interval options cannot be 0; the matching toggle is the way to turn a
  feature off.
- Options are per run and are not persisted between launches.

Examples
--------
- config = get_default_config()
- ok, message = set_option(config, "trials_per_block", "20")
- run = resolve_run_config(config)
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from . import settings


@dataclass(frozen=True)
class OptionSpec:
    key: str
    label: str
    kind: str
    description: str
    minimum: int | None = None
    maximum: int | None = None
    requires: str | None = None
    affects_mode: bool = True


OPTION_SPECS: tuple[OptionSpec, ...] = (
    OptionSpec("enable_perturbations", "Perturbations", "toggle",
               "Every Nth trial adds a brief physical perturbation and a post-perturbation probe."),
    OptionSpec("enable_extra_stimuli", "Extra Stimuli", "toggle",
               "Use the full 60-item stimulus library instead of the first 20."),
    OptionSpec("enable_probes", "Probes", "toggle",
               "Every Nth trial asks which interpretation is most active after feedback."),
    OptionSpec("enable_delayed_reentry", "Delayed Reentry", "toggle",
               "Every Nth trial in a block re-presents the stimulus from N trials earlier."),
    OptionSpec("enable_response_timer", "Response Timer", "toggle",
               "Limit prediction and behavioral choice to a fixed number of seconds."),
    OptionSpec("trial_duration_sec", "Response Timer Seconds", "int",
               "Seconds allowed for each timed response.",
               settings.RESPONSE_TIMER_MIN_SEC, settings.RESPONSE_TIMER_MAX_SEC, requires="enable_response_timer"),
    OptionSpec("trials_per_block", "Trials Per Block", "int",
               "Number of trials in each block.",
               settings.TRIALS_PER_BLOCK_MIN, settings.TRIALS_PER_BLOCK_MAX),
    OptionSpec("blocks", "Blocks", "blocks",
               "Which blocks to run. Blocks always keep the order affect, belief, contradiction unless shuffled."),
    OptionSpec("shuffle_blocks", "Shuffle Block Order", "toggle",
               "Shuffle the order of the selected blocks, reproducibly from the random seed."),
    OptionSpec("probe_interval", "Probe Interval", "int",
               "Ask the content probe on every Nth trial.",
               settings.INTERVAL_MIN, settings.INTERVAL_MAX, requires="enable_probes"),
    OptionSpec("delayed_reentry_interval", "Delayed Reentry Interval", "int",
               "Re-present the stimulus from N trials earlier on every Nth trial of a block.",
               settings.INTERVAL_MIN, settings.INTERVAL_MAX, requires="enable_delayed_reentry"),
    OptionSpec("perturbation_interval", "Perturbation Interval", "int",
               "Add a perturbation on every Nth trial.",
               settings.INTERVAL_MIN, settings.INTERVAL_MAX, requires="enable_perturbations"),
    OptionSpec("random_seed", "Random Seed", "seed",
               "A whole number reproduces the same trial sequence; 'random' draws a new seed for each run."),
    OptionSpec("session_label", "Session Label", "text",
               "Optional label added to the CSV file name and to every row. Letters, digits, - and _ only.",
               affects_mode=False),
)
SPECS_BY_KEY = {spec.key: spec for spec in OPTION_SPECS}

DEFAULT_OPTIONS = {
    "enable_perturbations": settings.DEFAULT_ENABLE_PERTURBATIONS,
    "enable_extra_stimuli": settings.DEFAULT_ENABLE_EXTRA_STIMULI,
    "enable_probes": settings.DEFAULT_ENABLE_PROBES,
    "enable_delayed_reentry": settings.DEFAULT_ENABLE_DELAYED_REENTRY,
    "enable_response_timer": settings.DEFAULT_ENABLE_RESPONSE_TIMER,
    "trial_duration_sec": settings.TRIAL_DURATION_SEC,
    "trials_per_block": settings.TRIALS_PER_BLOCK,
    "blocks": list(settings.BLOCKS),
    "shuffle_blocks": settings.DEFAULT_SHUFFLE_BLOCKS,
    "probe_interval": settings.PROBE_INTERVAL,
    "delayed_reentry_interval": settings.DELAYED_REENTRY_INTERVAL,
    "perturbation_interval": settings.PERTURBATION_INTERVAL,
    "random_seed": settings.RANDOM_SEED,
    "session_label": settings.SESSION_LABEL,
}


# ============================================================
# Defaults and run mode
# ============================================================
def get_default_config() -> dict:
    config = {key: (list(value) if isinstance(value, list) else value) for key, value in DEFAULT_OPTIONS.items()}
    config["perturbation_types"] = list(settings.PERTURBATION_TYPES)
    config["run_mode"] = settings.RUN_MODE
    return config


def restore_defaults(config: dict) -> dict:
    """Reset every option, keeping the session label (it is metadata, not protocol)."""
    restored = get_default_config()
    restored["session_label"] = config.get("session_label", settings.SESSION_LABEL)
    return update_run_mode(restored)


def is_default_configuration(config: dict) -> bool:
    return all(
        config.get(spec.key, DEFAULT_OPTIONS[spec.key]) == DEFAULT_OPTIONS[spec.key]
        for spec in OPTION_SPECS if spec.affects_mode
    )


def update_run_mode(config: dict) -> dict:
    config["run_mode"] = settings.RUN_MODE if is_default_configuration(config) else settings.MODIFIED_RUN_MODE
    return config


def format_run_mode(run_mode: str) -> str:
    return {"default_tfl": "Default TFL", "modified_tfl": "Modified TFL"}.get(run_mode, run_mode)


# ============================================================
# Validation
# ============================================================
def _parse_bool(text: str) -> bool | None:
    value = str(text).strip().casefold()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return None


def parse_option(key: str, raw) -> tuple[bool, object]:
    """Return (True, value) or (False, reason). Never raises."""
    spec = SPECS_BY_KEY.get(key)
    if spec is None:
        return False, f"Unknown option: {key}"
    if spec.kind == "toggle":
        value = raw if isinstance(raw, bool) else _parse_bool(raw)
        return (True, value) if value is not None else (False, f"{spec.label} must be on or off.")
    if spec.kind == "int":
        try:
            number = int(str(raw).strip())
        except (TypeError, ValueError):
            return False, f"{spec.label} must be a whole number from {spec.minimum} to {spec.maximum}."
        if not spec.minimum <= number <= spec.maximum:
            return False, f"{spec.label} must be from {spec.minimum} to {spec.maximum}."
        return True, number
    if spec.kind == "blocks":
        items = raw if isinstance(raw, (list, tuple)) else str(raw).replace(",", " ").split()
        chosen = {str(item).strip().casefold() for item in items if str(item).strip()}
        unknown = chosen - set(settings.BLOCKS)
        if unknown:
            return False, "Unknown block(s): " + ", ".join(sorted(unknown)) + ". Use affect, belief, contradiction."
        if not chosen:
            return False, "Select at least one block."
        return True, [block for block in settings.BLOCKS if block in chosen]
    if spec.kind == "seed":
        text = str(raw).strip().casefold()
        if text in {"random", "r"}:
            return True, "random"
        try:
            number = int(text)
        except ValueError:
            return False, f"Random Seed must be a whole number from 0 to {settings.SEED_MAX}, or 'random'."
        if not 0 <= number <= settings.SEED_MAX:
            return False, f"Random Seed must be from 0 to {settings.SEED_MAX}."
        return True, number
    if spec.kind == "text":
        text = str(raw).strip()
        cleaned = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in text).strip("_")
        if text and not cleaned:
            return False, "Session Label must contain letters or digits."
        if len(cleaned) > settings.SESSION_LABEL_MAX_LENGTH:
            return False, f"Session Label must be at most {settings.SESSION_LABEL_MAX_LENGTH} characters."
        return True, cleaned
    return False, f"Unsupported option kind: {spec.kind}"


def set_option(config: dict, key: str, raw) -> tuple[bool, str]:
    ok, value = parse_option(key, raw)
    if not ok:
        return False, str(value)
    config[key] = value
    update_run_mode(config)
    return True, f"{SPECS_BY_KEY[key].label}: {format_value(key, value)}"


def toggle_option(config: dict, key: str) -> tuple[bool, str]:
    return set_option(config, key, not bool(config.get(key, DEFAULT_OPTIONS[key])))


# ============================================================
# Presentation helpers
# ============================================================
def format_value(key: str, value) -> str:
    spec = SPECS_BY_KEY[key]
    if spec.kind == "toggle":
        return "ON" if value else "OFF"
    if spec.kind == "blocks":
        return ", ".join(value)
    if spec.kind == "text":
        return value or "(none)"
    if key == "trial_duration_sec":
        return f"{value} s"
    return str(value)


def total_trials(config: dict) -> int:
    return int(config.get("trials_per_block", 0)) * len(config.get("blocks", []))


def describe_current_options(config: dict) -> list[str]:
    update_run_mode(config)
    lines = [
        f"Framework: {settings.FRAMEWORK_NAME}",
        f"Run Configuration: {format_run_mode(config['run_mode'])}",
    ]
    for spec in OPTION_SPECS:
        value = config.get(spec.key, DEFAULT_OPTIONS[spec.key])
        inactive = spec.requires and not config.get(spec.requires, DEFAULT_OPTIONS[spec.requires])
        suffix = " (not used)" if inactive else ""
        lines.append(f"{spec.label}: {format_value(spec.key, value)}{suffix}")
    lines.append(f"Total Trials: {total_trials(config)}")
    return lines


def default_mode_description() -> list[str]:
    """Reference startup summary of what Default TFL means."""
    defaults = get_default_config()
    return [
        "Default TFL",
        f"First {settings.BASE_STIMULUS_LIMIT} stimuli only",
        f"{defaults['trials_per_block']} trials in each of: {', '.join(defaults['blocks'])}",
        "Perturbations OFF",
        "Probes ON",
        "Delayed reentry ON",
        "Response timer OFF",
        f"Random seed {defaults['random_seed']}",
    ]


# ============================================================
# Resolution
# ============================================================
def resolve_run_config(config: dict) -> dict:
    """Return a complete, validated copy with a concrete seed."""
    resolved = get_default_config()
    for spec in OPTION_SPECS:
        if spec.key in config:
            ok, value = parse_option(spec.key, config[spec.key])
            if not ok:
                raise ValueError(value)
            resolved[spec.key] = value
    for key in ("perturbation_types",):
        if key in config:
            resolved[key] = list(config[key])
    resolved["random_seed_mode"] = "random" if resolved["random_seed"] == "random" else "fixed"
    if resolved["random_seed"] == "random":
        resolved["random_seed"] = secrets.randbelow(settings.SEED_MAX + 1)
    update_run_mode(resolved)
    if resolved["random_seed_mode"] == "random":
        resolved["run_mode"] = settings.MODIFIED_RUN_MODE
    return resolved
