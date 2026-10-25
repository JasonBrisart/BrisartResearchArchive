"""
File: frameworks/TFL/settings.py

Purpose
-------
Hold every fixed TFL constant and every option default in one place. The
defaults reproduce the 02_Execution TFL Baseline Reference Implementation
v2.6 exactly; every Archive option is off or at its reference value by
default.

Communication / relationships
-----------------------------
- Imported by every other frameworks/TFL/ module; imports nothing itself, so it can
  never create a circular import.
- frameworks/TFL/config.py turns these defaults into run configurations and the
  option table shared by the GUI and the CLI.

Settings / parameters
---------------------
- Reference structure: 3 blocks (affect, belief, contradiction) x 40
  trials; probes every 4th trial; delayed reentry every 6th trial within
  a block; perturbations every 5th trial when enabled; seed 2026; first
  20 stimuli.
- Option limits: trials per block 1-200; intervals 1-50; timer 3-120 s;
  seed 0-2147483647; session label up to 40 characters.
- Output file names: tfl_output_[label_]YYYY-MM-DD_HH-MM-SS.csv.

Edge cases
----------
- Changing a default here changes what "Default TFL" means; runs are
  labelled default_tfl only when every protocol option matches these
  values.

Known limitations
-----------------
- Reference wording is reproduced verbatim, including the en dash in the
  affect prompt; non-UTF-8 consoles may render it differently.

Examples
--------
- settings.TRIALS_PER_BLOCK
- settings.DEFAULT_ENABLE_RESPONSE_TIMER
"""
# ============================================================
# Identity and reference wording
# ============================================================
FRAMEWORK_ID = "TFL"
FRAMEWORK_NAME = "Temporal Feedback Loop"
VERSION_LABEL = "TFL Baseline Reference Implementation v2.6"

PREDICTION_PROMPT = "\nPredicted interpretation (A/B): "
AFFECT_PROMPT = "Affect intensity for this prediction (0\u2013100): "
BEHAVIORAL_PROMPT = "Final behavioral choice (A/B): "
POST_PERTURBATION_PROMPT = "Which interpretation is most active immediately after the perturbation? (A/B/U): "
CONTENT_PROBE_PROMPT = "Which interpretation is most active in your mind right now? (A/B/U for uncodable): "

SESSION_INTRO_TEXT = (
    "You will see ambiguous stimuli with two possible interpretations.\n"
    "A = Interpretation A\n"
    "B = Interpretation B\n"
    "Use A or B only for prediction and behavioral choice.\n"
    "Affect rating must be 0\u2013100."
)

# ============================================================
# Fixed protocol constants
# ============================================================
BLOCKS = ["affect", "belief", "contradiction"]
FEEDBACK_LEVELS = ["confirmatory", "mildly_contradictory", "strongly_contradictory"]
PERTURBATION_TYPES = ["head_turn", "posture_shift", "scene_shift", "breath_reset"]
AFFECT_MIN = 0
AFFECT_MAX = 100
BASE_STIMULUS_LIMIT = 20

RUN_MODE = "default_tfl"
MODIFIED_RUN_MODE = "modified_tfl"

# ============================================================
# Option defaults (reference values)
# ============================================================
DEFAULT_ENABLE_EXTRA_STIMULI = False
DEFAULT_ENABLE_PERTURBATIONS = False
DEFAULT_ENABLE_PROBES = True
DEFAULT_ENABLE_DELAYED_REENTRY = True
DEFAULT_ENABLE_RESPONSE_TIMER = False
DEFAULT_SHUFFLE_BLOCKS = False

TRIAL_DURATION_SEC = 12
TRIALS_PER_BLOCK = 40
PROBE_INTERVAL = 4
DELAYED_REENTRY_INTERVAL = 6
PERTURBATION_INTERVAL = 5
RANDOM_SEED = 2026
SESSION_LABEL = ""

# ============================================================
# Option limits
# ============================================================
RESPONSE_TIMER_MIN_SEC = 3
RESPONSE_TIMER_MAX_SEC = 120
TRIALS_PER_BLOCK_MIN = 1
TRIALS_PER_BLOCK_MAX = 200
INTERVAL_MIN = 1
INTERVAL_MAX = 50
SEED_MAX = 2**31 - 1
SESSION_LABEL_MAX_LENGTH = 40

# ============================================================
# Output
# ============================================================
OUTPUT_FILE_PREFIX = "tfl_output"
OUTPUT_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
