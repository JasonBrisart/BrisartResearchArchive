"""
File: frameworks/TFL/settings.py

Purpose:
Hold every tunable TFL behavior setting in one place. Changing how a
TFL run is structured, timed, scored, or defaulted means editing this
file and nothing else.

Communication / relationships:
- frameworks/TFL/config.py builds DEFAULT_CONFIG and the default
  startup options from these constants.
- frameworks/TFL/framework.py re-exports BASE_STIMULUS_LIMIT and the
  prompt and intro text.
- frameworks/TFL/trial_builder.py validates against VALID_BLOCKS and
  VALID_FEEDBACK_LEVELS.
- frameworks/TFL/engine.py uses TRIAL_DURATION_SEC.
- frameworks/TFL/session_gui.py uses AUTOSAVE_INTERVAL_TRIALS.
- A pure-data leaf module: imports nothing from the TFL package or
  Tkinter, so it can never create a circular import.

Settings / parameters:
- TRIAL_DURATION_SEC 12; AUTOSAVE_INTERVAL_TRIALS 5.
- NUM_TRIALS 120; TRIALS_PER_BLOCK 40; BLOCKS affect, belief,
  contradiction.
- PROBE_INTERVAL 4; DELAYED_REENTRY_INTERVAL 6; PERTURBATION_INTERVAL 5.
- RANDOM_SEED 2026; AFFECT_MIN 0; AFFECT_MAX 100; BASE_STIMULUS_LIMIT 20.
- FEEDBACK_LEVELS, PERTURBATION_TYPES, default run-option toggles,
  RUN_MODE, DEFAULT_MODE_DESCRIPTION, prompts, and intro text.

Edge cases:
- An interval of 0 disables that feature entirely.
- The trial builder caps a run at TRIALS_PER_BLOCK * len(BLOCKS).
- A new block or feedback level must also be added to VALID_BLOCKS or
  VALID_FEEDBACK_LEVELS, or the trial builder rejects it.

Known limitations:
- Stimulus content lives in frameworks/TFL/stimuli.py, not here.
- Editing values changes run structure, but the recorded run_mode label
  stays "default_tfl" unless RUN_MODE is changed too.
- frameworks/TFL/screen.py defines its own button choice tuples.

Examples:
- TRIAL_DURATION_SEC = 15
- PERTURBATION_INTERVAL = 0
"""
from __future__ import annotations
# ============================================================
# Timing
# ============================================================
# Seconds a timed stage (prediction, behavioral_choice) stays open before
# it auto-advances as a timeout. Used by engine.begin_stage().
TRIAL_DURATION_SEC = 12
# How often (in completed trials) an in-progress GUI run is checkpointed
# to disk, so a crash never loses more than this many trials. Used by
# session_gui.TFLGuiSession._autosave_if_due().
AUTOSAVE_INTERVAL_TRIALS = 5
# ============================================================
# Trial structure
# ============================================================
# Total trials in a full run, and how many trials each block holds. The
# builder caps the run at TRIALS_PER_BLOCK * len(BLOCKS).
NUM_TRIALS = 120
TRIALS_PER_BLOCK = 40
# The block sequence a run cycles through, in order.
BLOCKS = ["affect", "belief", "contradiction"]
# ============================================================
# Intervals (every Nth trial). 0 disables that feature entirely.
# ============================================================
PROBE_INTERVAL = 4
DELAYED_REENTRY_INTERVAL = 6
PERTURBATION_INTERVAL = 5
# ============================================================
# Determinism
# ============================================================
# Fixed seed so a given config always yields the same trial sequence.
RANDOM_SEED = 2026
# ============================================================
# Affect rating range
# ============================================================
AFFECT_MIN = 0
AFFECT_MAX = 100
AFFECT_SCALE = [AFFECT_MIN, AFFECT_MAX]
# ============================================================
# Stimulus selection
# ============================================================
# Number of stimuli used by default (the first N of the embedded library
# in stimuli.py). Overridden only when a run enables extra stimuli.
BASE_STIMULUS_LIMIT = 20
# ============================================================
# Feedback
# ============================================================
FEEDBACK_LEVELS = ["confirmatory", "mildly_contradictory", "strongly_contradictory"]
# What the trial builder will ACCEPT (a superset guard, not an ordering).
VALID_FEEDBACK_LEVELS = {"confirmatory", "mildly_contradictory", "strongly_contradictory"}
# ============================================================
# Perturbation
# ============================================================
PERTURBATION_TYPES = ["head_turn", "posture_shift", "scene_shift", "breath_reset"]
# ============================================================
# Block validation
# ============================================================
VALID_BLOCKS = {"affect", "belief", "contradiction"}
# ============================================================
# Default run-option toggles (the "official default TFL startup")
# ============================================================
DEFAULT_ENABLE_EXTRA_STIMULI = False
DEFAULT_ENABLE_PERTURBATIONS = False
DEFAULT_ENABLE_PROBES = True
DEFAULT_ENABLE_DELAYED_REENTRY = True
RUN_MODE = "default_tfl"
DEFAULT_MODE_DESCRIPTION = [
    "Default TFL",
    "First 20 stimuli only",
    "Extra stimuli OFF",
    "Perturbations OFF",
    "Probes ON",
    "Delayed reentry ON",
]
# ============================================================
# Prompts and on-screen text
# ============================================================
PREDICTION_PROMPT = "\nPredicted interpretation (A/B): "
PREDICTION_CHOICES = ["A", "B"]
PROBE_CHOICES = ["A", "B", "U"]
SESSION_INTRO_TEXT = (
    "You will see ambiguous stimuli with two possible interpretations.\n"
    "A = Interpretation A\n"
    "B = Interpretation B\n"
    "Use A or B only for prediction and behavioral choice.\n"
    "Affect rating must be 0-100."
)
