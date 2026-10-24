"""
File: frameworks/TFL/analysis.py

Purpose
-------
Analyze TFL CSV output with the standard library. The report follows
the 02_Execution reference analysis section by section, including its
completion gate, without pandas.

Communication / relationships
-----------------------------
- services/tfl_analysis.py calls analyze_output(), load_output(), and
  get_default_output_file().
- framework.py exposes lazy wrappers; cli_runner.py prints the report.
- Reads the default file location through frameworks/TFL/output.py.

Settings / parameters
---------------------
- Sections: Run Metadata, Trial Counts, Prediction and Behavior, Affect
  and Reaction Time, Prior Consistency, Contradiction, Probes, Delayed
  Reentry, Perturbations, Response Timer (only when a timer was used),
  Completion Gate.
- Summaries report count, mean, std (sample, n-1), min, 25%, 50%, 75%,
  and max, with linear-interpolated quartiles, as pandas.describe() does.
- Completion gate: rows with A/B prediction, A/B behavioral choice, and a
  non-blank affect, against int(row_count * 0.8), as in the reference.

Edge cases
----------
- A missing, empty, or header-less file returns a readable message
  instead of raising from analyze_output().
- Blank values are counted as "<blank>" where pandas shows NaN.
- Boolean columns accept True/1/yes, case-insensitively.

Known limitations
-----------------
- Text layout differs from pandas' printed tables; the numbers and the
  gate rule are the reference's.

Examples
--------
- print(analyze_output())
- analyze_output(Path("tfl_output_20261024_101500_000000.csv"))
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

from . import settings
from .output import latest_output_file

SUMMARY_KEYS = ("count", "mean", "std", "min", "25%", "50%", "75%", "max")


# ============================================================
# Loading
# ============================================================
def get_output_dir() -> Path:
    return latest_output_file().parent


def get_default_output_file() -> Path:
    return latest_output_file()


def get_latest_output_file() -> Path:
    return latest_output_file()


def load_output(path: Path | str | None = None) -> list[dict]:
    path = Path(path or get_default_output_file())
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if not fieldnames:
        raise ValueError(f"Output CSV has no header: {path}")
    missing = {"prediction", "behavioral_choice", "affect"} - set(fieldnames)
    if missing:
        raise ValueError("Output CSV is missing required columns: " + ", ".join(sorted(missing)))
    return rows


# ============================================================
# Small statistics helpers
# ============================================================
def is_true(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def numbers(rows: list[dict], column: str) -> list[float]:
    values = []
    for row in rows:
        text = str(row.get(column, "") or "").strip()
        if not text:
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        if math.isfinite(value):
            values.append(value)
    return values


def quantile(sorted_values: list[float], q: float) -> float:
    position = (len(sorted_values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def describe(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    count = len(ordered)
    mean = sum(ordered) / count
    std = math.sqrt(sum((v - mean) ** 2 for v in ordered) / (count - 1)) if count > 1 else float("nan")
    return {
        "count": count, "mean": mean, "std": std, "min": ordered[0],
        "25%": quantile(ordered, 0.25), "50%": quantile(ordered, 0.5),
        "75%": quantile(ordered, 0.75), "max": ordered[-1],
    }


def format_describe(stats: dict, indent: str = "") -> list[str]:
    if not stats.get("count"):
        return [f"{indent}count: 0"]
    lines = []
    for key in SUMMARY_KEYS:
        value = stats[key]
        text = str(value) if key == "count" else ("NaN" if math.isnan(value) else f"{value:.6f}")
        lines.append(f"{indent}{key:<6} {text}")
    return lines


def value_counts(rows: list[dict], column: str) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    order: list[str] = []
    for row in rows:
        value = str(row.get(column, "") or "")
        if value not in counts:
            order.append(value)
            counts[value] = 0
        counts[value] += 1
    return sorted(((v, counts[v]) for v in order), key=lambda item: -item[1])


def format_counts(rows: list[dict], column: str) -> list[str]:
    pairs = value_counts(rows, column)
    if not pairs:
        return ["(no rows)"]
    return [f"{value or '<blank>'}: {count}" for value, count in pairs]


def section(title: str) -> list[str]:
    return ["", title, "-" * len(title)]


# ============================================================
# Report sections (reference order)
# ============================================================
def report_metadata(rows, columns) -> list[str]:
    lines = section("Run Metadata")
    if "framework_id" in columns:
        lines += ["Framework counts:"] + format_counts(rows, "framework_id")
    if "run_mode" in columns:
        lines += ["", "Run mode counts:"] + format_counts(rows, "run_mode")
    return lines


def report_trial_counts(rows, columns) -> list[str]:
    lines = section("Trial Counts") + ["Total trials:", str(len(rows))]
    if "block" in columns:
        lines += ["", "Trials by block:"] + format_counts(rows, "block")
    if "stimulus_id" in columns:
        unique = {row.get("stimulus_id", "") for row in rows if row.get("stimulus_id", "")}
        lines += ["", "Unique stimuli used:", str(len(unique))]
    return lines


def report_prediction_behavior(rows) -> list[str]:
    return (section("Prediction and Behavior") + ["Prediction counts:"] + format_counts(rows, "prediction")
            + ["", "Behavioral choice counts:"] + format_counts(rows, "behavioral_choice"))


def report_affect_rt(rows, columns) -> list[str]:
    lines = section("Affect and Reaction Time")
    if "affect" in columns:
        lines += ["Affect summary:"] + format_describe(describe(numbers(rows, "affect")))
    rt_columns = [c for c in ("prediction_rt", "behavioral_rt") if c in columns]
    if rt_columns:
        lines += ["", "Reaction time summary:"]
        for column in rt_columns:
            lines += [f"  {column}:"] + format_describe(describe(numbers(rows, column)), "    ")
    return lines


def report_prior_consistency(rows) -> list[str]:
    lines = section("Prior Consistency")
    predicted = [r for r in rows if r.get("prediction") in {"A", "B"}]
    if predicted:
        rate = sum(r["prediction"] == r.get("prior_instruction") for r in predicted) / len(predicted)
        lines += ["Prior-consistent prediction rate:", str(round(rate, 3))]
    else:
        lines.append("No A/B predictions available.")
    behaved = [r for r in rows if r.get("behavioral_choice") in {"A", "B"}]
    if behaved:
        rate = sum(r["behavioral_choice"] == r.get("prior_instruction") for r in behaved) / len(behaved)
        lines += ["", "Prior-consistent behavioral choice rate:", str(round(rate, 3))]
    return lines


def report_contradiction(rows, columns) -> list[str]:
    lines = section("Contradiction")
    if "contradiction" not in columns:
        return lines + ["No contradiction column found."]
    contradicted = [r for r in rows if r.get("contradiction") in {"mild", "strong"}]
    lines += ["Contradiction trial count:", str(len(contradicted))]
    if contradicted:
        lines += ["", "Contradiction counts:"] + format_counts(contradicted, "contradiction")
        lines += ["", "Affect by contradiction level:"]
        for level in sorted({r["contradiction"] for r in contradicted}):
            subset = [r for r in contradicted if r["contradiction"] == level]
            lines += [f"  {level}:"] + format_describe(describe(numbers(subset, "affect")), "    ")
    return lines


def report_probes(rows, columns) -> list[str]:
    lines = section("Probes")
    if "content_probe" not in columns:
        return lines + ["No content_probe column found."]
    probes = [r for r in rows if r.get("content_probe", "")]
    codable = [r for r in probes if r["content_probe"] in {"A", "B"}]
    lines += ["Probe responses:", str(len(probes)), "", "Codable probe responses:", str(len(codable))]
    if len(codable) > 1:
        matches = [False] + [codable[i]["content_probe"] == codable[i - 1]["content_probe"]
                             for i in range(1, len(codable))]
        lines += ["", "Simple recurrence rate across probes:", str(round(sum(matches) / len(matches), 3))]
    return lines


def report_delayed_reentry(rows, columns) -> list[str]:
    lines = section("Delayed Reentry")
    if "delayed_reentry" not in columns:
        return lines + ["No delayed_reentry column found."]
    delayed = [r for r in rows if is_true(r.get("delayed_reentry", ""))]
    lines += ["Delayed reentry trial count:", str(len(delayed))]
    if delayed:
        lines += ["", "Delayed reentry predictions:"] + format_counts(delayed, "prediction")
        lines += ["", "Delayed reentry behavioral choices:"] + format_counts(delayed, "behavioral_choice")
    return lines


def report_perturbations(rows, columns) -> list[str]:
    lines = section("Perturbations")
    if "perturbation_trial" not in columns:
        return lines + ["No perturbation_trial column found."]
    perturbed = [r for r in rows if is_true(r.get("perturbation_trial", ""))]
    lines += ["Perturbation trial count:", str(len(perturbed))]
    if not perturbed:
        return lines + ["No perturbation trials in this run."]
    return lines + ["", "Perturbation types:"] + format_counts(perturbed, "perturbation_type")


def report_response_timer(rows, columns) -> list[str]:
    if "response_timer_sec" not in columns:
        return []
    timed = [r for r in rows if str(r.get("response_timer_sec", "")).strip()]
    if not timed:
        return []
    return section("Response Timer") + [
        f"Timed trials: {len(timed)}",
        "Time limits (seconds): " + ", ".join(f"{v or '<blank>'} x{c}" for v, c in value_counts(timed, "response_timer_sec")),
        f"Prediction timeouts: {sum(is_true(r.get('prediction_timed_out')) for r in timed)}",
        f"Behavioral choice timeouts: {sum(is_true(r.get('behavioral_timed_out')) for r in timed)}",
    ]


def completion_gate(rows) -> tuple[int, int, bool]:
    usable = [r for r in rows if r.get("prediction") in {"A", "B"}
              and r.get("behavioral_choice") in {"A", "B"}
              and str(r.get("affect", "") or "").strip()]
    minimum = int(len(rows) * 0.8)
    return len(usable), minimum, len(usable) >= minimum


def report_completion_gate(rows) -> list[str]:
    usable, minimum, passed = completion_gate(rows)
    verdict = "PASS" if passed else "FAIL"
    return section("Completion Gate") + [
        "Completed usable trials:", str(usable), "",
        "Recommended minimum usable trials:", str(minimum), "",
        f"{verdict} \u2014 {usable} / {len(rows)} usable trials",
    ]


# ============================================================
# Entry point
# ============================================================
def analyze_output(path: Path | str | None = None) -> str:
    path = Path(path or get_default_output_file())
    if not path.exists():
        return f"CSV file does not exist yet: {path}"
    try:
        rows = load_output(path)
    except Exception as exc:
        return f"Could not load TFL output.\n\n{type(exc).__name__}: {exc}"
    if not rows:
        return f"CSV exists but contains no trial rows: {path}"
    columns = set(rows[0].keys())
    lines = [f"{settings.FRAMEWORK_ID} Analysis", "-" * 40, f"File: {path}"]
    lines += report_metadata(rows, columns)
    lines += report_trial_counts(rows, columns)
    lines += report_prediction_behavior(rows)
    lines += report_affect_rt(rows, columns)
    lines += report_prior_consistency(rows)
    lines += report_contradiction(rows, columns)
    lines += report_probes(rows, columns)
    lines += report_delayed_reentry(rows, columns)
    lines += report_perturbations(rows, columns)
    lines += report_response_timer(rows, columns)
    lines += report_completion_gate(rows)
    return "\n".join(lines)


__all__ = [
    "get_output_dir", "get_default_output_file", "get_latest_output_file", "load_output",
    "describe", "value_counts", "completion_gate", "analyze_output",
]
