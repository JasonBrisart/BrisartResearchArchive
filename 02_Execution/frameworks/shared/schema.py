"""
Shared trial-row schema.
Uses the fuller field set (includes *_timed_out and completion_status)
so the engine can distinguish a timeout from an active response.

session_id/participant_id/started_at_iso/completed_at_iso were added so
multiple participants and multiple sessions can be told apart in output
data - previously every run wrote to the same identity-less CSV.
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
