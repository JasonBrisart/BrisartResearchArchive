import csv
import time


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


def print_experiment_intro(framework, config, stimuli):
    print("\n" + "-" * 80)
    print(framework.VERSION_LABEL)
    print("-" * 80)

    print(framework.SESSION_INTRO_TEXT)

    print("\nCurrent run configuration:")
    print("-" * 80)
    print(f"Framework: {framework.FRAMEWORK_NAME}")
    print(f"Run Mode: {config.get('run_mode', 'base')}")
    print(f"Stimuli Available: {len(stimuli)}")
    print(f"Extra Stimuli: {'ON' if config.get('enable_extra_stimuli', False) else 'OFF'}")
    print(f"Perturbations: {'ON' if config.get('enable_perturbations', False) else 'OFF'}")
    print(f"Probes: {'ON' if config.get('enable_probes', True) else 'OFF'}")
    print(f"Delayed Reentry: {'ON' if config.get('enable_delayed_reentry', True) else 'OFF'}")
    print(f"Blocks: {', '.join(config['blocks'])}")
    print(f"Trials Per Block: {config['trials_per_block']}")
    print(f"Total Trials: {config['trials_per_block'] * len(config['blocks'])}")
    print("-" * 80)

    if config.get("enable_perturbations", False):
        print("Some trials include a brief perturbation step.")
    else:
        print("No perturbation trials will be presented in this run.")

    print()


def run_session(framework, config, stimuli, trials):
    framework.DATA_DIR.mkdir(parents=True, exist_ok=True)

    print_experiment_intro(framework, config, stimuli)

    with open(framework.OUTPUT_FILE, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=framework.CSV_FIELDNAMES)
        writer.writeheader()

        for trial in trials:
            row = run_single_trial(framework, trial, len(trials))
            writer.writerow(row)
            out.flush()

    print(f"\nExperiment complete. Data saved to: {framework.OUTPUT_FILE}")


def run_single_trial(framework, trial, total_trials):
    print("\n" + "=" * 60)
    print(f"Trial {trial['trial_id']} / {total_trials}")
    print(f"Framework: {trial['framework_id']}")
    print(f"Mode: {trial['run_mode']}")
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

    prediction, prediction_rt = collect_prediction(framework)
    affect = get_affect_rating("Affect intensity for this prediction (0–100): ")

    post_perturbation_probe, perturbation_match_prediction = handle_perturbation(
        framework,
        trial,
        prediction,
    )

    behavioral_choice, behavioral_rt = collect_behavioral_choice()

    correct_answer, contradiction = framework.determine_feedback(
        prediction,
        trial["feedback_level"],
    )

    framework.show_feedback(trial["feedback_level"], prediction, correct_answer)

    content_probe = collect_content_probe_if_needed(trial)

    return build_output_row(
        trial=trial,
        prediction=prediction,
        prediction_rt=prediction_rt,
        affect=affect,
        behavioral_choice=behavioral_choice,
        behavioral_rt=behavioral_rt,
        correct_answer=correct_answer,
        contradiction=contradiction,
        content_probe=content_probe,
        post_perturbation_probe=post_perturbation_probe,
        perturbation_match_prediction=perturbation_match_prediction,
    )


def collect_prediction(framework):
    start = time.time()
    prediction = get_valid_choice(framework.PREDICTION_PROMPT, framework.PREDICTION_CHOICES)
    prediction_rt = round(time.time() - start, 4)

    return prediction, prediction_rt


def collect_behavioral_choice():
    start = time.time()
    behavioral_choice = get_valid_choice("Final behavioral choice (A/B): ", ["A", "B"])
    behavioral_rt = round(time.time() - start, 4)

    return behavioral_choice, behavioral_rt


def handle_perturbation(framework, trial, prediction):
    post_perturbation_probe = ""
    perturbation_match_prediction = ""

    if not trial["perturbation_trial"]:
        return post_perturbation_probe, perturbation_match_prediction

    print("\nPerturbation step:")
    print(framework.make_perturbation_instruction(trial["perturbation_type"]))
    input("Press Enter once completed...")

    post_perturbation_probe = get_valid_choice(
        "Which interpretation is most active immediately after the perturbation? (A/B/U): ",
        ["A", "B", "U"],
    )

    if post_perturbation_probe in ["A", "B"] and prediction in ["A", "B"]:
        perturbation_match_prediction = post_perturbation_probe == prediction

    return post_perturbation_probe, perturbation_match_prediction


def collect_content_probe_if_needed(trial):
    if not trial["probe_trial"] and not trial["delayed_reentry"]:
        return ""

    print("\nProbe:")

    return get_valid_choice(
        "Which interpretation is most active in your mind right now? (A/B/U for uncodable): ",
        ["A", "B", "U"],
    )


def build_output_row(
    trial,
    prediction,
    prediction_rt,
    affect,
    behavioral_choice,
    behavioral_rt,
    correct_answer,
    contradiction,
    content_probe,
    post_perturbation_probe,
    perturbation_match_prediction,
):
    return {
        "trial_id": trial["trial_id"],
        "framework_id": trial["framework_id"],
        "run_mode": trial["run_mode"],
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
        "recurrence_source_trial": trial["recurrence_source_trial"],
        "perturbation_trial": trial["perturbation_trial"],
        "perturbation_type": trial["perturbation_type"],
        "post_perturbation_probe": post_perturbation_probe,
        "perturbation_match_prediction": perturbation_match_prediction,
    }