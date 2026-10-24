"""
File: frameworks/TFL/trial_builder.py

Purpose
-------
Build the ordered TFL trial sequence with the 02_Execution reference
algorithm: the same draws, in the same order, from the same seed.

Communication / relationships
-----------------------------
- Called by session_gui.py, cli_runner.py, app/headless.py, and the
  lazy wrapper in framework.py.
- Stamps settings.FRAMEWORK_ID onto every trial.

Settings / parameters
---------------------
- Per trial, in order: stimulus = choice(stimuli); prior = choice(A, B);
  probe flag; delayed-reentry substitution; perturbation type = choice()
  on perturbation trials; contradiction-block feedback = choice(levels).
- Probe: trial_id % probe_interval == 0 when probes are on.
- Delayed reentry: block_trial_num % interval == 0 and trial_id >
  interval; copies the stimulus of the trial `interval` positions back.
- Feedback: affect neutral, belief confirmatory, contradiction random.

Edge cases
----------
- A private random.Random(seed) instance is used instead of seeding the
  process-wide generator. Its draw sequence is identical to the
  reference's random.seed()/random.choice() sequence (proved by test),
  without side effects on other code.
- A seed of None gives a non-reproducible sequence, as in the reference.

Known limitations
-----------------
- No validation of block names or intervals, matching the reference.

Examples
--------
- trials = build_trials(get_default_config(), stimuli)
"""
from __future__ import annotations

import random

from . import settings


def should_use_probe(enable_probes: bool, probe_interval: int, trial_id: int) -> bool:
    if not enable_probes or not probe_interval or probe_interval <= 0:
        return False
    return trial_id % probe_interval == 0


def handle_delayed_reentry(enable, interval, trial_id, block_trial_num, trials, current_stimulus):
    if not enable or not interval or interval <= 0:
        return False, "", current_stimulus
    if trial_id <= interval or block_trial_num % interval != 0:
        return False, "", current_stimulus
    source = trials[-interval]
    stimulus = {key: source[key] for key in
                ("stimulus_id", "cue", "ambiguous_text", "interpretation_a", "interpretation_b")}
    return True, source["trial_id"], stimulus


def select_feedback_level(block: str, rng: random.Random) -> str:
    if block == "affect":
        return "neutral"
    if block == "belief":
        return "confirmatory"
    if block == "contradiction":
        return rng.choice(["confirmatory", "mildly_contradictory", "strongly_contradictory"])
    return "neutral"


def select_perturbation(interval, perturbation_types, trial_id, rng: random.Random):
    if not interval or interval <= 0 or trial_id % interval != 0:
        return False, ""
    return True, rng.choice(perturbation_types)


def build_trials(config: dict, stimuli: list[dict]) -> list[dict]:
    rng = random.Random(config.get("random_seed", None))
    blocks = config["blocks"]
    trials_per_block = config["trials_per_block"]
    probe_interval = config.get("probe_interval", 0)
    reentry_interval = config.get("delayed_reentry_interval", 0)
    enable_probes = config.get("enable_probes", True)
    enable_reentry = config.get("enable_delayed_reentry", True)
    perturbation_interval = (
        config.get("perturbation_interval", 0) if config.get("enable_perturbations", False) else 0
    )
    perturbation_types = config.get("perturbation_types", list(settings.PERTURBATION_TYPES))

    trials: list[dict] = []
    trial_id = 1
    for block in blocks:
        for block_trial_num in range(1, trials_per_block + 1):
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
                "stimulus_id": stimulus["stimulus_id"],
                "cue": stimulus["cue"],
                "ambiguous_text": stimulus["ambiguous_text"],
                "interpretation_a": stimulus["interpretation_a"],
                "interpretation_b": stimulus["interpretation_b"],
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
