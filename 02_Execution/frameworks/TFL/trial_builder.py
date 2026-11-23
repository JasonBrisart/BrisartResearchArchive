"""
File: frameworks/TFL/trial_builder.py

Purpose
-------
Build the ordered TFL trial sequence with the 02_Execution reference
algorithm: the same draws, in the same order, from the same seed. With
default options the sequence is identical to the reference.

Communication / relationships
-----------------------------
- Called by frameworks/TFL/headless.py, frameworks/TFL/gui_session.py, and frameworks/TFL/cli_runner.py
  with a configuration from frameworks/TFL/config.resolve_run_config().
- Reads constants from frameworks/TFL/settings.py.

Settings / parameters
---------------------
- Per trial, in order: stimulus = choice(stimuli); prior = choice(A, B);
  probe flag; delayed-reentry substitution; perturbation type on
  perturbation trials; contradiction-block feedback level.
- Probe: trial_id % probe_interval == 0 while probes are on.
- Delayed reentry: block_trial_num % interval == 0 and trial_id >
  interval; copies the stimulus from interval trials back.
- Feedback level: affect neutral, belief confirmatory, contradiction
  random.
- shuffle_blocks: block order is shuffled by a separate generator seeded
  from the run seed, so the trial draws themselves are unchanged.

Edge cases
----------
- Trial draws use a private random.Random(seed), which yields the same
  sequence as the reference's process-wide random.seed()/random.choice()
  (proved by test) without disturbing random state elsewhere.
- Delayed reentry can copy from the previous block when a block is
  shorter than the interval allows; this matches the reference rule.

Known limitations
-----------------
- Feedback levels inside the contradiction block are fixed to the three
  reference levels; they are not an option.

Examples
--------
- trials = build_trials(resolve_run_config(get_default_config()), stimuli)
"""
from __future__ import annotations

import random

from . import settings

STIMULUS_FIELDS = ("stimulus_id", "cue", "ambiguous_text", "interpretation_a", "interpretation_b")


def should_use_probe(enable_probes: bool, probe_interval: int, trial_id: int) -> bool:
    return bool(enable_probes and probe_interval and probe_interval > 0 and trial_id % probe_interval == 0)


def handle_delayed_reentry(enable, interval, trial_id, block_trial_num, trials, current_stimulus):
    if not enable or not interval or interval <= 0:
        return False, "", current_stimulus
    if trial_id <= interval or block_trial_num % interval != 0:
        return False, "", current_stimulus
    source = trials[-interval]
    return True, source["trial_id"], {key: source[key] for key in STIMULUS_FIELDS}


def select_feedback_level(block: str, rng: random.Random) -> str:
    if block == "affect":
        return "neutral"
    if block == "belief":
        return "confirmatory"
    if block == "contradiction":
        return rng.choice(settings.FEEDBACK_LEVELS)
    return "neutral"


def select_perturbation(interval, perturbation_types, trial_id, rng: random.Random):
    if not interval or interval <= 0 or trial_id % interval != 0:
        return False, ""
    return True, rng.choice(perturbation_types)


def block_order(config: dict) -> list[str]:
    blocks = list(config["blocks"])
    if config.get("shuffle_blocks", False):
        random.Random(f"blocks:{config.get('random_seed')}").shuffle(blocks)
    return blocks


def build_trials(config: dict, stimuli: list[dict]) -> list[dict]:
    rng = random.Random(config.get("random_seed", None))
    probe_interval = config.get("probe_interval", 0)
    reentry_interval = config.get("delayed_reentry_interval", 0)
    enable_probes = config.get("enable_probes", True)
    enable_reentry = config.get("enable_delayed_reentry", True)
    perturbation_interval = config.get("perturbation_interval", 0) if config.get("enable_perturbations", False) else 0
    perturbation_types = config.get("perturbation_types", settings.PERTURBATION_TYPES)

    trials: list[dict] = []
    trial_id = 1
    for block in block_order(config):
        for block_trial_num in range(1, config["trials_per_block"] + 1):
            stimulus = rng.choice(stimuli)
            prior = rng.choice(["A", "B"])
            probe_trial = should_use_probe(enable_probes, probe_interval, trial_id)
            delayed, source_trial, stimulus = handle_delayed_reentry(
                enable_reentry, reentry_interval, trial_id, block_trial_num, trials, stimulus,
            )
            perturbation_trial, perturbation_type = select_perturbation(
                perturbation_interval, perturbation_types, trial_id, rng,
            )
            trials.append({
                "trial_id": trial_id,
                "framework_id": settings.FRAMEWORK_ID,
                "run_mode": config.get("run_mode", settings.RUN_MODE),
                "block": block,
                "block_trial_num": block_trial_num,
                **{key: stimulus[key] for key in STIMULUS_FIELDS},
                "prior_instruction": prior,
                "feedback_level": select_feedback_level(block, rng),
                "probe_trial": probe_trial,
                "delayed_reentry": delayed,
                "recurrence_source_trial": source_trial,
                "perturbation_trial": perturbation_trial,
                "perturbation_type": perturbation_type,
            })
            trial_id += 1
    return trials
