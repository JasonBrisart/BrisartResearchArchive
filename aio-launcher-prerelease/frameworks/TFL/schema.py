"""
File: frameworks/TFL/schema.py

Purpose
-------
Own the TFL CSV column order: the 27 02_Execution reference columns in
reference order, followed by three response-timer columns.

Communication / relationships
-----------------------------
- frameworks/TFL/framework.py re-exports TRIAL_FIELDNAMES as
  CSV_FIELDNAMES.
- frameworks/TFL/engine.py builds rows with exactly these keys.
- frameworks/TFL/output.py writes them; analysis.py reads them by name.
- frameworks/shared/schema.py re-exports for older imports.

Settings / parameters
---------------------
- REFERENCE_FIELDNAMES: 27 columns, identical to the reference
  shared/output_schema.py.
- TIMER_FIELDNAMES: response_timer_sec, prediction_timed_out,
  behavioral_timed_out.

Edge cases
----------
- In untimed runs response_timer_sec is blank and both timeout flags are
  False, so the reference columns carry the full record.

Known limitations
-----------------
- Appending columns keeps reference columns readable by name, but tools
  that compare whole headers byte-for-byte will see three extra columns.

Examples
--------
- from frameworks.TFL.schema import TRIAL_FIELDNAMES
"""
from __future__ import annotations

REFERENCE_FIELDNAMES = [
    "trial_id",
    "framework_id",
    "run_mode",
    "block",
    "block_trial_num",
    "stimulus_id",
    "cue",
    "ambiguous_text",
    "interpretation_a",
    "interpretation_b",
    "prior_instruction",
    "prediction",
    "prediction_rt",
    "affect",
    "behavioral_choice",
    "behavioral_rt",
    "feedback_level",
    "correct_answer",
    "contradiction",
    "probe_trial",
    "content_probe",
    "delayed_reentry",
    "recurrence_source_trial",
    "perturbation_trial",
    "perturbation_type",
    "post_perturbation_probe",
    "perturbation_match_prediction",
]

TIMER_FIELDNAMES = [
    "response_timer_sec",
    "prediction_timed_out",
    "behavioral_timed_out",
]

TRIAL_FIELDNAMES = REFERENCE_FIELDNAMES + TIMER_FIELDNAMES
DEFAULT_TRIAL_FIELDNAMES = TRIAL_FIELDNAMES
