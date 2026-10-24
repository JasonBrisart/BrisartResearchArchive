"""
File: frameworks/TFL/feedback.py

Purpose
-------
Map a prediction and feedback level to (correct_answer, contradiction),
produce the participant-facing feedback sentence, and provide the
perturbation instructions, all with 02_Execution reference wording.

Communication / relationships
-----------------------------
- frameworks/TFL/engine.py calls determine_feedback() and feedback_text().
- frameworks/TFL/screen.py and cli_runner.py display the text the engine
  stores; they never compose feedback themselves.

Settings / parameters
---------------------
- Levels: neutral, confirmatory, mildly_contradictory,
  strongly_contradictory.
- Perturbation types: head_turn, posture_shift, scene_shift, breath_reset.

Edge cases
----------
- determine_feedback() keeps reference semantics for every input:
  neutral and unknown levels return ("", "none").
- feedback_text() returns "" for an unknown level, as the reference
  prints nothing in that case.
- A blank prediction can only occur when the optional timer expires;
  feedback_text() then reports that no prediction was recorded instead
  of printing an empty interpretation letter.

Known limitations
-----------------
- The timeout wording is an Archive addition; it never appears in a
  default (untimed) run.

Examples
--------
- determine_feedback("A", "strongly_contradictory") returns ("B", "strong")
- make_perturbation_instruction("breath_reset")
"""
from __future__ import annotations

PERTURBATION_INSTRUCTIONS = {
    "head_turn": "Turn your head slowly to one side, then return to center.",
    "posture_shift": "Change your sitting posture noticeably, then settle into the new posture.",
    "scene_shift": "Look away from the screen toward a different area of the room for 3 seconds, then return.",
    "breath_reset": "Take one slow breath in and out before continuing.",
}
DEFAULT_PERTURBATION_INSTRUCTION = "Change posture or gaze briefly, then continue."


def opposite_choice(choice: str) -> str:
    if choice == "A":
        return "B"
    if choice == "B":
        return "A"
    return ""


def determine_feedback(prediction: str, feedback_level: str) -> tuple[str, str]:
    if feedback_level == "confirmatory":
        return prediction, "none"
    if feedback_level == "mildly_contradictory":
        return opposite_choice(prediction), "mild"
    if feedback_level == "strongly_contradictory":
        return opposite_choice(prediction), "strong"
    return "", "none"


def feedback_text(feedback_level: str, prediction: str, correct_answer: str) -> str:
    if feedback_level == "neutral":
        return "Feedback: No outcome feedback on this trial."
    if feedback_level not in {"confirmatory", "mildly_contradictory", "strongly_contradictory"}:
        return ""
    if prediction not in {"A", "B"}:
        return "Feedback: No prediction was recorded before the time limit."
    if feedback_level == "confirmatory":
        return f"Feedback: Confirmed. Interpretation {prediction} was supported."
    if feedback_level == "mildly_contradictory":
        return (
            f"Feedback: Mild contradiction. Your prediction was {prediction}, "
            f"but Interpretation {correct_answer} is somewhat better supported."
        )
    return (
        f"Feedback: Strong contradiction. Your prediction was {prediction}, "
        f"but Interpretation {correct_answer} is strongly supported."
    )


def make_perturbation_instruction(perturbation_type: str) -> str:
    return PERTURBATION_INSTRUCTIONS.get(perturbation_type, DEFAULT_PERTURBATION_INSTRUCTION)
