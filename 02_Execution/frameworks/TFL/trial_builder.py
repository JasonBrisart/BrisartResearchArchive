from __future__ import annotations

import random
from collections.abc import Iterable

from . import framework
from .config import DEFAULT_FEEDBACK_LEVELS, DEFAULT_PERTURBATION_TYPES

VALID_BLOCKS = {"affect", "belief", "contradiction"}
VALID_FEEDBACK_LEVELS = {"confirmatory", "mildly_contradictory", "strongly_contradictory"}
REQUIRED_STIMULUS_FIELDS = (
    "stimulus_id", "cue", "ambiguous_text", "interpretation_a", "interpretation_b",
)


def normalize_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", ""}:
            return False
    return bool(default)


def positive_int(value, default: int, *, allow_zero: bool = False) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return default
    minimum = 0 if allow_zero else 1
    return normalized if normalized >= minimum else default


def normalize_blocks(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Iterable):
        raise ValueError("TFL config 'blocks' must be a list of block names.")
    blocks = []
    for item in value:
        block = str(item).strip().lower()
        if not block:
            continue
        if block not in VALID_BLOCKS:
            raise ValueError(f"Unsupported TFL block: {block!r}")
        blocks.append(block)
    if not blocks:
        raise ValueError("At least one TFL block is required.")
    return blocks


def normalize_feedback_levels(value) -> list[str]:
    if value is None:
        value = DEFAULT_FEEDBACK_LEVELS
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Iterable):
        raise ValueError("feedback_levels must be iterable")
    result = []
    for item in value:
        name = str(item).strip().lower()
        if not name:
            continue
        if name not in VALID_FEEDBACK_LEVELS:
            raise ValueError(f"Unsupported TFL feedback level: {name!r}")
        result.append(name)
    if not result:
        raise ValueError("At least one supported TFL feedback level is required.")
    return result


def normalize_perturbation_types(value) -> list[str]:
    if value is None:
        value = DEFAULT_PERTURBATION_TYPES
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Iterable):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def normalize_stimuli(stimuli) -> list[dict]:
    if isinstance(stimuli, dict) or not isinstance(stimuli, Iterable):
        raise TypeError("TFL stimuli must be an iterable of dictionaries.")
    normalized = []
    seen = set()
    for number, stimulus in enumerate(stimuli, start=1):
        if not isinstance(stimulus, dict):
            raise TypeError(f"TFL stimulus {number} is not a dictionary.")
        row = {}
        for field in REQUIRED_STIMULUS_FIELDS:
            row[field] = str(stimulus.get(field, "") or "").strip()
            if not row[field]:
                raise ValueError(f"TFL stimulus {number} missing required field {field}")
        sid = row["stimulus_id"]
        if sid in seen:
            raise ValueError(f"Duplicate TFL stimulus_id found: {sid}")
        seen.add(sid)
        normalized.append(row)
    if not normalized:
        raise ValueError("TFL cannot build trials without stimuli.")
    return normalized


# ============================================================
# Trial helpers
# ============================================================

def is_interval_trial(trial_number: int, interval: int) -> bool:
    return interval > 0 and trial_number % interval == 0


def should_use_probe(enable_probes: bool, probe_interval: int, trial_number: int) -> bool:
    return bool(enable_probes and is_interval_trial(trial_number, probe_interval))


def should_use_delayed_reentry(enable_delayed_reentry: bool, delayed_reentry_interval: int, trial_number: int) -> bool:
    return bool(
        enable_delayed_reentry
        and is_interval_trial(trial_number, delayed_reentry_interval)
        and trial_number > delayed_reentry_interval
    )


def recurrence_source_for_trial(trial_number: int, delayed_reentry_interval: int) -> int | str:
    if delayed_reentry_interval <= 0 or trial_number <= delayed_reentry_interval:
        return ""
    return trial_number - delayed_reentry_interval


def block_for_trial(trial_index: int, blocks: list[str], trials_per_block: int) -> tuple[str, int]:
    block_index = trial_index // trials_per_block
    if block_index >= len(blocks):
        block_index = block_index % len(blocks)
    block = blocks[block_index]
    block_trial_number = (trial_index % trials_per_block) + 1
    return block, block_trial_number


def select_feedback_level(block: str, block_trial_number: int, feedback_levels: list[str]) -> str:
    if block == "affect":
        return "neutral"
    if block == "belief":
        return "confirmatory"
    if block == "contradiction":
        feedback_index = (block_trial_number - 1) % len(feedback_levels)
        return feedback_levels[feedback_index]
    return "neutral"


def prior_for_trial(block: str, block_trial_number: int) -> str:
    if block != "belief":
        return ""
    return "A" if block_trial_number % 2 else "B"


