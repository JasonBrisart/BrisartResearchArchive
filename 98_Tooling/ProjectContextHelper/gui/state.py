"""
File: gui/state.py

Purpose
-------
Hold the window's shared state (GuiState: the Tk variables behind every control, the build
  runner, the detected CPU core count, and which optional sections are shown) and translate
  between it and ScanSettings in both directions. Every ScanSettings field has a control, so
  build_settings_from_state needs nothing but the window and a saved profile or last-used file
  restores everything. Also converts the window half of a custom profile (open-after-build,
  View choices, project folder) in both directions, owns the list of hideable sections
  (SECTIONS) and the helpers tabs use to show and hide them (bind_visibility,
  optional_section, has_visible_sections), restores the preferences and last-used settings at
  startup, and autosaves the preferences.

Communication / relationships
-----------------------------
Imports application/identity.py (EXPORTS_DIRNAME), export/settings.py (presets, ScanSettings,
  normalize_extension, core detection), gui/jobs.py (JobRunner), and application/storage.py
  (preferences, last-used settings, ProfileWindow). Imported by gui/build_tab.py,
  gui/options_tab.py, gui/extras_tab.py (GuiState, the conversions each needs, the profile
  window helpers, and the visibility helpers), gui/view_tab.py (SECTIONS), and gui/window.py
  (make_gui_state, SECTIONS, has_visible_sections). Running a build lives in gui/build_tab.py,
  the only place that starts one.

Settings / parameters
---------------------
Size fields are decimal MB (1 MB = 1000000 bytes) and convert with rounding, so a saved byte
  count survives a round trip exactly. The Advanced filters boxes hold comma- or
  line-separated names (names_to_text / parse_names): extensions and suffixes are lowercased
  with a leading dot, folder and file names are kept as typed. The CPU Cores selector text is
  "Auto (N cores)", "1 core", or "N cores"; worker_choices lists Auto plus 1 through this
  machine's limit (capped at 32). Open Export Folder After Build and every View checkbox
  autosave to app_settings.json on every change. optional_section puts a section in a
  permanent holder frame so it returns to its original place when shown again, and keeps a
  1-pixel placeholder in the holder while the section is hidden, because Tk does not shrink a
  frame whose last child was removed.

Edge cases
----------
Size fields reject non-numeric, infinite, NaN, and nonpositive values with a labelled
  ValueError; a negative skipped-details or Git history limit counts as 0. An empty extension
  list is rejected (nothing would be exported), and a folder or file name containing a path separator is
  rejected because the scanner compares one entry name at a time. A saved worker count above
  this machine's limit is shown (and next saved) as the limit. Setting profile_var fires the
  Build tab's preset reset, so apply_custom_profile_to_state sets the profile first and then
  reapplies the loaded values. apply_profile_window applies the saved View choices and
  open-after-build, and sets the stored project folder only if it exists on this computer,
  returning a note otherwise. The project folder is never restored at startup.

Known limitations
-----------------
Removing an entry from Excluded files or Excluded folders removes its protection: clearing
  .env from the files list exports it. The built-in presets always restore the default lists.
  A folder or file name that itself contains a comma (possible only through --exclude-dir or a
  hand-edited profile) is shown and read back as two names, because commas separate entries.
  A profile's window half records which sections were hidden by key; sections added by a
  newer release show as visible when an older profile is loaded.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
import re
import tkinter as tk

from application.identity import EXPORTS_DIRNAME
from export.settings import (
    AUTO_WORKERS,
    DEFAULT_PROFILE,
    ScanSettings,
    detect_cpu_cores,
    normalize_extension,
    settings_for_profile,
    worker_limit,
)
from gui.jobs import JobRunner
from application import storage


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
    extensions_var: tk.StringVar
    exclude_dirs_var: tk.StringVar
    exclude_files_var: tk.StringVar
    exclude_suffixes_var: tk.StringVar
    require_complete_var: tk.BooleanVar
    git_limit_var: tk.StringVar
    custom_profile_var: tk.StringVar
    profile_folder_var: tk.BooleanVar
    status_text: tk.StringVar
    last_export_dir: Path | None = None
    jobs: JobRunner | None = None
    history_refresh: Callable[[], None] | None = None
    closing: bool = False
    cpu_cores: int = 1
    section_vars: dict[str, tk.BooleanVar] = field(default_factory=dict)


# Optional parts of the window the View tab can hide: (key, tab, label). Hiding changes
# only what is on screen; every setting behind a hidden section still applies to builds.
SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("build_profile_help", "Build", "Profile description"),
    ("build_outputs", "Build", "List of generated files"),
    ("options_help", "Options", "Option descriptions"),
    ("options_advanced", "Options", "Advanced filters"),
    ("extras_git", "Extras", "Git State"),
    ("extras_performance", "Extras", "Performance (CPU cores)"),
    ("extras_profiles", "Extras", "Custom Profiles"),
    ("extras_history", "Extras", "Recent Exports"),
)


def has_visible_sections(state: GuiState, tab: str) -> bool:
    """True when at least one optional section of the named tab is currently shown."""
    return any(state.section_vars[key].get() for key, section_tab, _label in SECTIONS if section_tab == tab)


def bind_visibility(state: GuiState, key: str, show: Callable[[], None], hide: Callable[[], None]) -> None:
    """Call show or hide now and whenever the section's View checkbox changes."""
    variable = state.section_vars[key]

    def apply(*_args) -> None:
        (show if variable.get() else hide)()

    variable.trace_add("write", apply)
    apply()


