"""
frameworks/TFL/framework.py
TFL framework identity, metadata, paths, experiment constants, and output
schema -- the single module config.registries discovers (via
FRAMEWORK_METADATA) to register TFL, and the stable public surface other
layers import from.

BASE_STIMULUS_LIMIT / PREDICTION_PROMPT / PREDICTION_CHOICES /
SESSION_INTRO_TEXT are re-exported from frameworks/TFL/settings.py, THE
single place to edit TFL's tunable behavior. This module's own copies
were removed so there is exactly one source of truth for these values
instead of two that could silently drift apart.

The lazy re-export wrappers at the bottom (apply_default_options,
load_stimuli, build_trials, analyze_output, ...) forward to the real
implementations in config.py / stimuli.py / trial_builder.py /
feedback.py / analysis.py without importing them at module-load time, so
one broken submodule can't break framework discovery itself -- discovery
only needs FRAMEWORK_METADATA, which is defined here directly.
"""
from __future__ import annotations
from pathlib import Path

from config.runtime import get_framework_output_dir
from frameworks.shared.schema import DEFAULT_TRIAL_FIELDNAMES
from frameworks.TFL import settings

# ============================================================
# Framework Identity
# ============================================================
FRAMEWORK_ID = "TFL"
FRAMEWORK_NAME = "Temporal Feedback Loop"
VERSION_LABEL = "TFL Baseline Reference Implementation"
FRAMEWORK_DESCRIPTION = (
    "Recursive affect-modulated simulation framework for ambiguity, "
    "belief, contradiction, probes, delayed reentry, and optional "
    "perturbation testing."
)
FRAMEWORK_FEATURES = [
    "Ambiguous stimuli",
    "Prediction collection",
    "Affect ratings",
    "Prior/belief conditions",
    "Contradiction feedback",
    "Probe system",
    "Delayed reentry",
    "Optional perturbations",
    "CSV output and analysis",
]
FRAMEWORK_METADATA = {
    "id": FRAMEWORK_ID,
    "name": FRAMEWORK_NAME,
    "status": "Available",
    "module": "frameworks.TFL.framework",
    "runner_module": "frameworks.TFL.session_gui",
    "runner_class": "TFLGuiSession",
    "description": FRAMEWORK_DESCRIPTION,
    "features": FRAMEWORK_FEATURES,
}

# ============================================================
# Paths
# ============================================================
TFL_DIR = Path(__file__).resolve().parent


def get_output_dir() -> Path:
    """
    Return the current configured TFL output directory. Resolved
    dynamically on every call so changes to application settings don't
    leave active code using a stale import-time output path.
    """
    return get_framework_output_dir(FRAMEWORK_ID)


def get_output_file() -> Path:
    return get_output_dir() / "tfl_output_latest.csv"


# ============================================================
# Experiment Constants -- re-exported from settings.py
# (see that module for the actual values; edit them THERE, not here)
# ============================================================
BASE_STIMULUS_LIMIT = settings.BASE_STIMULUS_LIMIT
PREDICTION_PROMPT = settings.PREDICTION_PROMPT
PREDICTION_CHOICES = list(settings.PREDICTION_CHOICES)
SESSION_INTRO_TEXT = settings.SESSION_INTRO_TEXT

# ============================================================
# Output Schema
# ============================================================
CSV_FIELDNAMES = DEFAULT_TRIAL_FIELDNAMES

# ============================================================
# Lazy re-exports
# ============================================================
# These wrappers preserve stable public entry points without eagerly
# loading the rest of the TFL implementation during metadata discovery,
# so one broken submodule doesn't break framework discovery itself.
def apply_default_options(config=None):
    from .config import apply_default_options as _apply_default_options
    return _apply_default_options(config)


def get_default_config():
    from .config import get_default_config as _get_default_config
    return _get_default_config()


def get_raw_config():
    from .config import get_raw_config as _get_raw_config
    return _get_raw_config()


def load_stimuli():
    from .stimuli import load_stimuli as _load_stimuli
    return _load_stimuli()


def apply_stimulus_limit(stimuli, config):
    from .stimuli import apply_stimulus_limit as _apply_stimulus_limit
    return _apply_stimulus_limit(stimuli, config)


def build_trials(config, stimuli):
    from .trial_builder import build_trials as _build_trials
    return _build_trials(config, stimuli)


def determine_feedback(prediction, feedback_level):
    from .feedback import determine_feedback as _determine_feedback
    return _determine_feedback(prediction, feedback_level)


def make_perturbation_instruction(perturbation_type):
    from .feedback import make_perturbation_instruction as _make_perturbation_instruction
    return _make_perturbation_instruction(perturbation_type)


def save_rows(rows, path=None):
    from .analysis import save_rows as _save_rows
    return _save_rows(rows, path)


def load_output(path=None):
    from .analysis import load_output as _load_output
    return _load_output(path)


def analyze_output(path=None):
    from .analysis import analyze_output as _analyze_output
    return _analyze_output(path)
