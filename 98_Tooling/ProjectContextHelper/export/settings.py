"""
File: export/settings.py

Purpose
-------
Own everything about export settings: the ScanSettings record, the standard and archive
  presets, JSON loading and saving, validation before a build, extension normalization, and
  how many capture threads a build runs (CPU core detection and the 'auto' rule).

Communication / relationships
-----------------------------
Imports app (output and state file names for the default exclusions). Imported by
  export/scan.py (ScanSettings, resolve_workers), export/render.py and export/pipeline.py
  (ScanSettings, validate_settings, settings_for_profile), storage.py (ScanSettings for
  last-used settings and profiles), cli.py (presets, normalize_extension, AUTO_WORKERS,
  MAX_WORKERS), gui/state.py and gui/options_tab.py (presets, core detection, worker
  limits), gui/build_tab.py (the profile list), and gui/extras_tab.py (reserved names).

Settings / parameters
---------------------
Presets differ only in extensions, size limits, which detail sections are on, the skipped-
  detail cap, and required completeness; everything else is shared. Standard: 350000 bytes
  per file, 5000000 total, no hashes/line counts/contents/skipped details, completeness not
  required. Archive (the default): 2000000 per file, 100000000 total, everything on,
  completeness required. Both enable ZIP and redaction, disable Git State, and use
  workers='auto'.

workers is 'auto' or a whole number 1-MAX_WORKERS (32). 'auto' runs one thread per logical
  core the OS reports for this process; an explicit count is clamped to that, so a profile
  saved on a 16-core machine runs 4 threads on a 4-core one. The requested value is what gets
  saved; the resolved count is reported in each export.

DEFAULT_EXCLUDE_DIRS keeps "updates": installs older than v4.0.1 kept self-update downloads and
  full application backups there, and exporting this tool's own folder must not pick them up.

Edge cases
----------
from_jsonable never raises for bad field values: wrong types are dropped and fall back to the
  raw dataclass defaults, booleans are never accepted as integers, integer strings and
  integral floats are converted, and strings like '--5' are dropped. Unknown keys are
  ignored. Settings saved before v4.0.0 have no workers key and load as 'auto'; a number
  saved by v4.0.x (usually the old default 4) is kept as an explicit choice.

validate_settings returns a validated deep copy and raises ValueError for an unsupported
  profile, a nonpositive or non-int size limit, a workers value other than 'auto' or 1-32
  (including True, 2.0, and '4'), or an empty output folder name. Core detection never
  returns less than 1.

Known limitations
-----------------
Raw ScanSettings() is not a preset: its extension and exclusion sets are empty. Use
  settings_for_profile. Validation checks types and ranges, not whether extensions are
  normalized or the output folder is safe (export/pipeline.py checks the folder).

Core counts are logical processors (hyper-threads count individually). On Windows and macOS
  before Python 3.13, the count is machine-wide and ignores CPU affinity.

Examples
--------
Usage from the directory containing run.py:

    from export.settings import ScanSettings, resolve_workers, settings_for_profile

    settings = settings_for_profile("archive")
    assert settings.workers == "auto" and settings.require_complete_source
    restored = ScanSettings.from_jsonable(settings.to_jsonable())
    assert restored == settings
    assert resolve_workers("auto", cores=8) == 8
    assert resolve_workers(16, cores=4) == 4
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any
import os

from app import EXPORTS_DIRNAME, OUTPUT_FILENAMES, STATE_FILENAMES

AUTO_WORKERS = "auto"
MAX_WORKERS = 32

PROFILE_STANDARD = "standard"
PROFILE_ARCHIVE = "archive"
DEFAULT_PROFILE = PROFILE_ARCHIVE
VALID_PROFILES = frozenset({PROFILE_STANDARD, PROFILE_ARCHIVE})

STANDARD_EXTENSIONS = frozenset({
    ".py", ".json", ".csv", ".txt", ".md", ".toml", ".ini", ".cfg",
    ".yaml", ".yml", ".html", ".css", ".js", ".ts", ".tsx", ".jsx",
    ".sql", ".xml", ".bat", ".ps1", ".sh", ".gitignore", ".dockerignore",
})
ARCHIVE_EXTENSIONS = STANDARD_EXTENSIONS | {
    ".rst", ".log", ".env.example", ".sample", ".template", ".lock",
    ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
    ".php", ".swift", ".kt", ".kts", ".r", ".m", ".mm", ".pl", ".lua",
}
DEFAULT_EXCLUDE_DIRS = frozenset({
    ".git", ".venv", "venv", "env", "__pycache__", ".mypy_cache",
    ".pytest_cache", "node_modules", "build", "dist", ".idea",
    ".vscode", "updates", EXPORTS_DIRNAME,
})
DEFAULT_EXCLUDE_FILES = frozenset({
    *OUTPUT_FILENAMES, *STATE_FILENAMES,
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
})
DEFAULT_EXCLUDE_SUFFIXES = frozenset({
    ".pem", ".key", ".crt", ".pfx", ".p12", ".sqlite", ".db", ".exe",
    ".dll", ".so", ".dylib", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".ico", ".pdf", ".zip", ".7z", ".rar",
})

_PRESETS: dict[str, dict[str, Any]] = {
    PROFILE_STANDARD: dict(
        include_extensions=STANDARD_EXTENSIONS, max_file_bytes=350_000, max_total_bytes=5_000_000,
        include_hashes=False, include_line_counts=False, include_file_contents=False,
        include_skipped_details=False, skipped_details_limit=100, require_complete_source=False,
    ),
    PROFILE_ARCHIVE: dict(
        include_extensions=ARCHIVE_EXTENSIONS, max_file_bytes=2_000_000, max_total_bytes=100_000_000,
        include_hashes=True, include_line_counts=True, include_file_contents=True,
        include_skipped_details=True, skipped_details_limit=1000, require_complete_source=True,
    ),
}

_SET_FIELDS = ("include_extensions", "exclude_dirs", "exclude_files", "exclude_suffixes")
_INT_FIELDS = ("max_file_bytes", "max_total_bytes", "skipped_details_limit", "git_state_commit_limit")
_BOOL_FIELDS = (
    "include_snapshot_zip", "redact_sensitive_lines", "include_hashes", "include_line_counts",
    "include_folder_tree", "include_file_index", "include_file_contents", "include_skipped_details",
    "timestamped_export_folder", "require_complete_source", "include_git_state",
)
_STR_FIELDS = ("profile", "output_dir_name")


@dataclass(slots=True)
class ScanSettings:
    profile: str = PROFILE_STANDARD
    output_dir_name: str = EXPORTS_DIRNAME
    include_extensions: set[str] = field(default_factory=set)
    exclude_dirs: set[str] = field(default_factory=set)
    exclude_files: set[str] = field(default_factory=set)
    exclude_suffixes: set[str] = field(default_factory=set)
    max_file_bytes: int = 350_000
    max_total_bytes: int = 5_000_000
    include_snapshot_zip: bool = True
    redact_sensitive_lines: bool = True
    include_hashes: bool = True
    include_line_counts: bool = True
    include_folder_tree: bool = True
    include_file_index: bool = True
    include_file_contents: bool = True
    include_skipped_details: bool = True
    timestamped_export_folder: bool = True
    skipped_details_limit: int = 250
    require_complete_source: bool = False
    include_git_state: bool = False
    git_state_commit_limit: int = 5
    workers: int | str = AUTO_WORKERS

    def to_jsonable(self) -> dict[str, Any]:
        data = asdict(self)
        for name in _SET_FIELDS:
            data[name] = sorted(data[name])
        return data

    @classmethod
    def from_jsonable(cls, data: dict[str, Any]) -> "ScanSettings":
        kept: dict[str, Any] = {}
        for name, value in data.items():
            if name in _SET_FIELDS and isinstance(value, (list, tuple, set)):
                kept[name] = {item for item in value if isinstance(item, str)}
            elif name in _INT_FIELDS and (number := _parse_int(value)) is not None:
                kept[name] = number
            elif name in _BOOL_FIELDS and isinstance(value, bool):
                kept[name] = value
            elif name in _STR_FIELDS and isinstance(value, str):
                kept[name] = value
            elif name == "workers" and (workers := _parse_workers(value)) is not None:
                kept[name] = workers
        return cls(**kept)


def _parse_int(value: Any) -> int | None:
    # bool is an int subclass; a saved true/false is never a valid count or limit.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        digits = text[1:] if text.startswith("-") else text
        if digits.isdigit():
            return int(text)
    return None


def _parse_workers(value: Any) -> int | str | None:
    if isinstance(value, str) and value.strip().lower() == AUTO_WORKERS:
        return AUTO_WORKERS
    return _parse_int(value)


def settings_for_profile(profile: str) -> ScanSettings:
    profile = profile.lower().strip()
    if profile not in _PRESETS:
        raise ValueError(f"Invalid profile: {profile}")
    preset = {name: set(value) if isinstance(value, frozenset) else value for name, value in _PRESETS[profile].items()}
    return ScanSettings(
        profile=profile,
        exclude_dirs=set(DEFAULT_EXCLUDE_DIRS),
        exclude_files=set(DEFAULT_EXCLUDE_FILES),
        exclude_suffixes=set(DEFAULT_EXCLUDE_SUFFIXES),
        include_snapshot_zip=True,
        redact_sensitive_lines=True,
        include_folder_tree=True,
        include_file_index=True,
        timestamped_export_folder=True,
        include_git_state=False,
        git_state_commit_limit=5,
        workers=AUTO_WORKERS,
        **preset,
    )


def validate_settings(settings: ScanSettings) -> ScanSettings:
    settings = deepcopy(settings)
    if settings.profile not in VALID_PROFILES:
        raise ValueError(f"Unsupported profile: {settings.profile!r}.")
    for name in ("max_file_bytes", "max_total_bytes"):
        value = getattr(settings, name)
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer (got {value!r}).")
    workers = settings.workers
    if workers != AUTO_WORKERS and (type(workers) is not int or not 1 <= workers <= MAX_WORKERS):
        raise ValueError(f"workers must be 'auto' or a whole number from 1 to {MAX_WORKERS} (got {workers!r}).")
    if not isinstance(settings.output_dir_name, str) or not settings.output_dir_name.strip():
        raise ValueError("Output folder name cannot be empty.")
    settings.output_dir_name = settings.output_dir_name.strip()
    return settings


def normalize_extension(value: str) -> str:
    value = value.strip().lower()
    if value and not value.startswith("."):
        return f".{value}"
    return value


def detect_cpu_cores() -> int:
    # process_cpu_count (3.13+) and sched_getaffinity (Linux) respect CPU affinity;
    # cpu_count is machine-wide and is the fallback elsewhere, including Windows.
    counter = getattr(os, "process_cpu_count", None)
    if counter is not None:
        count = counter()
    elif hasattr(os, "sched_getaffinity"):
        try:
            count = len(os.sched_getaffinity(0))
        except OSError:
            count = os.cpu_count()
    else:
        count = os.cpu_count()
    return max(1, count or 1)


def worker_limit(cores: int | None = None) -> int:
    return min(cores if cores is not None else detect_cpu_cores(), MAX_WORKERS)


def resolve_workers(requested: int | str, cores: int | None = None) -> int:
    limit = worker_limit(cores)
    if requested == AUTO_WORKERS:
        return limit
    return max(1, min(int(requested), limit))
