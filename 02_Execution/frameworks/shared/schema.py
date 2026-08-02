"""
Shared trial-row schema.
Uses the fuller field set (includes *_timed_out and completion_status)
so the engine can distinguish a timeout from an active response.
"""

DEFAULT_TRIAL_FIELDNAMES = [
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
]
