from __future__ import annotations

from . import framework

# ============================================================
# Stimulus Schema
# ============================================================

REQUIRED_STIMULUS_FIELDS = (
    "stimulus_id",
    "cue",
    "ambiguous_text",
    "interpretation_a",
    "interpretation_b",
)

# ============================================================
# Embedded TFL Stimulus Library
# ============================================================

EMBEDDED_STIMULI = [
    {"stimulus_id": "S001", "cue": "context_person",
     "ambiguous_text": "Jordan saw Alex with the binoculars.",
     "interpretation_a": "Jordan used the binoculars.",
     "interpretation_b": "Alex had the binoculars."},
    {"stimulus_id": "S002", "cue": "context_message",
     "ambiguous_text": "Taylor said Morgan's reply was cold.",
     "interpretation_a": "Morgan's reply was emotionally distant.",
     "interpretation_b": "Morgan's reply referred to low temperature."},
    {"stimulus_id": "S003", "cue": "context_room",
     "ambiguous_text": "Casey noticed the light by the door.",
     "interpretation_a": "The light fixture was near the door.",
     "interpretation_b": "Casey noticed illumination coming from near the door."},
    {"stimulus_id": "S004", "cue": "context_action",
     "ambiguous_text": "Riley watched Sam duck under the table.",
     "interpretation_a": "Sam moved under the table.",
     "interpretation_b": "Sam avoided something while near the table."},
    {"stimulus_id": "S005", "cue": "context_sound",
     "ambiguous_text": "Avery heard the bat near the window.",
     "interpretation_a": "A flying animal was near the window.",
     "interpretation_b": "A sports bat was near the window."},
    {"stimulus_id": "S006", "cue": "context_social",
     "ambiguous_text": "Jamie thought Pat's smile changed the room.",
     "interpretation_a": "Pat's smile affected the social atmosphere.",
     "interpretation_b": "The room physically changed because of lighting or arrangement."},
    {"stimulus_id": "S007", "cue": "context_object",
     "ambiguous_text": "Drew found the glasses on the desk.",
     "interpretation_a": "Drew found eyewear.",
     "interpretation_b": "Drew found drinking glasses."},
    {"stimulus_id": "S008", "cue": "context_event",
     "ambiguous_text": "Quinn said the meeting turned sharp.",
     "interpretation_a": "The meeting became tense.",
     "interpretation_b": "The meeting became more precise or focused."},
    {"stimulus_id": "S009", "cue": "context_memory",
     "ambiguous_text": "Rowan remembered the bank clearly.",
     "interpretation_a": "Rowan remembered a financial bank.",
     "interpretation_b": "Rowan remembered a river bank."},
    {"stimulus_id": "S010", "cue": "context_signal",
     "ambiguous_text": "Skyler saw the signal fade.",
     "interpretation_a": "A communication signal weakened.",
     "interpretation_b": "A gesture or cue became less noticeable."},
    {"stimulus_id": "S011", "cue": "context_person",
     "ambiguous_text": "Morgan passed Taylor on the stairs with a smile.",
     "interpretation_a": "Morgan was smiling.",
     "interpretation_b": "Taylor was smiling."},
    {"stimulus_id": "S012", "cue": "context_event",
     "ambiguous_text": "Jordan told Alex the meeting was canceled late.",
     "interpretation_a": "The cancellation happened late.",
     "interpretation_b": "Jordan informed Alex late."},
    {"stimulus_id": "S013", "cue": "context_object",
     "ambiguous_text": "Riley placed the book on the table near the lamp.",
     "interpretation_a": "The lamp is near the table.",
     "interpretation_b": "The table is near the lamp."},
    {"stimulus_id": "S014", "cue": "context_social",
     "ambiguous_text": "Casey said Drew's joke was awkward at dinner.",
     "interpretation_a": "The joke felt socially uncomfortable.",
     "interpretation_b": "The joke was delivered poorly."},
    {"stimulus_id": "S015", "cue": "context_action",
     "ambiguous_text": "Sam helped Lee while carrying the boxes.",
     "interpretation_a": "Sam was carrying boxes.",
     "interpretation_b": "Lee was carrying boxes."},
    {"stimulus_id": "S016", "cue": "context_room",
     "ambiguous_text": "Taylor saw the chair by the window move.",
     "interpretation_a": "The chair moved.",
     "interpretation_b": "The lighting shifted making it seem like movement."},
    {"stimulus_id": "S017", "cue": "context_sound",
     "ambiguous_text": "Jamie heard the bell from the school.",
     "interpretation_a": "The bell originated at the school.",
     "interpretation_b": "Jamie was near the school when hearing it."},
    {"stimulus_id": "S018", "cue": "context_object",
     "ambiguous_text": "Avery picked up the glasses on the counter.",
     "interpretation_a": "Eyewear was picked up.",
     "interpretation_b": "Drinkware was picked up."},
    {"stimulus_id": "S019", "cue": "context_interaction",
     "ambiguous_text": "Quinn told Blake they needed to hurry.",
     "interpretation_a": "Quinn needed to hurry.",
     "interpretation_b": "Blake needed to hurry."},
    {"stimulus_id": "S020", "cue": "context_memory",
     "ambiguous_text": "Jordan remembered the note clearly.",
     "interpretation_a": "A written message was recalled.",
     "interpretation_b": "A musical tone was recalled."},
    {"stimulus_id": "S021", "cue": "context_person",
     "ambiguous_text": "Casey watched Riley leave with the package.",
     "interpretation_a": "Riley left carrying the package.",
     "interpretation_b": "Casey left with the package."},
    {"stimulus_id": "S022", "cue": "context_event",
     "ambiguous_text": "Taylor said the results surprised Morgan yesterday.",
     "interpretation_a": "The results were surprising yesterday.",
     "interpretation_b": "Taylor spoke yesterday."},
    {"stimulus_id": "S023", "cue": "context_environment",
     "ambiguous_text": "Drew noticed the light above the door flicker.",
     "interpretation_a": "The light above the door flickered.",
     "interpretation_b": "The doorway area seemed to flicker."},
    {"stimulus_id": "S024", "cue": "context_social",
     "ambiguous_text": "Sam thought Alex's comment shifted the mood.",
     "interpretation_a": "The comment changed the social atmosphere.",
     "interpretation_b": "The comment physically altered the setting."},
    {"stimulus_id": "S025", "cue": "context_object",
     "ambiguous_text": "Lee found the key under the paper.",
     "interpretation_a": "A physical key was found.",
     "interpretation_b": "A clue or answer was found."},
    {"stimulus_id": "S026", "cue": "context_action",
     "ambiguous_text": "Morgan followed Jordan through the hall quietly.",
     "interpretation_a": "Morgan was quiet.",
     "interpretation_b": "Jordan was quiet."},
    {"stimulus_id": "S027", "cue": "context_interaction",
     "ambiguous_text": "Casey told Taylor they were wrong.",
     "interpretation_a": "Casey told Taylor they were wrong.",
     "interpretation_b": "Casey said that Casey was wrong."},
    {"stimulus_id": "S028", "cue": "context_event",
     "ambiguous_text": "Riley mentioned the project was finished early.",
     "interpretation_a": "The project ended early.",
     "interpretation_b": "Riley spoke early."},
    {"stimulus_id": "S029", "cue": "context_sound",
     "ambiguous_text": "Blake heard a bat in the room.",
     "interpretation_a": "An animal was present.",
     "interpretation_b": "A sports object was present."},
    {"stimulus_id": "S030", "cue": "context_object",
     "ambiguous_text": "Avery opened the file on the computer.",
     "interpretation_a": "A digital document was opened.",
     "interpretation_b": "A physical folder was opened."},
    {"stimulus_id": "S031", "cue": "context_person",
     "ambiguous_text": "Jordan saw Casey with the camera.",
     "interpretation_a": "Jordan used the camera.",
     "interpretation_b": "Casey had the camera."},
    {"stimulus_id": "S032", "cue": "context_social",
     "ambiguous_text": "Lee said Sam's expression changed the situation.",
     "interpretation_a": "The expression influenced the mood.",
     "interpretation_b": "The situation physically changed."},
    {"stimulus_id": "S033", "cue": "context_event",
     "ambiguous_text": "Taylor mentioned the game was intense at the end.",
     "interpretation_a": "The ending was intense.",
     "interpretation_b": "The mention happened at the end."},
    {"stimulus_id": "S034", "cue": "context_room",
     "ambiguous_text": "Riley noticed the clock by the wall tilt.",
     "interpretation_a": "The clock tilted.",
     "interpretation_b": "The perspective made it appear tilted."},
    {"stimulus_id": "S035", "cue": "context_object",
     "ambiguous_text": "Drew held the glasses near the sink.",
     "interpretation_a": "Eyewear was near the sink.",
     "interpretation_b": "Drinking glasses were near the sink."},
    {"stimulus_id": "S036", "cue": "context_action",
     "ambiguous_text": "Alex guided Morgan through the door with care.",
     "interpretation_a": "Alex was careful.",
     "interpretation_b": "Morgan was careful."},
    {"stimulus_id": "S037", "cue": "context_interaction",
     "ambiguous_text": "Casey told Blake their answer was correct.",
     "interpretation_a": "Blake's answer was correct.",
     "interpretation_b": "Casey's answer was correct."},
    {"stimulus_id": "S038", "cue": "context_event",
     "ambiguous_text": "Sam said the event ended fast yesterday.",
     "interpretation_a": "The event ended quickly.",
     "interpretation_b": "Sam spoke quickly yesterday."},
    {"stimulus_id": "S039", "cue": "context_sound",
     "ambiguous_text": "Taylor heard the whistle near the field.",
     "interpretation_a": "The whistle came from the field.",
     "interpretation_b": "Taylor was near the field hearing it."},
    {"stimulus_id": "S040", "cue": "context_memory",
     "ambiguous_text": "Jamie remembered the bank near the street.",
     "interpretation_a": "A financial institution was recalled.",
     "interpretation_b": "A riverbank was recalled."},
    {"stimulus_id": "S041", "cue": "context_person",
     "ambiguous_text": "Quinn noticed Riley with the binoculars.",
     "interpretation_a": "Quinn used the binoculars.",
     "interpretation_b": "Riley had the binoculars."},
    {"stimulus_id": "S042", "cue": "context_social",
     "ambiguous_text": "Jordan thought Taylor's tone shifted the room.",
     "interpretation_a": "The tone changed the mood.",
     "interpretation_b": "The room physically shifted."},
    {"stimulus_id": "S043", "cue": "context_object",
     "ambiguous_text": "Avery picked up the paper on the desk.",
     "interpretation_a": "A document was picked up.",
     "interpretation_b": "A physical sheet was picked up."},
    {"stimulus_id": "S044", "cue": "context_action",
     "ambiguous_text": "Blake followed Casey across the room quietly.",
     "interpretation_a": "Blake was quiet.",
     "interpretation_b": "Casey was quiet."},
    {"stimulus_id": "S045", "cue": "context_interaction",
     "ambiguous_text": "Morgan told Lee they arrived early.",
     "interpretation_a": "Morgan arrived early.",
     "interpretation_b": "Lee arrived early."},
    {"stimulus_id": "S046", "cue": "context_event",
     "ambiguous_text": "Sam mentioned the talk was long at the end.",
     "interpretation_a": "The end was long.",
     "interpretation_b": "Sam spoke at the end."},
    {"stimulus_id": "S047", "cue": "context_sound",
     "ambiguous_text": "Riley heard the ring from the phone.",
     "interpretation_a": "The phone emitted the ring.",
     "interpretation_b": "Riley was near the phone."},
    {"stimulus_id": "S048", "cue": "context_object",
     "ambiguous_text": "Jordan found the light in the box.",
     "interpretation_a": "A light source was found.",
     "interpretation_b": "Understanding was gained."},
    {"stimulus_id": "S049", "cue": "context_person",
     "ambiguous_text": "Taylor saw Alex with the bag.",
     "interpretation_a": "Taylor carried the bag.",
     "interpretation_b": "Alex had the bag."},
    {"stimulus_id": "S050", "cue": "context_social",
     "ambiguous_text": "Casey said Morgan's reaction changed everything.",
     "interpretation_a": "The reaction changed the situation.",
     "interpretation_b": "Everything physically changed."},
    {"stimulus_id": "S051", "cue": "context_action",
     "ambiguous_text": "Lee walked Sam through the process slowly.",
     "interpretation_a": "Lee was slow.",
     "interpretation_b": "Sam was slow."},
    {"stimulus_id": "S052", "cue": "context_event",
     "ambiguous_text": "Avery noted the meeting ended quickly.",
     "interpretation_a": "The meeting ended quickly.",
     "interpretation_b": "The note occurred quickly."},
    {"stimulus_id": "S053", "cue": "context_room",
     "ambiguous_text": "Blake noticed the shadow by the door move.",
     "interpretation_a": "The shadow moved.",
     "interpretation_b": "Lighting conditions changed."},
    {"stimulus_id": "S054", "cue": "context_object",
     "ambiguous_text": "Jordan grabbed the glasses near the table.",
     "interpretation_a": "Eyewear was taken.",
     "interpretation_b": "Drinkware was taken."},
    {"stimulus_id": "S055", "cue": "context_interaction",
     "ambiguous_text": "Riley told Quinn they solved it.",
     "interpretation_a": "Riley solved it.",
     "interpretation_b": "Quinn solved it."},
    {"stimulus_id": "S056", "cue": "context_sound",
     "ambiguous_text": "Sam heard the bark from outside.",
     "interpretation_a": "An animal barked.",
     "interpretation_b": "The sound resembled barking."},
    {"stimulus_id": "S057", "cue": "context_memory",
     "ambiguous_text": "Morgan recalled the pitch clearly.",
     "interpretation_a": "A musical tone was recalled.",
     "interpretation_b": "A business proposal was recalled."},
    {"stimulus_id": "S058", "cue": "context_person",
     "ambiguous_text": "Casey noticed Alex with the keys.",
     "interpretation_a": "Casey used the keys.",
     "interpretation_b": "Alex had the keys."},
    {"stimulus_id": "S059", "cue": "context_social",
     "ambiguous_text": "Taylor believed Jordan's comment shifted things.",
     "interpretation_a": "The comment changed perception.",
     "interpretation_b": "The situation literally changed."},
    {"stimulus_id": "S060", "cue": "context_event",
     "ambiguous_text": "Blake said the task became easier later.",
     "interpretation_a": "It became easier later.",
     "interpretation_b": "Blake commented later."},
]

