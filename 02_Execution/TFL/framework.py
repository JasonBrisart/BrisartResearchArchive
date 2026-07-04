import random
from pathlib import Path

from shared.output_schema import DEFAULT_TRIAL_FIELDNAMES


FRAMEWORK_ID = "TFL"
FRAMEWORK_NAME = "Temporal Feedback Loop"

TFL_DIR = Path(__file__).resolve().parent

CONFIG_FILE = TFL_DIR / "config.json"
STIMULI_FILE = TFL_DIR / "stimuli" / "tfl_stimuli.csv"
DATA_DIR = TFL_DIR / "data"
OUTPUT_FILE = DATA_DIR / "tfl_output.csv"

VERSION_LABEL = "TFL Baseline Reference Implementation v2.6"

BASE_STIMULUS_LIMIT = 20

PREDICTION_PROMPT = "\nPredicted interpretation (A/B): "
PREDICTION_CHOICES = ["A", "B"]

CSV_FIELDNAMES = DEFAULT_TRIAL_FIELDNAMES

DEFAULT_MODE_DESCRIPTION = [
    "Default TFL",
    "First 20 stimuli only",
    "Extra stimuli OFF",
    "Perturbations OFF",
    "Probes ON",
    "Delayed reentry ON",
]

SESSION_INTRO_TEXT = (
    "You will see ambiguous stimuli with two possible interpretations.\n"
    "A = Interpretation A\n"
    "B = Interpretation B\n"
    "Use A or B only for prediction and behavioral choice.\n"
    "Affect rating must be 0–100."
)

DEFAULT_BLOCKS = [
    "affect",
    "belief",
    "contradiction",
]

DEFAULT_PERTURBATION_TYPES = [
    "head_turn",
    "posture_shift",
    "scene_shift",
    "breath_reset",
]


def apply_default_options(config):
    """
    Default startup:
    - Default TFL only
    - First 20 stimuli only
    - Extra stimuli OFF
    - Perturbations OFF
    - Probes ON
    - Delayed reentry ON
    """

    config = dict(config)

    config["run_mode"] = "default_tfl"

    config.setdefault("blocks", DEFAULT_BLOCKS)
    config.setdefault("trials_per_block", 40)
    config.setdefault("probe_interval", 4)
    config.setdefault("delayed_reentry_interval", 6)
    config.setdefault("perturbation_interval", 5)
    config.setdefault("perturbation_types", DEFAULT_PERTURBATION_TYPES)

    config["enable_extra_stimuli"] = False
    config["enable_perturbations"] = False
    config["enable_probes"] = True
    config["enable_delayed_reentry"] = True

    return config


def build_trials(config, stimuli):
    random.seed(config.get("random_seed", None))

    blocks = config["blocks"]
    trials_per_block = config["trials_per_block"]

    probe_interval = config.get("probe_interval", 0)
    delayed_reentry_interval = config.get("delayed_reentry_interval", 0)

    enable_probes = config.get("enable_probes", True)
    enable_delayed_reentry = config.get("enable_delayed_reentry", True)
    enable_perturbations = config.get("enable_perturbations", False)

    perturbation_interval = (
        config.get("perturbation_interval", 0)
        if enable_perturbations
        else 0
    )

    perturbation_types = config.get(
        "perturbation_types",
        DEFAULT_PERTURBATION_TYPES,
    )

    trials = []
    trial_id = 1

    for block in blocks:
        for block_trial_num in range(1, trials_per_block + 1):
            stimulus = random.choice(stimuli)
            prior = random.choice(["A", "B"])

            probe_trial = should_use_probe(
                enable_probes=enable_probes,
                probe_interval=probe_interval,
                trial_id=trial_id,
            )

            delayed_reentry, recurrence_source_trial, stimulus = handle_delayed_reentry(
                enable_delayed_reentry=enable_delayed_reentry,
                delayed_reentry_interval=delayed_reentry_interval,
                trial_id=trial_id,
                block_trial_num=block_trial_num,
                trials=trials,
                current_stimulus=stimulus,
            )

            perturbation_trial, perturbation_type = select_perturbation(
                perturbation_interval=perturbation_interval,
                perturbation_types=perturbation_types,
                trial_id=trial_id,
            )

            trials.append({
                "trial_id": trial_id,
                "framework_id": FRAMEWORK_ID,
                "run_mode": config.get("run_mode", "default_tfl"),
                "block": block,
                "block_trial_num": block_trial_num,
                "stimulus_id": stimulus["stimulus_id"],
                "cue": stimulus["cue"],
                "ambiguous_text": stimulus["ambiguous_text"],
                "interpretation_a": stimulus["interpretation_a"],
                "interpretation_b": stimulus["interpretation_b"],
                "prior_instruction": prior,
                "feedback_level": select_feedback_level(block),
                "probe_trial": probe_trial,
                "delayed_reentry": delayed_reentry,
                "recurrence_source_trial": recurrence_source_trial,
                "perturbation_trial": perturbation_trial,
                "perturbation_type": perturbation_type,
            })

            trial_id += 1

    return trials