def optional_section(state: GuiState, key: str, parent: tk.Widget, **pack_options) -> tk.Frame:
    """
    Return a frame for an optional section. It sits in a permanent holder so it comes back
    in its original place when shown again, and hiding it gives its space back.

    Tk stops managing a frame's size the moment its last child is removed: the frame keeps
    its old height, which would leave an empty gap where the hidden section was (and a
    scrollbar that never goes away). So the holder always keeps one child: the section while
    it is shown, a 1-pixel placeholder while it is hidden. The placeholder is added before the
    section is removed and removed after it is added, so the holder is never empty and adds no
    pixels while the section is visible.
    """
    holder = tk.Frame(parent)
    holder.pack(fill="x")
    section = tk.Frame(holder)
    placeholder = tk.Frame(holder, width=1, height=1)

    def show() -> None:
        section.pack(fill="x", **pack_options)
        placeholder.pack_forget()

    def hide() -> None:
        placeholder.pack(fill="x")
        section.pack_forget()

    bind_visibility(state, key, show, hide)
    return section


def names_to_text(values) -> str:
    """A set of names as the sorted, comma-separated text the Advanced filters boxes show."""
    return ", ".join(sorted(values))


NAME_SEPARATORS = re.compile(r"[,\n]")


def parse_names(text: str, label: str, kind: str) -> set[str]:
    """
    Turn comma- or line-separated text into a set of names. Extensions and suffixes are
    normalized like the command line (lowercase, leading dot); folder and file names are kept
    as typed and must be bare names, because the scanner compares one entry name at a time.
    """
    names: set[str] = set()
    for piece in NAME_SEPARATORS.split(text):
        item = piece.strip()
        if not item:
            continue
        if kind == "extension":
            item = normalize_extension(item)
            if item == ".":
                raise ValueError(f"{label}: '.' is not an extension.")
        elif "/" in item or "\\" in item:
            raise ValueError(f"{label}: '{item}' must be a single name, not a path.")
        names.add(item)
    return names


def bytes_to_mb_text(value: int) -> str:
    mb_value = value / 1_000_000
    if mb_value.is_integer():
        return str(int(mb_value))
    return str(mb_value).rstrip("0").rstrip(".")


def make_bool_var(value: bool) -> tk.BooleanVar:
    return tk.BooleanVar(value=bool(value))


def current_preferences(state: GuiState) -> storage.AppPreferences:
    return storage.AppPreferences(
        open_after_build=state.open_after_build_var.get(),
        hidden_sections=tuple(key for key, variable in state.section_vars.items() if not variable.get()),
    )


