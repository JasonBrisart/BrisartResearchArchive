"""
Temporal Feedback Loop analysis.
Pure standard library: CSV in, CSV out, text report out. No third-party
dependencies. Understands the fuller schema (prediction_timed_out,
behavioral_timed_out, completion_status) produced by the engine.
"""
from __future__ import annotations

import csv
import math
import os
import shutil
from datetime import datetime
from math import ceil
from pathlib import Path
from statistics import mean

from config.runtime import get_framework_output_dir
from . import framework

# ============================================================
# Paths
# ============================================================


def get_output_dir() -> Path:
    return get_framework_output_dir(framework.FRAMEWORK_ID)


def timestamp_string() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def get_timestamped_output_file() -> Path:
    return get_output_dir() / f"tfl_output_{timestamp_string()}.csv"


def get_latest_output_file() -> Path:
    return get_output_dir() / "tfl_output_latest.csv"


def get_default_output_file() -> Path:
    return get_latest_output_file()


def sanitize_session_id(session_id: str) -> str:
    session_id = str(session_id or "").strip()
    safe = "".join(character if (character.isalnum() or character in {"-", "_"}) else "_" for character in session_id)
    return safe.strip("._") or "UNKNOWN_SESSION"


def get_autosave_file(session_id: str) -> Path:
    """
    One fixed, overwritten-in-place file per session - not a growing pile
    of timestamped snapshots. This exists so an in-progress run survives
    a crash or a forced window close: previously, save_rows() was only
    ever called once, at session completion, so any interruption lost
    every trial collected up to that point.
    """
    return get_output_dir() / "autosave" / f"tfl_autosave_{sanitize_session_id(session_id)}.csv"


def autosave_rows(rows: list[dict], session_id: str) -> Path:
    """Best-effort incremental checkpoint. Raises on failure; callers should catch."""
    return write_rows(rows, get_autosave_file(session_id))


def remove_autosave_file(session_id: str) -> None:
    """Clean up the autosave checkpoint once a full, final save has succeeded."""
    path = get_autosave_file(session_id)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


# ============================================================
# Validation
# ============================================================


def valid_affect_value(value) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric) and 0 <= numeric <= 100


def validate_affect(value, row_number: int) -> None:
    if not valid_affect_value(value):
        raise ValueError(f"TFL row {row_number} has an affect value outside 0-100.")


def validate_rows(rows: list[dict]) -> None:
    if not isinstance(rows, list):
        raise TypeError("TFL rows must be provided as a list.")
    if not rows:
        raise ValueError("TFL rows cannot be empty.")
    allowed_fields = set(framework.CSV_FIELDNAMES)
    required_fields = {
        "trial_id", "framework_id", "block", "stimulus_id",
        "prediction", "behavioral_choice", "affect", "completion_status",
    }
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise TypeError(f"TFL row {index} is not a dictionary.")
        unexpected = set(row) - allowed_fields
        if unexpected:
            raise ValueError(f"TFL row {index} contains unsupported fields: " + ", ".join(sorted(unexpected)))
        missing = required_fields - set(row)
        if missing:
            raise ValueError(f"TFL row {index} is missing required fields: " + ", ".join(sorted(missing)))
        if row.get("framework_id") != framework.FRAMEWORK_ID:
            raise ValueError(f"TFL row {index} has an invalid framework_id.")
        if row.get("prediction") not in {"A", "B", ""}:
            raise ValueError(f"TFL row {index} has an invalid prediction.")
        if row.get("behavioral_choice") not in {"A", "B", ""}:
            raise ValueError(f"TFL row {index} has an invalid behavioral_choice.")
        validate_affect(row.get("affect"), index)


# ============================================================
# CSV storage
# ============================================================


def write_rows(rows: list[dict], path: Path) -> Path:
    validate_rows(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(path.name + ".tmp")
    try:
        with open(temporary_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=framework.CSV_FIELDNAMES, extrasaction="raise")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in framework.CSV_FIELDNAMES})
            file.flush()
            try:
                os.fsync(file.fileno())
            except OSError:
                pass
        temporary_path.replace(path)
    except Exception:
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass
        raise
    return path


def save_rows(rows: list[dict], path: Path | None = None) -> Path:
    """
    Save TFL rows. Default: write a unique timestamped CSV, then
    atomically refresh tfl_output_latest.csv. Explicit path: write only
    the provided path.
    """
    validate_rows(rows)
    if path is not None:
        return write_rows(rows, Path(path))
    timestamped_file = get_timestamped_output_file()
    latest_file = get_latest_output_file()
    latest_temp_file = latest_file.with_name(latest_file.name + ".tmp")
    write_rows(rows, timestamped_file)
    latest_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(timestamped_file, latest_temp_file)
        latest_temp_file.replace(latest_file)
    except Exception:
        try:
            if latest_temp_file.exists():
                latest_temp_file.unlink()
        except OSError:
            pass
        raise
    return timestamped_file


