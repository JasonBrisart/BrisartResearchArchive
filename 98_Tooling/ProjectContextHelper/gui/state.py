"""
File: gui/state.py

Purpose
-------
Hold the window's shared state (GuiState: the Tk variables behind every control, the last
  fully loaded settings, the build runner, and the detected CPU core count) and translate
  between it and ScanSettings in both directions, including the CPU Cores selector labels.
  Also restores the preference and last-used settings at startup and autosaves the
  preference checkbox.

Communication / relationships
-----------------------------
Imports app (EXPORTS_DIRNAME), export/settings.py (presets, ScanSettings, core detection),
  gui/jobs.py (JobRunner), and storage (preferences, last-used settings). Imported by
  gui/build_tab.py, gui/options_tab.py, gui/extras_tab.py, gui/about_tab.py (GuiState and
  the conversions each needs), and gui/window.py (make_gui_state). Running a build lives in gui/build_tab.py, the
  only place that starts one.

Settings / parameters
---------------------
Size fields are decimal MB (1 MB = 1000000 bytes). The CPU Cores selector text is "Auto (N
  cores)", "1 core", or "N cores"; worker_choices lists Auto plus 1 through this machine's
  limit (capped at 32). Open Export Folder After Build autosaves on every change.

Edge cases
----------
Size fields reject non-numeric, infinite, NaN, and nonpositive values with a labelled
  ValueError; a negative skipped-details limit counts as 0. A saved worker count above this
  machine's limit is shown (and next saved) as the limit. Setting profile_var fires the Build
  tab's preset reset, so apply_custom_profile_to_state sets the profile first and then
  reapplies the loaded values. The project folder is never restored at startup.

Known limitations
-----------------
Not every ScanSettings field has a control. The hidden ones (extension and exclusion sets,
  Git history limit, required completeness) come from base_settings while its profile matches
  the dropdown; picking another built-in profile resets them, and resets CPU Cores to Auto.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.state import build_settings_from_state, make_gui_state

    window = tk.Tk()
    state = make_gui_state()
    settings = build_settings_from_state(state)
    print(settings.profile, settings.max_file_bytes, settings.workers)
    window.destroy()
"""

from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import tkinter as tk

from app import EXPORTS_DIRNAME
from export.settings import (
    AUTO_WORKERS,
    DEFAULT_PROFILE,
    ScanSettings,
    detect_cpu_cores,
    settings_for_profile,
    worker_limit,
)
from gui.jobs import JobRunner
import storage


@dataclass(slots=True)
class GuiState:
    selected_folder: tk.StringVar
    profile_var: tk.StringVar
    output_dir_var: tk.StringVar
    max_file_mb_var: tk.StringVar
    max_total_mb_var: tk.StringVar
    skipped_limit_var: tk.StringVar
    workers_var: tk.StringVar
    include_zip_var: tk.BooleanVar
    redact_var: tk.BooleanVar
    include_hashes_var: tk.BooleanVar
    include_line_counts_var: tk.BooleanVar
    include_tree_var: tk.BooleanVar
    include_index_var: tk.BooleanVar
    include_contents_var: tk.BooleanVar
    include_skipped_details_var: tk.BooleanVar
    include_git_state_var: tk.BooleanVar
    timestamped_folder_var: tk.BooleanVar
    open_after_build_var: tk.BooleanVar
    custom_profile_var: tk.StringVar
    status_text: tk.StringVar
    last_export_dir: Path | None = None
    base_settings: ScanSettings | None = None
    jobs: JobRunner | None = None
    history_refresh: Callable[[], None] | None = None
    closing: bool = False
    cpu_cores: int = 1


def bytes_to_mb_text(value: int) -> str:
    mb_value = value / 1_000_000
    if mb_value.is_integer():
        return str(int(mb_value))
    return str(mb_value).rstrip("0").rstrip(".")


def make_bool_var(value: bool) -> tk.BooleanVar:
    return tk.BooleanVar(value=bool(value))


def wire_preference_autosave(state: GuiState) -> None:
    def persist(*_args) -> None:
        storage.save_preferences(storage.AppPreferences(open_after_build=state.open_after_build_var.get()))
    state.open_after_build_var.trace_add("write", persist)


def core_label(count: int) -> str:
    return "1 core" if count == 1 else f"{count} cores"


def worker_choices(cores: int) -> list[str]:
    limit = worker_limit(cores)
    return [f"Auto ({core_label(limit)})"] + [core_label(count) for count in range(1, limit + 1)]


def workers_to_label(value: int | str, cores: int) -> str:
    if value == AUTO_WORKERS:
        return worker_choices(cores)[0]
    return core_label(max(1, min(int(value), worker_limit(cores))))


def label_to_workers(label: str) -> int | str:
    if label.startswith("Auto"):
        return AUTO_WORKERS
    return int(label.split()[0])