def wire_preference_autosave(state: GuiState) -> None:
    def persist(*_args) -> None:
        storage.save_preferences(current_preferences(state))
    state.open_after_build_var.trace_add("write", persist)
    for variable in state.section_vars.values():
        variable.trace_add("write", persist)


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
        extensions_var=tk.StringVar(value=names_to_text(active_settings.include_extensions)),
        exclude_dirs_var=tk.StringVar(value=names_to_text(active_settings.exclude_dirs)),
        exclude_files_var=tk.StringVar(value=names_to_text(active_settings.exclude_files)),
        exclude_suffixes_var=tk.StringVar(value=names_to_text(active_settings.exclude_suffixes)),
        require_complete_var=make_bool_var(active_settings.require_complete_source),
        git_limit_var=tk.StringVar(value=str(active_settings.git_state_commit_limit)),
        custom_profile_var=tk.StringVar(value=""),
        profile_folder_var=tk.BooleanVar(value=True),
        status_text=tk.StringVar(value="Select a project folder."),
        cpu_cores=cpu_cores,
        section_vars={key: tk.BooleanVar(value=key not in preferences.hidden_sections) for key, _tab, _label in SECTIONS},
    )
    state.jobs = JobRunner()
    wire_preference_autosave(state)
    return state


def apply_settings_to_state(state: GuiState, settings: ScanSettings) -> None:
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
    state.extensions_var.set(names_to_text(settings.include_extensions))
    state.exclude_dirs_var.set(names_to_text(settings.exclude_dirs))
    state.exclude_files_var.set(names_to_text(settings.exclude_files))
    state.exclude_suffixes_var.set(names_to_text(settings.exclude_suffixes))
    state.require_complete_var.set(settings.require_complete_source)
    state.git_limit_var.set(str(settings.git_state_commit_limit))


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
        # round, not int: 0.489 * 1_000_000 is 488999.99999999994, which int() would cut to 488999.
        result = round(parsed * 1_000_000)
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
    Every ScanSettings field comes from a control, so this builds the settings from the window
    alone and a saved profile or last-used settings file restores everything.
    """
    extensions = parse_names(state.extensions_var.get(), "Included extensions", "extension")
    if not extensions:
        raise ValueError("Included extensions cannot be empty: nothing would be exported.")
    return ScanSettings(
        profile=state.profile_var.get(),
        output_dir_name=state.output_dir_var.get().strip() or EXPORTS_DIRNAME,
        include_extensions=extensions,
        exclude_dirs=parse_names(state.exclude_dirs_var.get(), "Excluded folders", "name"),
        exclude_files=parse_names(state.exclude_files_var.get(), "Excluded files", "name"),
        exclude_suffixes=parse_names(state.exclude_suffixes_var.get(), "Excluded suffixes", "extension"),
        max_file_bytes=parse_mb_to_bytes(state.max_file_mb_var.get(), "Max File MB"),
        max_total_bytes=parse_mb_to_bytes(state.max_total_mb_var.get(), "Max Total MB"),
        include_snapshot_zip=state.include_zip_var.get(),
        redact_sensitive_lines=state.redact_var.get(),
        include_hashes=state.include_hashes_var.get(),
        include_line_counts=state.include_line_counts_var.get(),
        include_folder_tree=state.include_tree_var.get(),
        include_file_index=state.include_index_var.get(),
        include_file_contents=state.include_contents_var.get(),
        include_skipped_details=state.include_skipped_details_var.get(),
        timestamped_export_folder=state.timestamped_folder_var.get(),
        skipped_details_limit=parse_nonnegative_int(state.skipped_limit_var.get(), "Skipped Details Limit"),
        require_complete_source=state.require_complete_var.get(),
        include_git_state=state.include_git_state_var.get(),
        git_state_commit_limit=parse_nonnegative_int(state.git_limit_var.get(), "Git History Limit"),
        workers=label_to_workers(state.workers_var.get()),
    )


def current_profile_window(state: GuiState, include_folder: bool) -> storage.ProfileWindow:
    """The window half of a profile as the window is now: preferences, and optionally the folder."""
    folder = state.selected_folder.get().strip() if include_folder else ""
    return storage.ProfileWindow(current_preferences(state), folder)


def apply_profile_window(state: GuiState, window: storage.ProfileWindow) -> list[str]:
    """
    Apply a profile's window half. Returns notes for the person loading it: a stored project
    folder that does not exist on this computer is skipped and reported, never half-applied.
    """
    notes: list[str] = []
    state.open_after_build_var.set(window.preferences.open_after_build)
    hidden = set(window.preferences.hidden_sections)
    for key, variable in state.section_vars.items():
        variable.set(key not in hidden)
    if window.project_folder:
        if Path(window.project_folder).is_dir():
            state.selected_folder.set(window.project_folder)
        else:
            notes.append(f"The stored project folder was not found on this computer, so it was left alone: {window.project_folder}")
    return notes
