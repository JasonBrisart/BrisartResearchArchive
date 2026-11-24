"""
File: frameworks/TFL/analysis.py

Purpose
-------
Analyze TFL session CSVs with the standard library only. One session gives
the 02_Execution reference report, section by section including its
completion gate, with no pandas. Several sessions give the same sections
pooled across all of them, plus a per-session comparison in which each
session keeps its own completion gate.

Communication / relationships
-----------------------------
- controllers/system_controller.py calls analyze_outputs() for the Results
  page; cli.py calls analyze_output() and analyze_outputs() for "analyze".
- Reads FRAMEWORK_ID from frameworks/TFL/settings.py for the report title.
- Does not decide which session is "the latest": the host picks files
  (controllers/system_controller.py through the Results page, cli.py through
  frameworks/TFL/output.latest_session_file()) and passes them in, so this
  module depends on neither the output folder nor the host application.

Settings / parameters
---------------------
- Single-session sections: Session, Run Metadata, Trial Counts, Prediction
  and Behavior, Affect and Reaction Time, Prior Consistency, Contradiction,
  Probes, Delayed Reentry, Perturbations, Response Timer (only when a
  timer was used), Completion Gate.
- Pooled report: Sessions, Per Session, then every section above except the
  gate, computed over all pooled trials. report_sections() builds those
  sections for both reports, so they cannot drift apart.
- analyze_output(path) analyzes one file; analyze_outputs(paths) is exactly
  that for one path and pools two or more, in the order given.
- Summaries report count, mean, std (sample, n-1), min, 25%, 50%, 75%, and
  max, with linear-interpolated quartiles, matching pandas describe().
- Completion gate: complete rows with an A/B prediction, an A/B behavioral
  choice, and a non-blank affect, against int(complete_rows * 0.8), as in
  the reference. A pooled report shows each session's gate and never a
  pooled one, so one good session cannot hide a failed one.

Edge cases
----------
- Rows marked trial_status "in_progress" (the partly answered last trial of
  an interrupted run) are excluded from every figure and counted.
- CSVs without a trial_status column (0.9.3 and earlier) are treated as all
  complete; columns missing from older files count as blank when pooled.
- A single missing, empty, or header-less file returns a readable message
  instead of raising. A file that lacks the prediction, behavioral_choice,
  or affect column is reported with its missing columns.
- In a pooled analysis an unusable file is listed under "Left out" with its
  reason and excluded from every figure while the others are analyzed; if
  none can be analyzed, the reasons are shown. The same path listed twice
  is analyzed once.
- Contradiction, Probes, Delayed Reentry, and Perturbations print a "No
  <column> column found" line when their column is absent.
- Blank values are counted as "<blank>" where pandas shows NaN.
- Trials whose prediction timed out still appear in the Contradiction
  counts, because the engine records the feedback level for them (see
  frameworks/TFL/feedback.py).

Known limitations
-----------------
- Text layout differs from pandas' printed tables; the figures and the gate
  rule are the reference's.
- Pooling treats every trial from every selected session as one data set.
  It does not separate run modes, seeds, or participants; Run Metadata and
  the Per Session blocks show what was pooled.
- There are no statistics across sessions (no between-session tests or
  confidence intervals), and no charts.

Examples
--------
- analyze_output(Path("tfl_output_2026-10-24_18-45-12.csv"))
- analyze_outputs([Path("a.csv"), Path("b.csv")])
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

from . import settings

SUMMARY_KEYS = ("count", "mean", "std", "min", "25%", "50%", "75%", "max")
REQUIRED_COLUMNS = {"prediction", "behavioral_choice", "affect"}


def load_output(path: Path | str) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if not fieldnames:
        raise ValueError(f"Output CSV has no header: {path}")
    missing = REQUIRED_COLUMNS - set(fieldnames)
    if missing:
        raise ValueError("Output CSV is missing required columns: " + ", ".join(sorted(missing)))
    return rows


def split_by_status(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    complete = [row for row in rows if (row.get("trial_status") or "complete") == "complete"]
    in_progress = [row for row in rows if (row.get("trial_status") or "complete") != "complete"]
    return complete, in_progress


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


def report_session(path, complete, in_progress, columns) -> list[str]:
    lines = section("Session") + [f"File: {path}", f"Complete trials: {len(complete)}"]
    if in_progress:
        lines.append(f"Incomplete trials excluded: {len(in_progress)} (run was interrupted mid-trial)")
    if "protocol_edition" in columns:
        editions = sorted({str(row.get("protocol_edition", "")) for row in complete if row.get("protocol_edition", "")})
        lines.append("Protocol edition: " + (", ".join(editions) if editions else "<blank>"))
    if "random_seed" in columns:
        seeds = sorted({str(row.get("random_seed", "")) for row in complete if row.get("random_seed", "")})
        lines.append("Random seed: " + (", ".join(seeds) if seeds else "<blank>"))
    if "session_label" in columns:
        labels = sorted({row.get("session_label", "") for row in complete if row.get("session_label", "")})
        lines.append("Session label: " + (", ".join(labels) if labels else "(none)"))
    return lines


def report_response_timer(rows, columns) -> list[str]:
    if "response_timer_sec" not in columns:
        return []
    timed = [r for r in rows if str(r.get("response_timer_sec", "")).strip()]
    if not timed:
        return []
    limits = ", ".join(f"{value or '<blank>'} x{count}" for value, count in value_counts(timed, "response_timer_sec"))
    return section("Response Timer") + [
        f"Timed trials: {len(timed)}",
        f"Time limits (seconds): {limits}",
        f"Prediction timeouts: {sum(is_true(r.get('prediction_timed_out')) for r in timed)}",
        f"Behavioral choice timeouts: {sum(is_true(r.get('behavioral_timed_out')) for r in timed)}",
    ]


def completion_gate(rows) -> tuple[int, int, bool]:
    usable = [r for r in rows if r.get("prediction") in {"A", "B"}
              and r.get("behavioral_choice") in {"A", "B"}
              and r.get("affect") is not None and str(r.get("affect", "")).strip()]
    minimum = int(len(rows) * 0.8)
    return len(usable), minimum, len(usable) >= minimum


def report_completion_gate(rows) -> list[str]:
    usable, minimum, passed = completion_gate(rows)
    return section("Completion Gate") + [
        "Completed usable trials:", str(usable), "",
        "Recommended minimum usable trials:", str(minimum), "",
        f"{'PASS' if passed else 'FAIL'} \u2014 {usable} / {len(rows)} usable trials",
    ]


def report_sections(rows, columns) -> list[str]:
    """Every section of the reference report except the session header and the gate."""
    lines = report_metadata(rows, columns)
    lines += report_trial_counts(rows, columns)
    lines += report_prediction_behavior(rows)
    lines += report_affect_rt(rows, columns)
    lines += report_prior_consistency(rows)
    lines += report_contradiction(rows, columns)
    lines += report_probes(rows, columns)
    lines += report_delayed_reentry(rows, columns)
    lines += report_perturbations(rows, columns)
    lines += report_response_timer(rows, columns)
    return lines


def analyze_output(path: Path | str) -> str:
    path = Path(path)
    if not path.exists():
        return f"CSV file does not exist: {path}"
    try:
        rows = load_output(path)
    except Exception as exc:
        return f"Could not load TFL output.\n\n{type(exc).__name__}: {exc}"
    complete, in_progress = split_by_status(rows)
    if not complete:
        return f"CSV exists but contains no completed trials: {path}"
    columns = set(rows[0].keys())
    lines = [f"{settings.FRAMEWORK_ID} Analysis", "-" * 40]
    lines += report_session(path, complete, in_progress, columns)
    lines += report_sections(complete, columns)
    lines += report_completion_gate(complete)
    return "\n".join(lines)


# ============================================================
# Several sessions at once
# ============================================================
def mean_text(values: list[float], unit: str = "") -> str:
    return f"{sum(values) / len(values):.2f}{unit}" if values else "n/a"


def session_block(number: int, path: Path, complete: list[dict]) -> list[str]:
    usable, minimum, passed = completion_gate(complete)
    timeouts = sum(is_true(r.get("prediction_timed_out")) + is_true(r.get("behavioral_timed_out"))
                   for r in complete)
    seeds = sorted({str(r.get("random_seed", "")) for r in complete if r.get("random_seed", "")})
    labels = sorted({r.get("session_label", "") for r in complete if r.get("session_label", "")})
    modes = sorted({r.get("run_mode", "") for r in complete if r.get("run_mode", "")})
    return [
        f"{number}. {path.name}",
        f"   Complete trials: {len(complete)}   Usable: {usable}   Gate: {'PASS' if passed else 'FAIL'}",
        f"   Mean affect: {mean_text(numbers(complete, 'affect'))}"
        f"   Mean prediction RT: {mean_text(numbers(complete, 'prediction_rt'), ' s')}"
        f"   Timeouts: {timeouts}",
        f"   Seed: {', '.join(seeds) or '<blank>'}   Label: {', '.join(labels) or '(none)'}"
        f"   Run mode: {', '.join(modes) or '<blank>'}",
    ]


def analyze_outputs(paths) -> str:
    """Analyze one session, or pool several. One path is exactly analyze_output()."""
    unique: list[Path] = []
    for item in paths:
        path = Path(item)
        if path not in unique:
            unique.append(path)
    if not unique:
        return "No sessions were selected."
    if len(unique) == 1:
        return analyze_output(unique[0])

    sessions, skipped, in_progress_total = [], [], 0
    for path in unique:
        try:
            rows = load_output(path)
        except Exception as exc:
            skipped.append(f"{path.name}: {type(exc).__name__}: {exc}")
            continue
        complete, in_progress = split_by_status(rows)
        in_progress_total += len(in_progress)
        if not complete:
            skipped.append(f"{path.name}: no completed trials")
            continue
        sessions.append((path, complete))
    if not sessions:
        return "None of the selected sessions could be analyzed.\n\n" + "\n".join(skipped)

    pooled = [row for _, complete in sessions for row in complete]
    columns = set().union(*(row.keys() for row in pooled))
    lines = [f"{settings.FRAMEWORK_ID} Combined Analysis", "-" * 40]
    lines += section("Sessions") + [
        f"Files selected: {len(unique)}",
        f"Files analyzed: {len(sessions)}",
        f"Complete trials pooled: {len(pooled)}",
    ]
    if in_progress_total:
        lines.append(f"Incomplete trials excluded: {in_progress_total} (interrupted runs)")
    if skipped:
        lines += ["", "Left out:"] + [f"  {item}" for item in skipped]
    lines += ["", "Figures below pool every trial from the analyzed sessions. Each session's",
              "own completion gate is shown under Per Session; a pooled gate is not reported."]
    lines += section("Per Session")
    for number, (path, complete) in enumerate(sessions, start=1):
        lines += session_block(number, path, complete) + [""]
    lines.pop()
    lines += report_sections(pooled, columns)
    return "\n".join(lines)


__all__ = ["load_output", "split_by_status", "describe", "value_counts", "completion_gate",
           "analyze_output", "analyze_outputs"]