# Backward-compatible name for code that imported FALLBACK_STIMULI.
FALLBACK_STIMULI = EMBEDDED_STIMULI


# ============================================================
# Stimulus Validation
# ============================================================

def normalize_stimulus_row(row: dict, row_number: int) -> dict:
    if not isinstance(row, dict):
        raise TypeError(f"Stimulus row {row_number} is not a dictionary.")
    normalized = {}
    for field in REQUIRED_STIMULUS_FIELDS:
        value = row.get(field, "")
        if value is None:
            value = ""
        normalized[field] = str(value).strip()
    missing = [field for field, value in normalized.items() if not value]
    if missing:
        raise ValueError(f"Stimulus row {row_number} is missing: " + ", ".join(sorted(missing)))
    return normalized


def validate_stimuli(rows: list[dict]) -> list[dict]:
    """
    Validate a TFL stimulus collection. Rejects non-list collections,
    empty collections, non-dictionary entries, missing required fields,
    blank values, and duplicate stimulus IDs. Returns newly created
    dictionaries so callers cannot mutate the embedded definitions.
    """
    if not isinstance(rows, list):
        raise TypeError("TFL stimuli must be provided as a list.")
    if not rows:
        raise ValueError("No TFL stimuli were provided.")
    validated = []
    seen_ids = set()
    for row_number, row in enumerate(rows, start=1):
        normalized = normalize_stimulus_row(row, row_number)
        stimulus_id = normalized["stimulus_id"]
        if stimulus_id in seen_ids:
            raise ValueError(f"Duplicate stimulus_id found: {stimulus_id}")
        seen_ids.add(stimulus_id)
        validated.append(normalized)
    return validated


# ============================================================
# Public Stimulus API
# ============================================================

def load_stimuli() -> list[dict]:
    """Return the embedded TFL stimulus library. No filesystem or network lookup required."""
    return validate_stimuli([dict(stimulus) for stimulus in EMBEDDED_STIMULI])


def apply_stimulus_limit(stimuli: list[dict], config: dict) -> list[dict]:
    """
    Apply the baseline stimulus limit unless extra stimuli are enabled.
    """
    validated = validate_stimuli(list(stimuli))
    if config.get("enable_extra_stimuli", False):
        return validated
    return validated[:framework.BASE_STIMULUS_LIMIT]
