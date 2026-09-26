"""
File: frameworks/shared/schema.py

Purpose:
Define DEFAULT_TRIAL_FIELDNAMES, the shared column order for framework
trial rows written to CSV.

Communication / relationships:
- frameworks/TFL/framework.py re-exports it as CSV_FIELDNAMES.
- frameworks/TFL/analysis.py uses it to validate and write rows.
- frameworks/TFL/engine.py builds rows with exactly these keys.

Settings / parameters:
- 34 columns, including session_id and participant_id identity fields,
  prediction_timed_out and behavioral_timed_out flags,
  completion_status, and trial_started_at_iso/trial_completed_at_iso.

Edge cases:
- analysis.validate_rows() rejects any row containing a field that is
  not in this list.
- The list order is the CSV header order.

Known limitations:
- The columns are TFL-shaped; future frameworks may need their own
  schema.
- Renaming or reordering columns breaks compatibility with CSVs already
  produced.

Examples:
- from frameworks.shared.schema import DEFAULT_TRIAL_FIELDNAMES
"""

DEFAULT_TRIAL_FIELDNAMES = [
    "session_id",
    "participant_id",
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
    "prediction_timed_out",
    "affect",
    "behavioral_choice",
    "behavioral_rt",
    "behavioral_timed_out",
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
    "completion_status",
    "trial_started_at_iso",
    "trial_completed_at_iso",
]