def make_gui_state() -> GuiState:
    cpu_cores = detect_cpu_cores()
    settings = settings_for_profile(DEFAULT_PROFILE)
    preferences = storage.load_preferences()
    remembered_settings = storage.load_last_settings()
    active_settings = remembered_settings or settings
    state = GuiState(
        selected_folder=tk.StringVar(value=""),
        profile_var=tk.StringVar(value=active_settings.profile),
        output_dir_var=tk.StringVar(value=active_settings.output_dir_name or EXPORTS_DIRNAME),
        max_file_mb_var=tk.StringVar(value=bytes_to_mb_text(active_settings.max_file_bytes)),
        max_total_mb_var=tk.StringVar(value=bytes_to_mb_text(active_settings.max_total_bytes)),
        skipped_limit_var=tk.StringVar(value=str(active_settings.skipped_details_limit)),
        workers_var=tk.StringVar(value=workers_to_label(active_settings.workers, cpu_cores)),
        include_zip_var=make_bool_var(active_settings.include_snapshot_zip),
        redact_var=make_bool_var(active_settings.redact_sensitive_lines),
        include_hashes_var=make_bool_var(active_settings.include_hashes),
        include_line_counts_var=make_bool_var(active_settings.include_line_counts),
        include_tree_var=make_bool_var(active_settings.include_folder_tree),
        include_index_var=make_bool_var(active_settings.include_file_index),
        include_contents_var=make_bool_var(active_settings.include_file_contents),
        include_skipped_details_var=make_bool_var(active_settings.include_skipped_details),
        include_git_state_var=make_bool_var(active_settings.include_git_state),
        timestamped_folder_var=make_bool_var(active_settings.timestamped_export_folder),
        open_after_build_var=tk.BooleanVar(value=preferences.open_after_build),
        custom_profile_var=tk.StringVar(value=""),
        status_text=tk.StringVar(value="Select a project folder."),
        cpu_cores=cpu_cores,
    )
    state.base_settings = deepcopy(active_settings)
    state.jobs = JobRunner()
    wire_preference_autosave(state)
    return state


def apply_settings_to_state(state: GuiState, settings: ScanSettings) -> None:
    state.base_settings = deepcopy(settings)
    state.output_dir_var.set(settings.output_dir_name or EXPORTS_DIRNAME)
    state.max_file_mb_var.set(bytes_to_mb_text(settings.max_file_bytes))
    state.max_total_mb_var.set(bytes_to_mb_text(settings.max_total_bytes))
    state.skipped_limit_var.set(str(settings.skipped_details_limit))
    state.workers_var.set(workers_to_label(settings.workers, state.cpu_cores))
    state.include_zip_var.set(settings.include_snapshot_zip)
    state.redact_var.set(settings.redact_sensitive_lines)
    state.include_hashes_var.set(settings.include_hashes)
    state.include_line_counts_var.set(settings.include_line_counts)
    state.include_tree_var.set(settings.include_folder_tree)
    state.include_index_var.set(settings.include_file_index)
    state.include_contents_var.set(settings.include_file_contents)
    state.include_skipped_details_var.set(settings.include_skipped_details)
    state.include_git_state_var.set(settings.include_git_state)
    state.timestamped_folder_var.set(settings.timestamped_export_folder)


def apply_profile_defaults(state: GuiState) -> None:
    settings = settings_for_profile(state.profile_var.get())
    apply_settings_to_state(state, settings)


def apply_custom_profile_to_state(state: GuiState, settings: ScanSettings) -> None:
    state.profile_var.set(settings.profile)
    apply_settings_to_state(state, settings)


def parse_mb_to_bytes(value: str, label: str) -> int:
    try:
        parsed = float(value)
    except ValueError:
        raise ValueError(f"{label} must be numeric.")
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        raise ValueError(f"{label} must be a finite number.")
    try:
        result = int(parsed * 1_000_000)
    except (ValueError, OverflowError):
        raise ValueError(f"{label} must be numeric.")
    if result <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return result


def parse_nonnegative_int(value: str, label: str) -> int:
    try:
        return max(0, int(value))
    except ValueError:
        raise ValueError(f"{label} must be a whole number.")


def build_settings_from_state(state: GuiState) -> ScanSettings:
    """
    Start from the last fully loaded settings when their profile still matches
    the dropdown, so values the window does not show (custom extensions and
    exclusions, the Git history limit) survive builds and profile saves.
    """
    profile = state.profile_var.get()
    base = state.base_settings
    if base is not None and base.profile == profile:
        settings = deepcopy(base)
    else:
        settings = settings_for_profile(profile)
    settings.output_dir_name = state.output_dir_var.get().strip() or EXPORTS_DIRNAME
    settings.include_snapshot_zip = state.include_zip_var.get()
    settings.redact_sensitive_lines = state.redact_var.get()
    settings.include_hashes = state.include_hashes_var.get()
    settings.include_line_counts = state.include_line_counts_var.get()
    settings.include_folder_tree = state.include_tree_var.get()
    settings.include_file_index = state.include_index_var.get()
    settings.include_file_contents = state.include_contents_var.get()
    settings.include_skipped_details = state.include_skipped_details_var.get()
    settings.include_git_state = state.include_git_state_var.get()
    settings.timestamped_export_folder = state.timestamped_folder_var.get()
    settings.max_file_bytes = parse_mb_to_bytes(state.max_file_mb_var.get(), "Max File MB")
    settings.max_total_bytes = parse_mb_to_bytes(state.max_total_mb_var.get(), "Max Total MB")
    settings.skipped_details_limit = parse_nonnegative_int(state.skipped_limit_var.get(), "Skipped Details Limit")
    settings.workers = label_to_workers(state.workers_var.get())
    return settings
