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