def load_output(path: Path | None = None) -> list[dict]:
    path = Path(path or get_default_output_file())
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Output file is empty: {path}")
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if not fieldnames:
        raise ValueError(f"Output CSV has no header: {path}")
    required_columns = {"prediction", "behavioral_choice", "affect", "completion_status"}
    missing = required_columns - set(fieldnames)
    if missing:
        raise ValueError("Output CSV is missing required columns: " + ", ".join(sorted(missing)))
    return rows


# ============================================================
# Reports
# ============================================================


def count_report(rows: list[dict], column: str, title: str) -> list[str]:
    counts: dict = {}
    for row in rows:
        value = row.get(column, "")
        if value is None:
            value = ""
        counts[value] = counts.get(value, 0) + 1
    lines = ["", title, "-" * 40]
    if not counts:
        lines.append("No values found.")
        return lines
    for key, value in sorted(counts.items(), key=lambda item: str(item[0])):
        label = key if key not in {"", None} else "<blank>"
        lines.append(f"{label}: {value}")
    return lines


def numeric_values(rows: list[dict], column: str) -> list[float]:
    values = []
    for row in rows:
        raw = row.get(column, "")
        if raw in {"", None}:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def numeric_report(rows: list[dict], column: str, title: str, precision: int) -> list[str]:
    values = numeric_values(rows, column)
    if not values:
        return ["", title, "-" * 40, "No valid numeric values found."]
    return [
        "", title, "-" * 40,
        f"Count: {len(values)}",
        f"Mean: {round(mean(values), precision)}",
        f"Min: {min(values)}",
        f"Max: {max(values)}",
    ]


# ============================================================
# Temporal Feedback Loop analysis
# ============================================================
# The engine records both "prediction" (stated in advance) and
# "behavioral_choice" (acted on afterward) for every trial, plus whether
# the trial's feedback was confirmatory or contradictory. Previously
# nothing ever compared these fields against each other or across
# trials, which meant the framework never actually reported on its own
# central premise: does prediction match behavior, and does contradictory
# feedback change what happens on the *next* trial. These two functions
# close that gap.


def sorted_completed_rows(rows: list[dict]) -> list[dict]:
    """Completed trials only, in original trial order (by trial_id)."""
    completed = [row for row in rows if row.get("completion_status") == "completed"]

    def trial_sort_key(row: dict):
        try:
            return int(row.get("trial_id", 0))
        except (TypeError, ValueError):
            return 0

    return sorted(completed, key=trial_sort_key)


def prediction_behavior_consistency_report(rows: list[dict]) -> list[str]:
    """
    For every completed trial where both prediction and behavioral_choice
    are real A/B responses (not blank/timed-out), report whether the
    participant's stated prediction matched what they actually chose,
    overall and broken down by block.
    """
    usable = [
        row for row in sorted_completed_rows(rows)
        if row.get("prediction") in {"A", "B"} and row.get("behavioral_choice") in {"A", "B"}
    ]
    lines = ["", "Prediction-Behavior Consistency", "-" * 40]
    if not usable:
        lines.append("No trials had both a prediction and a behavioral choice to compare.")
        return lines

    matched = [row for row in usable if row["prediction"] == row["behavioral_choice"]]
    rate = round(100.0 * len(matched) / len(usable), 1)
    lines.append(f"Comparable trials: {len(usable)}")
    lines.append(f"Prediction matched behavior: {len(matched)} ({rate}%)")
    lines.append(f"Prediction contradicted behavior: {len(usable) - len(matched)} ({round(100.0 - rate, 1)}%)")

    by_block: dict[str, list[bool]] = {}
    for row in usable:
        block = str(row.get("block", "") or "<blank>")
        by_block.setdefault(block, []).append(row["prediction"] == row["behavioral_choice"])
    if by_block:
        lines.append("")
        lines.append("By block:")
        for block in sorted(by_block):
            outcomes = by_block[block]
            block_rate = round(100.0 * sum(outcomes) / len(outcomes), 1)
            lines.append(f"  {block}: {sum(outcomes)}/{len(outcomes)} matched ({block_rate}%)")
    return lines


