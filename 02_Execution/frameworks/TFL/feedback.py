from __future__ import annotations


def opposite_choice(choice: str) -> str:
    if choice == "A":
        return "B"
    if choice == "B":
        return "A"
    return ""


def determine_feedback(prediction: str, feedback_level: str) -> tuple[str, str]:
    """
    Determine the feedback outcome for one TFL trial.

    Returns:
        correct_answer: the answer shown as correct for this trial.
        contradiction: one of "", "mild", "strong".
    """
    prediction = str(prediction).strip().upper()
    feedback_level = str(feedback_level).strip().lower()

    if prediction not in {"A", "B"}:
        return "", ""
    if feedback_level in {"", "neutral"}:
        return "", "none" if feedback_level == "neutral" else ""
    if feedback_level == "confirmatory":
        return prediction, "none"
    if feedback_level == "mildly_contradictory":
        return opposite_choice(prediction), "mild"
    if feedback_level == "strongly_contradictory":
        return opposite_choice(prediction), "strong"
    return prediction, "none"


def show_feedback(feedback_level: str, prediction: str, correct_answer: str) -> None:
    """Console feedback display, retained for headless/CLI runs."""
    feedback_level = str(feedback_level).strip().lower()
    print()
    print("Feedback")
    print("-" * 40)
    if feedback_level == "confirmatory":
        print(f"Your interpretation was supported: {correct_answer}")
    elif feedback_level == "mildly_contradictory":
        print(f"A mildly contradictory interpretation was presented: {correct_answer}")
    elif feedback_level == "strongly_contradictory":
        print(f"A strongly contradictory interpretation was presented: {correct_answer}")
    else:
        print(f"Recorded interpretation: {prediction}")
    print("-" * 40)


def make_perturbation_instruction(perturbation_type: str) -> str:
    """Return a short perturbation instruction for console and GUI use."""
    perturbation_type = str(perturbation_type).strip().lower()
    instructions = {
        "head_turn": (
            "Briefly turn your head left, then right, then return to center. "
            "Afterward, report which interpretation feels most active."
        ),
        "posture_shift": (
            "Briefly shift your posture, then settle again. "
            "Afterward, report which interpretation feels most active."
        ),
        "scene_shift": (
            "Look away from the screen briefly, then return to the stimulus. "
            "Afterward, report which interpretation feels most active."
        ),
        "breath_reset": (
            "Take one slow breath, then return attention to the stimulus. "
            "Afterward, report which interpretation feels most active."
        ),
    }
    return instructions.get(
        perturbation_type,
        "Perform the brief perturbation step, then report which interpretation feels most active.",
    )
