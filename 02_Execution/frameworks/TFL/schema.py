"""
File: frameworks/TFL/schema.py

Purpose
-------
Own the TFL CSV column order: the 27 02_Execution reference columns in
reference order, then three response-timer columns, then three session
columns.

Communication / relationships
-----------------------------
- frameworks/TFL/engine.py builds rows with exactly these keys.
- frameworks/TFL/output.py writes them (an unknown key raises); the
  reference columns match the 02_Execution reference's own
  shared/output_schema.py. frameworks/TFL/analysis.py reads them by name.

Settings / parameters
---------------------
- REFERENCE_FIELDNAMES: 27 columns, in the reference's order.
- TIMER_FIELDNAMES: response_timer_sec, prediction_timed_out,
  behavioral_timed_out.
- SESSION_FIELDNAMES: protocol_edition, session_label, random_seed, and
  trial_status ("complete" or "in_progress").
- TRIAL_FIELDNAMES: the three lists joined; 34 columns.

Edge cases
----------
- In untimed runs response_timer_sec is blank and both timeout flags are
  False.
- A trial_status of "in_progress" marks the partially answered trial of an
  interrupted run; analysis excludes it.

Known limitations
-----------------
- Tools that compare whole headers byte-for-byte against the reference
  will see seven extra columns; reading by column name is unaffected.
- Column order is a file-format promise: reordering it changes every future
  session file, and analysis reads old files by name only.

Examples
--------
- from frameworks.TFL.schema import TRIAL_FIELDNAMES
"""
from __future__ import annotations

REFERENCE_FIELDNAMES = [
    "trial_id", "framework_id", "run_mode", "block", "block_trial_num",
    "stimulus_id", "cue", "ambiguous_text", "interpretation_a", "interpretation_b",
    "prior_instruction", "prediction", "prediction_rt", "affect",
    "behavioral_choice", "behavioral_rt", "feedback_level", "correct_answer",
    "contradiction", "probe_trial", "content_probe", "delayed_reentry",
    "recurrence_source_trial", "perturbation_trial", "perturbation_type",
    "post_perturbation_probe", "perturbation_match_prediction",
]
TIMER_FIELDNAMES = ["response_timer_sec", "prediction_timed_out", "behavioral_timed_out"]
SESSION_FIELDNAMES = ["protocol_edition", "session_label", "random_seed", "trial_status"]
TRIAL_FIELDNAMES = REFERENCE_FIELDNAMES + TIMER_FIELDNAMES + SESSION_FIELDNAMES

