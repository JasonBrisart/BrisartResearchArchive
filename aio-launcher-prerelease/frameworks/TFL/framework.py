"""
File: frameworks/TFL/framework.py

Purpose
-------
Define TFL's identity and FRAMEWORK_METADATA for discovery, re-export
constants and the CSV schema, and provide lazy wrappers.

Communication / relationships
-----------------------------
- config/registries.py discovers TFL through FRAMEWORK_METADATA.
- services/framework_service.py launches runner_module/runner_class.
- cli.py launches cli_module/cli_function.
- Re-exports values from settings.py and schema.py.

Settings / parameters
---------------------
- runner: frameworks.TFL.session_gui.TFLGuiSession.
- cli: frameworks.TFL.cli_runner.run_cli.
- analysis: frameworks.TFL.analysis.analyze_output.
- results_filename: tfl_output.csv.

Edge cases
----------
- Wrappers import submodules lazily, so one broken submodule cannot
  break framework discovery.

Known limitations
-----------------
- Changing status away from "Available" hides the Run button and blocks
  launch in both front ends.

Examples
--------
- from frameworks.TFL import framework
- framework.analyze_output()
"""
from __future__ import annotations

from pathlib import Path

from . import settings
from .schema import TRIAL_FIELDNAMES

FRAMEWORK_ID = settings.FRAMEWORK_ID
FRAMEWORK_NAME = settings.FRAMEWORK_NAME
VERSION_LABEL = settings.VERSION_LABEL
FRAMEWORK_DESCRIPTION = (
    "02_Execution reference procedure for ambiguity, belief, contradiction, "
    "probes, delayed reentry, and optional perturbations, with an optional "
    "response timer."
)
FRAMEWORK_FEATURES = [
    "Reference trial generation",
    "Prediction, affect, and behavioral choice",
    "Contradiction feedback",
    "Probes and delayed reentry",
    "Optional perturbations",
    "Optional response timer",
    "Standard-library CSV output and analysis",
    "GUI and command-line runners",
]

FRAMEWORK_METADATA = {
    "id": FRAMEWORK_ID,
    "name": FRAMEWORK_NAME,
    "status": "Available",
    "module": "frameworks.TFL.framework",
    "runner_module": "frameworks.TFL.session_gui",
    "runner_class": "TFLGuiSession",
    "cli_module": "frameworks.TFL.cli_runner",
    "cli_function": "run_cli",
    "analysis_module": "frameworks.TFL.analysis",
    "results_filename": settings.OUTPUT_FILENAME,
    "description": FRAMEWORK_DESCRIPTION,
    "features": FRAMEWORK_FEATURES,
}

TFL_DIR = Path(__file__).resolve().parent
BASE_STIMULUS_LIMIT = settings.BASE_STIMULUS_LIMIT
PREDICTION_PROMPT = settings.PREDICTION_PROMPT
PREDICTION_CHOICES = list(settings.PREDICTION_CHOICES)
SESSION_INTRO_TEXT = settings.SESSION_INTRO_TEXT
CSV_FIELDNAMES = TRIAL_FIELDNAMES


def get_output_dir() -> Path:
    from .output import default_output_dir
    return default_output_dir()


def get_output_file() -> Path:
    return get_output_dir() / settings.OUTPUT_FILENAME


def apply_default_options(config=None):
    from .config import apply_default_options as _apply
    return _apply(config)


def get_default_config():
    from .config import get_default_config as _get
    return _get()


def get_raw_config():
    from .config import get_raw_config as _get
    return _get()


def load_stimuli():
    from .stimuli import load_stimuli as _load
    return _load()


def apply_stimulus_limit(stimuli, config):
    from .stimuli import apply_stimulus_limit as _apply
    return _apply(stimuli, config)


def build_trials(config, stimuli):
    from .trial_builder import build_trials as _build
    return _build(config, stimuli)


def determine_feedback(prediction, feedback_level):
    from .feedback import determine_feedback as _determine
    return _determine(prediction, feedback_level)


def make_perturbation_instruction(perturbation_type):
    from .feedback import make_perturbation_instruction as _make
    return _make(perturbation_type)


def load_output(path=None):
    from .analysis import load_output as _load
    return _load(path)


def analyze_output(path=None):
    from .analysis import analyze_output as _analyze
    return _analyze(path)
