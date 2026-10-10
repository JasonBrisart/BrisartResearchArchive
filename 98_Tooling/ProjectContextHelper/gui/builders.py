"""
File: gui/builders.py

Purpose
-------
Bridge tkinter state to ScanSettings, restore preferences/last successful build settings,
  validate GUI inputs, and execute exports.

Implemented responsibilities:
- bytes_to_mb_text: Convert integer bytes to decimal MB text, omitting an unnecessary fractional
  suffix for integral MB values.
- make_bool_var: Construct a tkinter BooleanVar from a truth-coerced input value.
- wire_preference_autosave: Register write traces on folder-opening, startup-check, and auto-
  install variables; each change writes a complete AppPreferences record.
- make_gui_state: Load archive defaults, app preferences, and last saved export settings;
  initialize tkinter variables and wire preference autosave; leave folder/session-export state
  empty.
- profile_description: Return the standard/archive explanatory label or Unknown profile for an
  unsupported string.
- apply_settings_to_state: Copy the GUI-exposed output settings into tkinter variables; this
  does not itself change profile_var or expose every ScanSettings field.
- apply_profile_defaults: Resolve the current profile variable to its built-in preset and copy
  the exposed settings into state.
- apply_custom_profile_to_state: Set profile_var first, allowing the preset trace to fire, then
  reapply loaded exposed values so custom settings win.
- parse_mb_to_bytes: Parse decimal MB text, reject nonnumeric/nonfinite/nonpositive results, and
  convert by multiplying by 1000000 and truncating to int.
- parse_nonnegative_int: Parse a whole-number string and clamp negatives to zero; invalid
  integer syntax raises a labeled ValueError.
- build_settings_from_state: Start with the selected built-in preset, overlay exposed GUI
  controls, validate size/detail inputs, and return ScanSettings.
- run_project_build: Require a selected folder, build validated settings, call create_context,
  remember the returned export directory in session state, and save last-used settings after
  success.
- persist: Nested preference trace callback: read the three current BooleanVars and pass a new
  AppPreferences record to save_preferences.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- services.storage: AppPreferences, load_preferences, save_preferences, load_last_settings,
  save_last_settings.
- core.constants: DEFAULT_PROFILE, EXPORTS_DIRNAME, PROFILE_ARCHIVE, PROFILE_STANDARD,
  settings_for_profile.
- core.builder: create_context.
- core.models: BuildResult, ScanSettings.

Consumers in the supplied source:
- gui/about_tab.py imports GuiState.
- gui/build_tab.py imports GuiState, apply_profile_defaults, profile_description,
  run_project_build.
- gui/extras_tab.py imports GuiState.
- gui/main_gui.py imports make_gui_state.
- gui/options_tab.py imports GuiState.
- gui/profiles_section.py imports GuiState, apply_custom_profile_to_state,
  build_settings_from_state.

Settings / parameters
---------------------
GuiState holds tkinter variables. GUI sizes use decimal MB (1000000 bytes). Profile defaults
  come from core.constants; preference changes autosave and successful builds save last-used
  export settings.

Function signatures (nested callbacks are scoped to their enclosing function):
- bytes_to_mb_text(value: int) -> str
- make_bool_var(value: bool) -> tk.BooleanVar
- wire_preference_autosave(state: GuiState) -> None
- make_gui_state() -> GuiState
- profile_description(profile: str) -> str
- apply_settings_to_state(state: GuiState, settings: ScanSettings) -> None
- apply_profile_defaults(state: GuiState) -> None
- apply_custom_profile_to_state(state: GuiState, settings: ScanSettings) -> None
- parse_mb_to_bytes(value: str, label: str) -> int
- parse_nonnegative_int(value: str, label: str) -> int
- build_settings_from_state(state: GuiState) -> ScanSettings
- run_project_build(state: GuiState) -> BuildResult
- persist(*_args) -> None

GuiState record fields:
- selected_folder: tk.StringVar (required constructor field)
- profile_var: tk.StringVar (required constructor field)
- output_dir_var: tk.StringVar (required constructor field)
- max_file_mb_var: tk.StringVar (required constructor field)
- max_total_mb_var: tk.StringVar (required constructor field)
- skipped_limit_var: tk.StringVar (required constructor field)
- include_zip_var: tk.BooleanVar (required constructor field)
- redact_var: tk.BooleanVar (required constructor field)
- include_hashes_var: tk.BooleanVar (required constructor field)
- include_line_counts_var: tk.BooleanVar (required constructor field)
- include_tree_var: tk.BooleanVar (required constructor field)
- include_index_var: tk.BooleanVar (required constructor field)
- include_contents_var: tk.BooleanVar (required constructor field)
- include_skipped_details_var: tk.BooleanVar (required constructor field)
- include_git_state_var: tk.BooleanVar (required constructor field)
- timestamped_folder_var: tk.BooleanVar (required constructor field)
- open_after_build_var: tk.BooleanVar (required constructor field)
- check_updates_startup_var: tk.BooleanVar (required constructor field)
- auto_install_var: tk.BooleanVar (required constructor field)
- custom_profile_var: tk.StringVar (required constructor field)
- status_text: tk.StringVar (required constructor field)
- last_export_dir: Path | None = None

Edge cases
----------
Rejects nonnumeric, nonfinite, and nonpositive size inputs. Negative skipped-detail limits clamp
  to zero. Loading a custom profile reapplies its values after the profile-change callback.

The selected project folder is not restored from saved export settings. Setting profile_var can
  trigger the Build tab preset-reset trace; custom profile loading compensates by applying
  values afterward. Positive fractional bytes below one truncate to zero and are rejected.

Known limitations
-----------------
The GUI does not expose every ScanSettings field. Rebuilding settings from the selected preset
  can discard hidden custom fields. Unsaved edits are not automatically persisted as last-used
  export settings.

GUI conversion rebuilds settings from a preset; custom extension/exclusion sets and a custom Git
  history limit are not retained by that conversion. Persistence failures may be suppressed by
  storage.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.builders import make_gui_state, build_settings_from_state

    window = tk.Tk()
    state = make_gui_state()
    settings = build_settings_from_state(state)
    print(settings.profile, settings.max_file_bytes)
    window.destroy()
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk

from services.storage import (
    AppPreferences,
    load_preferences,
    save_preferences,
    load_last_settings,
    save_last_settings,
)
from core.constants import (
    DEFAULT_PROFILE,
    EXPORTS_DIRNAME,
    PROFILE_ARCHIVE,
    PROFILE_STANDARD,
    settings_for_profile,
)
from core.builder import create_context
from core.models import (
    BuildResult,
    ScanSettings,
)


@dataclass(slots=True)
class GuiState:
    selected_folder: tk.StringVar
    profile_var: tk.StringVar
    output_dir_var: tk.StringVar
    max_file_mb_var: tk.StringVar
    max_total_mb_var: tk.StringVar
    skipped_limit_var: tk.StringVar
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
    check_updates_startup_var: tk.BooleanVar
    auto_install_var: tk.BooleanVar
    custom_profile_var: tk.StringVar
    status_text: tk.StringVar
    last_export_dir: Path | None = None


def bytes_to_mb_text(value: int) -> str:
    mb_value = value / 1_000_000
    if mb_value.is_integer():
        return str(int(mb_value))
    return str(mb_value).rstrip("0").rstrip(".")


def make_bool_var(value: bool) -> tk.BooleanVar:
    return tk.BooleanVar(value=bool(value))


def wire_preference_autosave(state: GuiState) -> None:
    def persist(*_args) -> None:
        save_preferences(
            AppPreferences(
                open_after_build=state.open_after_build_var.get(),
                check_updates_startup=state.check_updates_startup_var.get(),
                auto_install_updates=state.auto_install_var.get(),
            )
        )
    state.open_after_build_var.trace_add("write", persist)
    state.check_updates_startup_var.trace_add("write", persist)
    state.auto_install_var.trace_add("write", persist)


def make_gui_state() -> GuiState:
    settings = settings_for_profile(DEFAULT_PROFILE)
    preferences = load_preferences()
    remembered_settings = load_last_settings()
    active_settings = remembered_settings or settings
    state = GuiState(
        selected_folder=tk.StringVar(value=""),
        profile_var=tk.StringVar(value=active_settings.profile),
        output_dir_var=tk.StringVar(value=active_settings.output_dir_name or EXPORTS_DIRNAME),
        max_file_mb_var=tk.StringVar(value=bytes_to_mb_text(active_settings.max_file_bytes)),
        max_total_mb_var=tk.StringVar(value=bytes_to_mb_text(active_settings.max_total_bytes)),
        skipped_limit_var=tk.StringVar(value=str(active_settings.skipped_details_limit)),
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
        check_updates_startup_var=tk.BooleanVar(value=preferences.check_updates_startup),
        auto_install_var=tk.BooleanVar(value=preferences.auto_install_updates),
        custom_profile_var=tk.StringVar(value=""),
        status_text=tk.StringVar(value="Select a project folder."),
    )
    wire_preference_autosave(state)
    return state


def profile_description(profile: str) -> str:
    if profile == PROFILE_STANDARD:
        return (
            "standard: quick everyday backup and project overview. "
            "Creates a ZIP snapshot, folder tree, and file index "
            "without hashes, line counts, full file contents, or "
            "skipped-file details."
        )
    if profile == PROFILE_ARCHIVE:
        return (
            "archive (default): maximum preservation mode. Includes "
            "all available export information with larger limits and "
            "enforced source completeness. Best for backups, long-term "
            "preservation, research archives, and full project records."
        )
    return "Unknown profile."


def apply_settings_to_state(state: GuiState, settings: ScanSettings) -> None:
    state.output_dir_var.set(settings.output_dir_name or EXPORTS_DIRNAME)
    state.max_file_mb_var.set(bytes_to_mb_text(settings.max_file_bytes))
    state.max_total_mb_var.set(bytes_to_mb_text(settings.max_total_bytes))
    state.skipped_limit_var.set(str(settings.skipped_details_limit))
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
    settings = settings_for_profile(state.profile_var.get())
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
    return settings


def run_project_build(state: GuiState) -> BuildResult:
    folder = state.selected_folder.get().strip()
    if not folder:
        raise ValueError("Please select a project folder first.")
    settings = build_settings_from_state(state)
    result = create_context(Path(folder), settings=settings)
    state.last_export_dir = result.export_dir
    save_last_settings(settings)
    return result

