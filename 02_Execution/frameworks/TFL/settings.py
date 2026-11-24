"""
File: frameworks/TFL/settings.py

Purpose
-------
Hold every fixed TFL constant and every option default in one place. The
trial structure and the console wording come from the 02_Execution TFL
Baseline Reference Implementation v2.6, which this framework was rebuilt
from; the Archive differs from it by default in two ways: the 12-second
response timer is on, and affect is rated on five fixed values instead of a
typed 0 to 100.

Communication / relationships
-----------------------------
- Imported by every other frameworks/TFL/ module and by
  gui/pages/tfl_page.py; imports nothing itself, so it can never create a
  circular import.
- frameworks/TFL/config.py turns these defaults into run configurations
  and the option table shared by the GUI and the CLI.

Settings / parameters
---------------------
- Default run: 3 blocks (affect, belief, contradiction) of 40 trials;
  response timer on at 12 seconds; probes every 4th trial; delayed
  reentry every 6th trial within a block; perturbations every 5th trial
  when enabled; seed 2026; the first 20 stimuli.
- Option limits: trials per block 1-200; intervals 1-50; timer 3-120 s;
  seed 0-2147483647; session label up to 40 characters.
- AFFECT_CHOICES: the five values an affect rating can take, 0, 25, 50, 75,
  and 100. The engine accepts only these; the GUI shows them as buttons and
  the console asks for one of them.
- Protocol identity: PROTOCOL_EDITION is the reproducibility identifier written
  to every new session and PROTOCOL_LABEL is shown by the GUI and CLI.
- Reference wording: the session intro and the CLI prompts.
- Output file names: tfl_output_[label_]YYYY-MM-DD_HH-MM-SS.csv.

Edge cases
----------
- Changing AFFECT_CHOICES changes what values new sessions contain; session
  files already saved keep their values and still analyze.
- Changing a default here changes what "Default TFL" means; runs are
  labelled default_tfl only when every protocol option matches these
  values. Turning the timer off, for instance, makes a run modified_tfl.
- The "Default TFL" description shown on the options screens and the TFL
  page is generated from these values by config.default_mode_description(),
  so changing a default here updates every place that describes it.

Known limitations
-----------------
- The affect rating differs from the reference, which accepted any whole
  number from 0 to 100; sessions from this scale cannot be compared value
  for value with typed ratings.
- The CLI uses these prompts; the GUI screens use their own shorter
  question text (frameworks/TFL/gui_screens.py).

Examples
--------
- settings.PROTOCOL_LABEL
- settings.TRIALS_PER_BLOCK
- settings.DEFAULT_ENABLE_RESPONSE_TIMER
"""
# ============================================================
# Identity and reference wording
# ============================================================
FRAMEWORK_ID = "TFL"
FRAMEWORK_NAME = "Temporal Feedback Loop"
PROTOCOL_EDITION = "3.0"
PROTOCOL_LABEL = f"{FRAMEWORK_NAME} — Protocol Edition {PROTOCOL_EDITION}"

# Protocol edition history (oldest first). Keep this record in the owning file.
# 2.6 — Baseline reference: untimed by default; typed whole-number affect 0-100.
# 3.0 — Archive protocol: 12-second default response timer; fixed affect choices
#       0, 25, 50, 75, and 100. The trial-generation algorithm, stimulus library,
#       feedback wording, probes, delayed reentry, and perturbations retain the
#       documented 2.6 reference lineage.

PREDICTION_PROMPT = "\nPredicted interpretation (A/B): "
AFFECT_PROMPT = "Affect intensity for this prediction (0, 25, 50, 75, or 100): "
BEHAVIORAL_PROMPT = "Final behavioral choice (A/B): "
POST_PERTURBATION_PROMPT = "Which interpretation is most active immediately after the perturbation? (A/B/U): "
CONTENT_PROBE_PROMPT = "Which interpretation is most active in your mind right now? (A/B/U for uncodable): "

SESSION_INTRO_TEXT = (
    "You will see ambiguous stimuli with two possible interpretations.\n"
    "A = Interpretation A\n"
    "B = Interpretation B\n"
    "Use A or B only for prediction and behavioral choice.\n"
    "Affect rating must be 0, 25, 50, 75, or 100."
)

# ============================================================
# Fixed protocol constants
# ============================================================
BLOCKS = ["affect", "belief", "contradiction"]
FEEDBACK_LEVELS = ["confirmatory", "mildly_contradictory", "strongly_contradictory"]
PERTURBATION_TYPES = ["head_turn", "posture_shift", "scene_shift", "breath_reset"]
AFFECT_CHOICES = (0, 25, 50, 75, 100)
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
DEFAULT_ENABLE_RESPONSE_TIMER = True
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