def feedback_carryover_report(rows: list[dict]) -> list[str]:
    """
    The actual "temporal feedback loop" question: after a trial gives
    confirmatory vs. mildly/strongly contradictory feedback, does the
    *next* trial's prediction-behavior consistency and affect rating
    shift? Buckets each trial by the contradiction level of the trial
    immediately before it, then compares consistency rate and mean
    affect across those buckets.
    """
    ordered = sorted_completed_rows(rows)
    lines = ["", "Temporal Feedback Carryover (effect of prior-trial contradiction)", "-" * 40]
    if len(ordered) < 2:
        lines.append("Not enough sequential trials to measure a carryover effect.")
        return lines

    buckets: dict[str, list[dict]] = {"none": [], "mild": [], "strong": []}
    for previous_row, current_row in zip(ordered, ordered[1:]):
        prior_contradiction = str(previous_row.get("contradiction", "") or "none").strip().lower()
        if prior_contradiction not in buckets:
            prior_contradiction = "none"
        buckets[prior_contradiction].append(current_row)

    any_bucket_populated = False
    for bucket_name in ("none", "mild", "strong"):
        bucket_rows = buckets[bucket_name]
        if not bucket_rows:
            continue
        any_bucket_populated = True
        comparable = [
            row for row in bucket_rows
            if row.get("prediction") in {"A", "B"} and row.get("behavioral_choice") in {"A", "B"}
        ]
        affect_values = numeric_values(bucket_rows, "affect")
        lines.append(f"Following '{bucket_name}' feedback ({len(bucket_rows)} trials):")
        if comparable:
            matched = sum(1 for row in comparable if row["prediction"] == row["behavioral_choice"])
            rate = round(100.0 * matched / len(comparable), 1)
            lines.append(f"  Prediction-behavior consistency: {matched}/{len(comparable)} ({rate}%)")
        else:
            lines.append("  Prediction-behavior consistency: no comparable trials")
        if affect_values:
            lines.append(f"  Mean affect rating: {round(mean(affect_values), 2)}")
        else:
            lines.append("  Mean affect rating: no valid affect values")

    if not any_bucket_populated:
        lines.append("No trials followed a scored feedback trial.")
    return lines


# ============================================================
# Analyzer
# ============================================================


def analyze_output(path: Path | None = None) -> str:
    path = Path(path or get_default_output_file())
    if not path.exists():
        return f"CSV file does not exist yet: {path}"
    try:
        rows = load_output(path)
    except Exception as exc:
        return f"Could not load TFL output.\n\n{type(exc).__name__}: {exc}"
    if not rows:
        return f"CSV exists but contains no trial rows: {path}"

    usable = [row for row in rows if row.get("completion_status") == "completed"]
    expected_minimum = ceil(len(rows) * 0.8)
    lines = [
        f"{framework.FRAMEWORK_ID} Analysis",
        "-" * 40,
        f"File: {path}",
        f"Rows: {len(rows)}",
    ]
    for column, title in [
        ("run_mode", "Run Mode Counts"),
        ("block", "Block Counts"),
        ("prediction", "Prediction Counts"),
        ("behavioral_choice", "Behavioral Choice Counts"),
        ("contradiction", "Contradiction Counts"),
        ("feedback_level", "Feedback Level Counts"),
        ("completion_status", "Completion Status Counts"),
    ]:
        lines.extend(count_report(rows, column, title))
    lines.extend(numeric_report(rows, "affect", "Affect Summary", 3))
    lines.extend(numeric_report(rows, "prediction_rt", "Prediction RT Summary", 4))
    lines.extend(numeric_report(rows, "behavioral_rt", "Behavioral RT Summary", 4))
    lines.extend(prediction_behavior_consistency_report(rows))
    lines.extend(feedback_carryover_report(rows))
    lines.extend([
        "", "Completion Gate", "-" * 40,
        f"Completed usable trials: {len(usable)}",
        f"Recommended minimum usable trials: {expected_minimum}",
        (
            f"PASS - {len(usable)} / {len(rows)} usable trials"
            if len(usable) >= expected_minimum
            else f"FAIL - {len(usable)} / {len(rows)} usable trials"
        ),
    ])
    return "\n".join(lines)


__all__ = [
    "get_output_dir", "get_default_output_file", "get_latest_output_file",
    "get_timestamped_output_file", "timestamp_string", "valid_affect_value",
    "validate_affect", "validate_rows", "write_rows", "save_rows", "load_output",
    "count_report", "numeric_values", "numeric_report", "analyze_output",
    "sanitize_session_id", "get_autosave_file", "autosave_rows", "remove_autosave_file",
    "sorted_completed_rows", "prediction_behavior_consistency_report", "feedback_carryover_report",
]
