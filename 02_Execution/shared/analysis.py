from pathlib import Path

import pandas as pd


def safe_bool_series(series):
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])


def print_section(title):
    print("\n" + title)
    print("-" * len(title))


def load_output(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {path}")

    return pd.read_csv(path)


def run_basic_analysis(framework):
    df = load_output(framework.OUTPUT_FILE)

    print(f"\n{framework.FRAMEWORK_ID} Analysis")
    print("-" * 40)

    report_metadata(df)
    report_trial_counts(df)
    report_prediction_behavior(df)
    report_affect_rt(df)
    report_prior_consistency(df)
    report_contradiction(df)
    report_probes(df)
    report_delayed_reentry(df)
    report_perturbations(df)
    report_completion_gate(df)


def report_metadata(df):
    print_section("Run Metadata")

    if "framework_id" in df.columns:
        print("Framework counts:")
        print(df["framework_id"].value_counts(dropna=False))

    if "run_mode" in df.columns:
        print("\nRun mode counts:")
        print(df["run_mode"].value_counts(dropna=False))


def report_trial_counts(df):
    print_section("Trial Counts")

    print("Total trials:")
    print(len(df))

    if "block" in df.columns:
        print("\nTrials by block:")
        print(df["block"].value_counts(dropna=False))

    if "stimulus_id" in df.columns:
        print("\nUnique stimuli used:")
        print(df["stimulus_id"].nunique())


def report_prediction_behavior(df):
    print_section("Prediction and Behavior")

    print("Prediction counts:")
    print(df["prediction"].value_counts(dropna=False))

    print("\nBehavioral choice counts:")
    print(df["behavioral_choice"].value_counts(dropna=False))


def report_affect_rt(df):
    print_section("Affect and Reaction Time")

    if "affect" in df.columns:
        print("Affect summary:")
        print(df["affect"].describe())

    rt_columns = [
        column for column in ["prediction_rt", "behavioral_rt"]
        if column in df.columns
    ]

    if rt_columns:
        print("\nReaction time summary:")
        print(df[rt_columns].describe())


def report_prior_consistency(df):
    print_section("Prior Consistency")

    ab_prediction_df = df[df["prediction"].isin(["A", "B"])].copy()

    if len(ab_prediction_df) > 0:
        ab_prediction_df["prediction_matches_prior"] = (
            ab_prediction_df["prediction"] == ab_prediction_df["prior_instruction"]
        )

        print("Prior-consistent prediction rate:")
        print(round(ab_prediction_df["prediction_matches_prior"].mean(), 3))
    else:
        print("No A/B predictions available.")

    behavior_df = df[df["behavioral_choice"].isin(["A", "B"])].copy()

    if len(behavior_df) > 0:
        behavior_df["behavior_matches_prior"] = (
            behavior_df["behavioral_choice"] == behavior_df["prior_instruction"]
        )

        print("\nPrior-consistent behavioral choice rate:")
        print(round(behavior_df["behavior_matches_prior"].mean(), 3))


def report_contradiction(df):
    print_section("Contradiction")

    if "contradiction" not in df.columns:
        print("No contradiction column found.")
        return

    contradiction_df = df[df["contradiction"].isin(["mild", "strong"])]

    print("Contradiction trial count:")
    print(len(contradiction_df))

    if len(contradiction_df) > 0:
        print("\nContradiction counts:")
        print(contradiction_df["contradiction"].value_counts(dropna=False))

        print("\nAffect by contradiction level:")
        print(contradiction_df.groupby("contradiction")["affect"].describe())


def report_probes(df):
    print_section("Probes")

    if "content_probe" not in df.columns:
        print("No content_probe column found.")
        return

    probe_df = df[df["content_probe"].notna() & (df["content_probe"] != "")]
    codable_probe_df = probe_df[probe_df["content_probe"].isin(["A", "B"])].copy()

    print("Probe responses:")
    print(len(probe_df))

    print("\nCodable probe responses:")
    print(len(codable_probe_df))

    if len(codable_probe_df) > 1:
        codable_probe_df["previous_probe"] = codable_probe_df["content_probe"].shift(1)
        codable_probe_df["recurrence"] = (
            codable_probe_df["content_probe"] == codable_probe_df["previous_probe"]
        )

        print("\nSimple recurrence rate across probes:")
        print(round(codable_probe_df["recurrence"].mean(), 3))


def report_delayed_reentry(df):
    print_section("Delayed Reentry")

    if "delayed_reentry" not in df.columns:
        print("No delayed_reentry column found.")
        return

    delayed_df = df[safe_bool_series(df["delayed_reentry"])]

    print("Delayed reentry trial count:")
    print(len(delayed_df))

    if len(delayed_df) > 0:
        print("\nDelayed reentry predictions:")
        print(delayed_df["prediction"].value_counts(dropna=False))

        print("\nDelayed reentry behavioral choices:")
        print(delayed_df["behavioral_choice"].value_counts(dropna=False))


def report_perturbations(df):
    print_section("Perturbations")

    if "perturbation_trial" not in df.columns:
        print("No perturbation_trial column found.")
        return

    pert_df = df[safe_bool_series(df["perturbation_trial"])]

    print("Perturbation trial count:")
    print(len(pert_df))

    if len(pert_df) == 0:
        print("No perturbation trials in this run.")
        return

    print("\nPerturbation types:")
    print(pert_df["perturbation_type"].value_counts(dropna=False))


def report_completion_gate(df):
    print_section("Completion Gate")

    completed_trials = df[
        df["prediction"].isin(["A", "B"])
        & df["behavioral_choice"].isin(["A", "B"])
        & df["affect"].notna()
    ]

    expected_minimum = int(len(df) * 0.8)

    print("Completed usable trials:")
    print(len(completed_trials))

    print("\nRecommended minimum usable trials:")
    print(expected_minimum)

    if len(completed_trials) >= expected_minimum:
        print(f"\nPASS — {len(completed_trials)} / {len(df)} usable trials")
    else:
        print(f"\nFAIL — {len(completed_trials)} / {len(df)} usable trials")