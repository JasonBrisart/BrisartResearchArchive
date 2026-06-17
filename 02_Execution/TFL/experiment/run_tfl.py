import csv
import json
import random
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

DATA_DIR = ROOT_DIR / "data"
STIM_DIR = ROOT_DIR / "stimuli"

CONFIG_FILE = BASE_DIR / "config.json"
STIM_FILE = STIM_DIR / "tfl_stimuli.csv"
DATA_FILE = DATA_DIR / "tfl_output.csv"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_stimuli():
    if not STIM_FILE.exists():
        raise FileNotFoundError(f"Stimulus file not found: {STIM_FILE}")

    with open(STIM_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        stimuli = list(reader)

    if not stimuli:
        raise ValueError("Stimulus file is empty.")

    return stimuli


def get_valid_choice(prompt, allowed):
    allowed_upper = [x.upper() for x in allowed]

    while True:
        response = input(prompt).strip().upper()

        if response in allowed_upper:
            return response

        print(f"Please enter one of: {', '.join(allowed_upper)}")


def get_affect_rating(prompt, min_value=0, max_value=100):
    while True:
        response = input(prompt).strip()

        try:
            value = int(response)
            if min_value <= value <= max_value:
                return value
        except ValueError:
            pass

        print(f"Please enter a whole number from {min_value} to {max_value}.")


def opposite_choice(choice):
    if choice == "A":
        return "B"
    if choice == "B":
        return "A"
    return ""


def make_trials(config, stimuli):
    random.seed(config.get("random_seed", None))

    blocks = config["blocks"]
    trials_per_block = config["trials_per_block"]
    probe_interval = config["probe_interval"]
    delayed_reentry_interval = config["delayed_reentry_interval"]

    trials = []
    trial_id = 1

    for block in blocks:
        for block_trial_num in range(1, trials_per_block + 1):
            stimulus = random.choice(stimuli)

            prior = random.choice(["A", "B"])

            is_probe = trial_id % probe_interval == 0

            delayed_reentry = False
            recurrence_source_trial = ""

            if trial_id > delayed_reentry_interval and block_trial_num % delayed_reentry_interval == 0:
                delayed_reentry = True
                source_trial = trials[-delayed_reentry_interval]
                stimulus = {
                    "stimulus_id": source_trial["stimulus_id"],
                    "cue": source_trial["cue"],
                    "ambiguous_text": source_trial["ambiguous_text"],
                    "interpretation_a": source_trial["interpretation_a"],
                    "interpretation_b": source_trial["interpretation_b"]
                }
                recurrence_source_trial = source_trial["trial_id"]

            if block == "affect":
                feedback_level = "neutral"
            elif block == "belief":
                feedback_level = "confirmatory"
            elif block == "contradiction":
                feedback_level = random.choice(
                    ["confirmatory", "mildly_contradictory", "strongly_contradictory"]
                )
            else:
                feedback_level = "neutral"

            trials.append({
                "trial_id": trial_id,
                "block": block,
                "block_trial_num": block_trial_num,
                "stimulus_id": stimulus["stimulus_id"],
                "cue": stimulus["cue"],
                "ambiguous_text": stimulus["ambiguous_text"],
                "interpretation_a": stimulus["interpretation_a"],
                "interpretation_b": stimulus["interpretation_b"],
                "prior_instruction": prior,
                "feedback_level": feedback_level,
                "probe_trial": is_probe,
                "delayed_reentry": delayed_reentry,
                "recurrence_source_trial": recurrence_source_trial
            })

            trial_id += 1

    return trials


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


def run_experiment():
    config = load_config()
    stimuli = load_stimuli()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    trials = make_trials(config, stimuli)

    fieldnames = [
        "trial_id",
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
        "affect",
        "behavioral_choice",
        "behavioral_rt",
        "feedback_level",
        "correct_answer",
        "contradiction",
        "probe_trial",
        "content_probe",
        "delayed_reentry",
        "recurrence_source_trial"
    ]

    print("\nTFL Baseline Reference Implementation")
    print("-------------------------------------")
    print("You will see ambiguous stimuli with two possible interpretations.")
    print("A = Interpretation A")
    print("B = Interpretation B")
    print("Use A or B only for prediction and behavioral choice.")
    print("Affect rating must be 0–100.\n")

    with open(DATA_FILE, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()

        for trial in trials:
            print("\n" + "=" * 60)
            print(f"Trial {trial['trial_id']} / {len(trials)}")
            print(f"Block: {trial['block']}")
            print(f"Cue/context: {trial['cue']}")
            print(f"Prior instruction: Interpretation {trial['prior_instruction']} is more likely.")
            input("\nPress Enter to view the stimulus...")

            print("\nAmbiguous stimulus:")
            print(trial["ambiguous_text"])

            print("\nInterpretation A:")
            print(trial["interpretation_a"])

            print("\nInterpretation B:")
            print(trial["interpretation_b"])

            start = time.time()
            prediction = get_valid_choice("\nPredicted interpretation (A/B): ", ["A", "B"])
            prediction_rt = round(time.time() - start, 4)

            affect = get_affect_rating("Affect intensity for this prediction (0–100): ")

            start = time.time()
            behavioral_choice = get_valid_choice("Final behavioral choice (A/B): ", ["A", "B"])
            behavioral_rt = round(time.time() - start, 4)

            correct_answer, contradiction = determine_feedback(
                prediction,
                trial["feedback_level"]
            )

            show_feedback(trial["feedback_level"], prediction, correct_answer)

            content_probe = ""

            if trial["probe_trial"] or trial["delayed_reentry"]:
                print("\nProbe:")
                content_probe = get_valid_choice(
                    "Which interpretation is most active in your mind right now? (A/B/U for uncodable): ",
                    ["A", "B", "U"]
                )

            writer.writerow({
                "trial_id": trial["trial_id"],
                "block": trial["block"],
                "block_trial_num": trial["block_trial_num"],
                "stimulus_id": trial["stimulus_id"],
                "cue": trial["cue"],
                "ambiguous_text": trial["ambiguous_text"],
                "interpretation_a": trial["interpretation_a"],
                "interpretation_b": trial["interpretation_b"],
                "prior_instruction": trial["prior_instruction"],
                "prediction": prediction,
                "prediction_rt": prediction_rt,
                "affect": affect,
                "behavioral_choice": behavioral_choice,
                "behavioral_rt": behavioral_rt,
                "feedback_level": trial["feedback_level"],
                "correct_answer": correct_answer,
                "contradiction": contradiction,
                "probe_trial": trial["probe_trial"],
                "content_probe": content_probe,
                "delayed_reentry": trial["delayed_reentry"],
                "recurrence_source_trial": trial["recurrence_source_trial"]
            })

    print(f"\nExperiment complete. Data saved to: {DATA_FILE}")

if __name__ == "__main__":
    run_experiment()