def should_use_probe(enable_probes, probe_interval, trial_id):
    if not enable_probes:
        return False

    if not probe_interval or probe_interval <= 0:
        return False

    return trial_id % probe_interval == 0


def handle_delayed_reentry(
    enable_delayed_reentry,
    delayed_reentry_interval,
    trial_id,
    block_trial_num,
    trials,
    current_stimulus,
):
    if not enable_delayed_reentry:
        return False, "", current_stimulus

    if not delayed_reentry_interval or delayed_reentry_interval <= 0:
        return False, "", current_stimulus

    if trial_id <= delayed_reentry_interval:
        return False, "", current_stimulus

    if block_trial_num % delayed_reentry_interval != 0:
        return False, "", current_stimulus

    source_trial = trials[-delayed_reentry_interval]

    stimulus = {
        "stimulus_id": source_trial["stimulus_id"],
        "cue": source_trial["cue"],
        "ambiguous_text": source_trial["ambiguous_text"],
        "interpretation_a": source_trial["interpretation_a"],
        "interpretation_b": source_trial["interpretation_b"],
    }

    return True, source_trial["trial_id"], stimulus


def select_feedback_level(block):
    if block == "affect":
        return "neutral"

    if block == "belief":
        return "confirmatory"

    if block == "contradiction":
        return random.choice([
            "confirmatory",
            "mildly_contradictory",
            "strongly_contradictory",
        ])

    return "neutral"


def select_perturbation(perturbation_interval, perturbation_types, trial_id):
    if not perturbation_interval or perturbation_interval <= 0:
        return False, ""

    if trial_id % perturbation_interval != 0:
        return False, ""

    return True, random.choice(perturbation_types)


def opposite_choice(choice):
    if choice == "A":
        return "B"

    if choice == "B":
        return "A"

    return ""


def determine_feedback(prediction, feedback_level):
    if feedback_level == "confirmatory":
        correct_answer = prediction
        contradiction = "none"

    elif feedback_level == "mildly_contradictory":
        correct_answer = opposite_choice(prediction)
        contradiction = "mild"

    elif feedback_level == "strongly_contradictory":
        correct_answer = opposite_choice(prediction)
        contradiction = "strong"

    else:
        correct_answer = ""
        contradiction = "none"

    return correct_answer, contradiction


def show_feedback(feedback_level, prediction, correct_answer):
    if feedback_level == "neutral":
        print("Feedback: No outcome feedback on this trial.")

    elif feedback_level == "confirmatory":
        print(f"Feedback: Confirmed. Interpretation {prediction} was supported.")

    elif feedback_level == "mildly_contradictory":
        print(
            f"Feedback: Mild contradiction. Your prediction was {prediction}, "
            f"but Interpretation {correct_answer} is somewhat better supported."
        )

    elif feedback_level == "strongly_contradictory":
        print(
            f"Feedback: Strong contradiction. Your prediction was {prediction}, "
            f"but Interpretation {correct_answer} is strongly supported."
        )


def make_perturbation_instruction(perturbation_type):
    instructions = {
        "head_turn": "Turn your head slowly to one side, then return to center.",
        "posture_shift": "Change your sitting posture noticeably, then settle into the new posture.",
        "scene_shift": "Look away from the screen toward a different area of the room for 3 seconds, then return.",
        "breath_reset": "Take one slow breath in and out before continuing.",
    }

    return instructions.get(
        perturbation_type,
        "Change posture or gaze briefly, then continue."
    )