def select_perturbation(
    perturbation_interval: int,
    perturbation_types: list[str],
    trial_number: int,
) -> tuple[bool, str]:
    if perturbation_interval <= 0 or not perturbation_types:
        return False, ""
    if not is_interval_trial(trial_number, perturbation_interval):
        return False, ""
    index = ((trial_number // max(perturbation_interval, 1)) - 1) % len(perturbation_types)
    return True, perturbation_types[index]


# ============================================================
# Trial construction
# ============================================================

def build_trials(config: dict, stimuli: list[dict]) -> list[dict]:
    """
    Build the complete TFL trial sequence. Delayed-reentry trials reuse
    the stimulus content from their declared recurrence source, so the
    relationship represented by recurrence_source_trial always holds.
    """
    if not isinstance(config, dict):
        raise TypeError("TFL config must be a dictionary.")

    normalized_stimuli = normalize_stimuli(stimuli)
    blocks = normalize_blocks(config.get("blocks", ["affect", "belief", "contradiction"]))
    trials_per_block = positive_int(config.get("trials_per_block", len(normalized_stimuli)), len(normalized_stimuli))
    configured_trial_count = positive_int(
        config.get("num_trials", trials_per_block * len(blocks)), trials_per_block * len(blocks)
    )
    total_trials = min(configured_trial_count, trials_per_block * len(blocks))
    if total_trials < 1:
        raise ValueError("TFL trial count must be at least one.")

    random_seed = positive_int(config.get("random_seed", 2026), 2026, allow_zero=True)
    probe_interval = positive_int(config.get("probe_interval", 4), 4, allow_zero=True)
    delayed_reentry_interval = positive_int(config.get("delayed_reentry_interval", 6), 6, allow_zero=True)
    perturbation_interval = positive_int(config.get("perturbation_interval", 5), 5, allow_zero=True)
    feedback_levels = normalize_feedback_levels(config.get("feedback_levels", DEFAULT_FEEDBACK_LEVELS))
    perturbation_types = normalize_perturbation_types(config.get("perturbation_types", DEFAULT_PERTURBATION_TYPES))
    enable_probes = normalize_bool(config.get("enable_probes", True), True)
    enable_delayed_reentry = normalize_bool(config.get("enable_delayed_reentry", True), True)
    enable_perturbations = normalize_bool(config.get("enable_perturbations", False), False)
    run_mode = str(config.get("run_mode", "default_tfl")).strip() or "default_tfl"

    randomizer = random.Random(random_seed)
    stimulus_pool = [dict(stimulus) for stimulus in normalized_stimuli]
    randomizer.shuffle(stimulus_pool)

    trials: list[dict] = []
    for trial_index in range(total_trials):
        trial_number = trial_index + 1
        if trial_index > 0 and trial_index % len(stimulus_pool) == 0:
            randomizer.shuffle(stimulus_pool)

        block, block_trial_number = block_for_trial(trial_index, blocks, trials_per_block)
        stimulus = dict(stimulus_pool[trial_index % len(stimulus_pool)])

        delayed_reentry = should_use_delayed_reentry(enable_delayed_reentry, delayed_reentry_interval, trial_number)
        recurrence_source_trial = ""
        if delayed_reentry:
            recurrence_source_trial = recurrence_source_for_trial(trial_number, delayed_reentry_interval)
            if recurrence_source_trial:
                source_index = int(recurrence_source_trial) - 1
                if not (0 <= source_index < len(trials)):
                    raise RuntimeError("Delayed-reentry source trial is outside the generated trial list.")
                source_trial = trials[source_index]
                stimulus = {field: source_trial[field] for field in REQUIRED_STIMULUS_FIELDS}

        perturbation_trial = False
        perturbation_type = ""
        if enable_perturbations:
            perturbation_trial, perturbation_type = select_perturbation(
                perturbation_interval, perturbation_types, trial_number
            )

        trials.append({
            "trial_id": trial_number,
            "framework_id": framework.FRAMEWORK_ID,
            "run_mode": run_mode,
            "block": block,
            "block_trial_num": block_trial_number,
            "stimulus_id": stimulus["stimulus_id"],
            "cue": stimulus["cue"],
            "ambiguous_text": stimulus["ambiguous_text"],
            "interpretation_a": stimulus["interpretation_a"],
            "interpretation_b": stimulus["interpretation_b"],
            "prior_instruction": prior_for_trial(block, block_trial_number),
            "feedback_level": select_feedback_level(block, block_trial_number, feedback_levels),
            "probe_trial": should_use_probe(enable_probes, probe_interval, trial_number),
            "delayed_reentry": delayed_reentry,
            "recurrence_source_trial": recurrence_source_trial,
            "perturbation_trial": perturbation_trial,
            "perturbation_type": perturbation_type,
        })

    return trials
