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
]
