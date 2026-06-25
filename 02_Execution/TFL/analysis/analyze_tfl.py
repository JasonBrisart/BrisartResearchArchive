import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
DATA_FILE = ROOT_DIR / "data" / "tfl_output.csv"


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")

    df = pd.read_csv(DATA_FILE)

    print("\nTFL Baseline Analysis v2.5")
    print("-------------------------")
    print("\nBasic trial count:")
    print(len(df))

    print("\nTrials by block:")
    print(df["block"].value_counts())

    print("\nPrediction counts:")
    print(df["prediction"].value_counts(dropna=False))

    print("\nBehavioral choice counts:")
    print(df["behavioral_choice"].value_counts(dropna=False))

    print("\nAffect summary:")
    print(df["affect"].describe())

    print("\nReaction time summary:")
    print(df[["prediction_rt", "behavioral_rt"]].describe())

    df["prediction_matches_prior"] = df["prediction"] == df["prior_instruction"]
    df["behavior_matches_prior"] = df["behavioral_choice"] == df["prior_instruction"]

    print("\nPrior-consistent prediction rate:")
    print(round(df["prediction_matches_prior"].mean(), 3))

    print("\nPrior-consistent behavioral choice rate:")
    print(round(df["behavior_matches_prior"].mean(), 3))

    contradiction_df = df[df["contradiction"].isin(["mild", "strong"])]
    print("\nContradiction trials:")
    print(len(contradiction_df))
    if len(contradiction_df) > 0:
        print("\nAffect by contradiction level:")
        print(contradiction_df.groupby("contradiction")["affect"].describe())

    probe_df = df[df["content_probe"].notna() & (df["content_probe"] != "")]
    print("\nProbe trials with codable content:")
    codable_probe_df = probe_df[probe_df["content_probe"].isin(["A", "B"])]
    print(len(codable_probe_df))
    if len(codable_probe_df) > 1:
        codable_probe_df = codable_probe_df.copy()
        codable_probe_df["previous_probe"] = codable_probe_df["content_probe"].shift(1)
        codable_probe_df["recurrence"] = (
            codable_probe_df["content_probe"] == codable_probe_df["previous_probe"]
        )
        recurrence_rate = codable_probe_df["recurrence"].mean()
        print("\nSimple content recurrence rate across probes:")
        print(round(recurrence_rate, 3))

    delayed_df = df[df["delayed_reentry"] == True]
    print("\nDelayed reentry trial count:")
    print(len(delayed_df))
    if len(delayed_df) > 0:
        print("\nDelayed reentry behavioral choices:")
        print(delayed_df["behavioral_choice"].value_counts(dropna=False))

    if "perturbation_trial" in df.columns:
        pert_df = df[df["perturbation_trial"].fillna(False).astype(bool)].copy()
        print("\nPerturbation trial count:")
        print(len(pert_df))
        if len(pert_df) > 0:
            print("\nPerturbation types:")
            print(pert_df["perturbation_type"].value_counts(dropna=False))

            codable_pert_df = pert_df[pert_df["post_perturbation_probe"].isin(["A", "B"])].copy()
            print("\nPerturbation trials with codable immediate probe:")
            print(len(codable_pert_df))
            if len(codable_pert_df) > 0:
                codable_pert_df["probe_changed_from_prediction"] = (
                    codable_pert_df["post_perturbation_probe"] != codable_pert_df["prediction"]
                )
                print("\nPost-perturbation interpretation switch rate:")
                print(round(codable_pert_df["probe_changed_from_prediction"].mean(), 3))

                codable_pert_df["behavior_changed_from_prediction"] = (
                    codable_pert_df["behavioral_choice"] != codable_pert_df["prediction"]
                )
                print("\nBehavioral switch rate on perturbation trials:")
                print(round(codable_pert_df["behavior_changed_from_prediction"].mean(), 3))

                print("\nSwitch rate by perturbation type:")
                print(
                    codable_pert_df.groupby("perturbation_type")["probe_changed_from_prediction"]
                    .mean()
                    .round(3)
                )

                codable_pert_df["stable_after_perturbation"] = (
                    codable_pert_df["post_perturbation_probe"] == codable_pert_df["prediction"]
                )
                print("\nMean affect by post-perturbation stability:")
                print(codable_pert_df.groupby("stable_after_perturbation")["affect"].mean().round(2))

    completed_trials = df[
        df["prediction"].isin(["A", "B"]) &
        df["behavioral_choice"].isin(["A", "B"]) &
        df["affect"].notna()
    ]
    print("\nCompleted usable trials:")
    print(len(completed_trials))
    if len(completed_trials) >= 96:
        print("\nBaseline completion gate: PASS")
    else:
        print("\nBaseline completion gate: FAIL")


if __name__ == "__main__":
    main()