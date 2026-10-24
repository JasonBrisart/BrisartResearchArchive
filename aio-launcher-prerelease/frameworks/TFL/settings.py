"""
File: frameworks/TFL/settings.py

Purpose
-------
Hold every tunable TFL value in one place. The defaults reproduce the
02_Execution TFL Baseline Reference Implementation v2.6; the optional
response timer is the only addition and is off by default.

Communication / relationships
-----------------------------
- frameworks/TFL/config.py builds run configurations from these values.
- frameworks/TFL/framework.py re-exports the identity and prompt text.
- frameworks/TFL/trial_builder.py, engine.py, options_screen.py, and
  cli_runner.py read the values through config.py.
- Pure-data leaf module: imports nothing, so it can never create a
  circular import.

Settings / parameters
---------------------
- TRIALS_PER_BLOCK 40 x BLOCKS (affect, belief, contradiction) = 120 trials.
- PROBE_INTERVAL 4; DELAYED_REENTRY_INTERVAL 6; PERTURBATION_INTERVAL 5.
- RANDOM_SEED 2026; BASE_STIMULUS_LIMIT 20; AFFECT_MIN 0; AFFECT_MAX 100.
- DEFAULT_ENABLE_RESPONSE_TIMER False; TRIAL_DURATION_SEC 12 (used only
  when the timer is enabled); RESPONSE_TIMER_MIN_SEC 3,
  RESPONSE_TIMER_MAX_SEC 120.

Edge cases
----------
- NUM_TRIALS is informational, exactly as in the reference: the trial
  count is always TRIALS_PER_BLOCK * len(BLOCKS).
- An interval of 0 disables that feature.

Known limitations
-----------------
- Editing structural values (blocks, intervals, seed) changes the
  protocol away from the reference; the run is still labelled by the
  four toggles and the timer only, as in the reference.

Examples
--------
- TRIAL_DURATION_SEC = 15
- DEFAULT_ENABLE_RESPONSE_TIMER = False
"""
from __future__ import annotations

# ============================================================
# Identity and on-screen text (02_Execution reference wording)
# ============================================================
FRAMEWORK_ID = "TFL"
FRAMEWORK_NAME = "Temporal Feedback Loop"
VERSION_LABEL = "TFL Baseline Reference Implementation v2.6"

PREDICTION_PROMPT = "\nPredicted interpretation (A/B): "
PREDICTION_CHOICES = ["A", "B"]
PROBE_CHOICES = ["A", "B", "U"]

SESSION_INTRO_TEXT = (
    "You will see ambiguous stimuli with two possible interpretations.\n"
    "A = Interpretation A\n"
    "B = Interpretation B\n"
    "Use A or B only for prediction and behavioral choice.\n"
    "Affect rating must be 0\u2013100."
)

# ============================================================
# Trial structure
# ============================================================
NUM_TRIALS = 120
TRIALS_PER_BLOCK = 40
BLOCKS = ["affect", "belief", "contradiction"]

PROBE_INTERVAL = 4
DELAYED_REENTRY_INTERVAL = 6
PERTURBATION_INTERVAL = 5

RANDOM_SEED = 2026

AFFECT_MIN = 0
AFFECT_MAX = 100
AFFECT_SCALE = [AFFECT_MIN, AFFECT_MAX]

BASE_STIMULUS_LIMIT = 20

FEEDBACK_LEVELS = ["confirmatory", "mildly_contradictory", "strongly_contradictory"]
PERTURBATION_TYPES = ["head_turn", "posture_shift", "scene_shift", "breath_reset"]

# ============================================================
# Default run options ("Default TFL")
# ============================================================
DEFAULT_ENABLE_EXTRA_STIMULI = False
DEFAULT_ENABLE_PERTURBATIONS = False
DEFAULT_ENABLE_PROBES = True
DEFAULT_ENABLE_DELAYED_REENTRY = True

RUN_MODE = "default_tfl"
MODIFIED_RUN_MODE = "modified_tfl"

DEFAULT_MODE_DESCRIPTION = [
    "Default TFL",
    "First 20 stimuli only",
    "Extra stimuli OFF",
    "Perturbations OFF",
    "Probes ON",
    "Delayed reentry ON",
    "Response timer OFF",
]

# ============================================================
# Optional response timer (an Archive addition; OFF = reference)
# ============================================================
DEFAULT_ENABLE_RESPONSE_TIMER = False
TRIAL_DURATION_SEC = 12
RESPONSE_TIMER_MIN_SEC = 3
RESPONSE_TIMER_MAX_SEC = 120

# ============================================================
# Output
# ============================================================
OUTPUT_FILENAME = "tfl_output.csv"
SESSION_FILE_PREFIX = "tfl_output_"
