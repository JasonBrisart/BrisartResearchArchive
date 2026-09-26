"""
File: frameworks/TFL/feedback.py

Purpose:
Map a trial's prediction and feedback level to (correct_answer,
contradiction), and provide display helpers for console feedback and
perturbation instructions. No file I/O and no state.

Communication / relationships:
- frameworks/TFL/engine.py calls determine_feedback() for every row.
- frameworks/TFL/screen.py calls make_perturbation_instruction().
- frameworks/TFL/analysis.py buckets trials by the recorded
  contradiction value.
- frameworks/TFL/framework.py exposes lazy wrappers.

Settings / parameters:
- Feedback levels: neutral, confirmatory, mildly_contradictory,
  strongly_contradictory.
- Perturbation types with instructions: head_turn, posture_shift,
  scene_shift, breath_reset.

Edge cases:
- A blank or timed-out prediction returns ("", "").
- "neutral" returns ("", "none"); an empty level returns ("", "").
- An unknown level returns (prediction, "none").
- An unknown perturbation type returns a generic instruction.

Known limitations:
- show_feedback() prints to the console only and is not used by the GUI.
- Instruction text lives here rather than in frameworks/TFL/settings.py.

Examples:
- determine_feedback("A", "strongly_contradictory") returns ("B", "strong")
- make_perturbation_instruction("breath_reset")
"""
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
