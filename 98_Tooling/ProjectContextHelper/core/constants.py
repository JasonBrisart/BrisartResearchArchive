"""
File: core/constants.py

Purpose
-------
Centralize application metadata, output filenames, exclusion rules, and the standard/archive
  presets for Project Context Helper in Brisart Research Archive.

Implemented responsibilities:
- apply_common_defaults: Replace exclusion sets with fresh copies of shared defaults and set the
  Git history limit and capture worker count; mutate and return the supplied settings object.
- apply_standard_preset: Mutate the settings to standard extension/size limits and a compact
  output selection, with ZIP/redaction enabled and completeness/Git disabled.
- apply_archive_preset: Mutate the settings to expanded extensions and larger limits, enable
  full text/hash/line/skip output and required eligible-source completeness, and leave Git
  disabled.
- settings_for_profile: Normalize the profile string, reject unknown names, create ScanSettings,
  apply common defaults, and apply the matching built-in preset.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.models: ScanSettings.

Consumers in the supplied source:
- cli/cli.py imports APP_NAME, APP_VERSION, DEFAULT_PROFILE, VALID_PROFILES,
  settings_for_profile.
- core/builder.py imports CONTEXT_FILENAME, DEFAULT_PROFILE, INTERNAL_NAME_PREFIX,
  MANIFEST_FILENAME, MAX_WORKERS, SETTINGS_FILENAME, SNAPSHOT_FILENAME, SUMMARY_FILENAME,
  VALID_PROFILES, settings_for_profile.
- core/exporters.py imports AFFILIATION, APP_NAME, APP_VERSION, AUTHOR.
- gui/about_tab.py imports AFFILIATION, APP_NAME, APP_VERSION, AUTHOR.
- core/scanner.py imports INTERNAL_NAME_PREFIX.
- gui/build_tab.py imports VALID_PROFILES.
- gui/builders.py imports DEFAULT_PROFILE, EXPORTS_DIRNAME, PROFILE_ARCHIVE, PROFILE_STANDARD,
  settings_for_profile.
- gui/main_gui.py imports AFFILIATION, APP_NAME, APP_VERSION, AUTHOR.
- gui/profiles_section.py imports PROFILE_ARCHIVE, PROFILE_STANDARD.
- services/storage.py imports APP_SETTINGS_FILENAME, BUILD_HISTORY_FILENAME,
  CUSTOM_PROFILES_FILENAME, INTERNAL_NAME_PREFIX, LAST_SETTINGS_FILENAME, MAX_HISTORY_ENTRIES,
  PROFILE_ARCHIVE, PROFILE_STANDARD.
- services/updater.py imports APP_NAME, APP_VERSION, EXPORTS_DIRNAME, RELEASE_TAG_PREFIX,
  RELEASES_LIST_URL, RELEASES_URL, STAGED_EXE_FILENAME.

Settings / parameters
---------------------
APP_VERSION is 4.0.0. The interface default is archive. Standard limits are 350000/5000000
  bytes; archive limits are 2000000/100000000 bytes. Both presets enable redaction and ZIP
  creation and disable Git State. Both presets capture with DEFAULT_WORKERS (4) threads;
  validated worker counts range from 1 to MAX_WORKERS (32).

Function signatures (nested callbacks are scoped to their enclosing function):
- apply_common_defaults(settings: ScanSettings) -> ScanSettings
- apply_standard_preset(settings: ScanSettings) -> ScanSettings
- apply_archive_preset(settings: ScanSettings) -> ScanSettings
- settings_for_profile(profile: str) -> ScanSettings

Module constants and expressions:
- APP_NAME = 'Project Context Helper'
- APP_VERSION = '4.0.0'
- AUTHOR = 'Jason Brisart'
- AFFILIATION = 'Brisart Research Archive'
- RELEASES_URL = 'https://github.com/JasonBrisart/BrisartDevTools/releases'
- RELEASES_LIST_URL = 'https://api.github.com/repos/JasonBrisart/BrisartDevTools/releases'
- RELEASE_TAG_PREFIX = 'project-context-helper-v'
- EXPORTS_DIRNAME = 'PROJECT_CONTEXT_EXPORTS'
- CONTEXT_FILENAME = 'PROJECT_CONTEXT.md'
- MANIFEST_FILENAME = 'PROJECT_MANIFEST.json'
- SUMMARY_FILENAME = 'PROJECT_SUMMARY.txt'
- SNAPSHOT_FILENAME = 'PROJECT_SNAPSHOT.zip'
- SETTINGS_FILENAME = 'PROJECT_CONTEXT_SETTINGS.json'
- BUILD_HISTORY_FILENAME = 'build_history.json'
- MAX_HISTORY_ENTRIES = 50
- APP_SETTINGS_FILENAME = 'app_settings.json'
- LAST_SETTINGS_FILENAME = 'last_export_settings.json'
- CUSTOM_PROFILES_FILENAME = 'custom_profiles.json'
- STAGED_EXE_FILENAME = 'staged_update.exe'
- DEFAULT_GIT_STATE_COMMIT_LIMIT = 5
- DEFAULT_WORKERS = 4
- MAX_WORKERS = 32
- INTERNAL_NAME_PREFIX = '.pch-'
- PROFILE_STANDARD = 'standard'
- PROFILE_ARCHIVE = 'archive'
- DEFAULT_PROFILE = PROFILE_ARCHIVE
- VALID_PROFILES = {PROFILE_STANDARD, PROFILE_ARCHIVE}
- DEFAULT_EXTENSIONS = {'.py', '.json', '.csv', '.txt', '.md', '.toml', '.ini', '.cfg', '.yaml',
  '.yml', '.html', '.css', '.js', '.ts', '.tsx', '.jsx', '.sql', '.xml', '.bat', '.ps1', '.sh',
  '.gitignore', '.dockerignore'}
- ARCHIVE_EXTENSIONS = DEFAULT_EXTENSIONS | {'.rst', '.log', '.env.example', '.sample',
  '.template', '.lock', '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.go', '.rs', '.rb', '.php',
  '.swift', '.kt', '.kts', '.r', '.m', '.mm', '.pl', '.lua'}
- DEFAULT_EXCLUDE_DIRS = {'.git', '.venv', 'venv', 'env', '__pycache__', '.mypy_cache',
  '.pytest_cache', 'node_modules', 'build', 'dist', '.idea', '.vscode', 'updates',
  EXPORTS_DIRNAME}
- DEFAULT_EXCLUDE_FILES = {CONTEXT_FILENAME, MANIFEST_FILENAME, SUMMARY_FILENAME,
  SNAPSHOT_FILENAME, SETTINGS_FILENAME, BUILD_HISTORY_FILENAME, APP_SETTINGS_FILENAME,
  LAST_SETTINGS_FILENAME, CUSTOM_PROFILES_FILENAME, '.env', '.env.local', '.env.development',
  '.env.production', '.env.test'}
- DEFAULT_EXCLUDE_SUFFIXES = {'.pem', '.key', '.crt', '.pfx', '.p12', '.sqlite', '.db', '.exe',
  '.dll', '.so', '.dylib', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.pdf', '.zip',
  '.7z', '.rar'}
- DEFAULT_MAX_FILE_BYTES = 350000
- DEFAULT_MAX_TOTAL_BYTES = 5000000
- ARCHIVE_MAX_FILE_BYTES = 2000000
- ARCHIVE_MAX_TOTAL_BYTES = 100000000
- STANDARD_SKIPPED_DETAILS_LIMIT = 100
- ARCHIVE_SKIPPED_DETAILS_LIMIT = 1000

Edge cases
----------
Profile names are stripped and lowercased; unsupported names raise ValueError. Preset functions
  mutate the supplied ScanSettings.

Every preset receives fresh set copies rather than sharing the constant sets.
  apply_standard_preset/apply_archive_preset do not change settings.profile themselves;
  settings_for_profile sets it when constructing settings.

Known limitations
-----------------
AUTHOR and AFFILIATION are the attribution shown in the GUI and written into every export;
  v4.0.0 removed the GitHub repository link from that attribution. The RELEASES_* constants are
  used only by the legacy updater (services/updater.py) and still point to the BrisartDevTools
  GitHub releases; they are not shown as attribution.

Changing AUTHOR or AFFILIATION changes generated export metadata; changing release constants
  changes updater behavior. INTERNAL_NAME_PREFIX is a naming convention, not a security
  boundary: any project file whose name starts with it is skipped by the scanner.

Examples
--------
Usage from the directory containing run.py:

    from core.constants import settings_for_profile

    settings = settings_for_profile("archive")
    assert settings.max_file_bytes == 2000000
    assert settings.require_complete_source is True
    assert settings.include_git_state is False
    assert settings.workers == 4
"""

from core.models import ScanSettings

APP_NAME = "Project Context Helper"
APP_VERSION = "4.0.1"
AUTHOR = "Jason Brisart"
AFFILIATION = "Brisart Research Archive"

# Legacy updater endpoints only (services/updater.py); never shown as attribution.
RELEASES_URL = "https://github.com/JasonBrisart/BrisartDevTools/releases"
RELEASES_LIST_URL = (
    "https://api.github.com/repos/"
    "JasonBrisart/BrisartDevTools/releases"
)
RELEASE_TAG_PREFIX = "project-context-helper-v"

EXPORTS_DIRNAME = "PROJECT_CONTEXT_EXPORTS"
CONTEXT_FILENAME = "PROJECT_CONTEXT.md"
MANIFEST_FILENAME = "PROJECT_MANIFEST.json"
SUMMARY_FILENAME = "PROJECT_SUMMARY.txt"
SNAPSHOT_FILENAME = "PROJECT_SNAPSHOT.zip"
SETTINGS_FILENAME = "PROJECT_CONTEXT_SETTINGS.json"
BUILD_HISTORY_FILENAME = "build_history.json"
MAX_HISTORY_ENTRIES = 50
APP_SETTINGS_FILENAME = "app_settings.json"
LAST_SETTINGS_FILENAME = "last_export_settings.json"
CUSTOM_PROFILES_FILENAME = "custom_profiles.json"
STAGED_EXE_FILENAME = "staged_update.exe"

DEFAULT_GIT_STATE_COMMIT_LIMIT = 5
DEFAULT_WORKERS = 4
MAX_WORKERS = 32

# Prefix for this tool's own hidden staging folders and state temp/lock files.
INTERNAL_NAME_PREFIX = ".pch-"

PROFILE_STANDARD = "standard"
PROFILE_ARCHIVE = "archive"
DEFAULT_PROFILE = PROFILE_ARCHIVE
VALID_PROFILES = {
    PROFILE_STANDARD,
    PROFILE_ARCHIVE,
}

DEFAULT_EXTENSIONS = {
    ".py", ".json", ".csv", ".txt", ".md", ".toml", ".ini", ".cfg",
    ".yaml", ".yml", ".html", ".css", ".js", ".ts", ".tsx", ".jsx",
    ".sql", ".xml", ".bat", ".ps1", ".sh", ".gitignore", ".dockerignore",
}
ARCHIVE_EXTENSIONS = DEFAULT_EXTENSIONS | {
    ".rst", ".log", ".env.example", ".sample", ".template", ".lock",
    ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
    ".php", ".swift", ".kt", ".kts", ".r", ".m", ".mm", ".pl", ".lua",
}
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", ".mypy_cache",
    ".pytest_cache", "node_modules", "build", "dist", ".idea",
    ".vscode", "updates", EXPORTS_DIRNAME,
}
DEFAULT_EXCLUDE_FILES = {
    CONTEXT_FILENAME, MANIFEST_FILENAME, SUMMARY_FILENAME,
    SNAPSHOT_FILENAME, SETTINGS_FILENAME, BUILD_HISTORY_FILENAME,
    APP_SETTINGS_FILENAME, LAST_SETTINGS_FILENAME, CUSTOM_PROFILES_FILENAME,
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
}
DEFAULT_EXCLUDE_SUFFIXES = {
    ".pem", ".key", ".crt", ".pfx", ".p12", ".sqlite", ".db", ".exe",
    ".dll", ".so", ".dylib", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".ico", ".pdf", ".zip", ".7z", ".rar",
}

DEFAULT_MAX_FILE_BYTES = 350_000
DEFAULT_MAX_TOTAL_BYTES = 5_000_000
ARCHIVE_MAX_FILE_BYTES = 2_000_000
ARCHIVE_MAX_TOTAL_BYTES = 100_000_000
STANDARD_SKIPPED_DETAILS_LIMIT = 100
ARCHIVE_SKIPPED_DETAILS_LIMIT = 1000


def apply_common_defaults(settings: ScanSettings) -> ScanSettings:
    settings.exclude_dirs = set(DEFAULT_EXCLUDE_DIRS)
    settings.exclude_files = set(DEFAULT_EXCLUDE_FILES)
    settings.exclude_suffixes = set(DEFAULT_EXCLUDE_SUFFIXES)
    settings.git_state_commit_limit = DEFAULT_GIT_STATE_COMMIT_LIMIT
    settings.workers = DEFAULT_WORKERS
    return settings


def apply_standard_preset(settings: ScanSettings) -> ScanSettings:
    settings.include_extensions = set(DEFAULT_EXTENSIONS)
    settings.max_file_bytes = DEFAULT_MAX_FILE_BYTES
    settings.max_total_bytes = DEFAULT_MAX_TOTAL_BYTES
    settings.include_snapshot_zip = True
    settings.redact_sensitive_lines = True
    settings.include_hashes = False
    settings.include_line_counts = False
    settings.include_folder_tree = True
    settings.include_file_index = True
    settings.include_file_contents = False
    settings.include_skipped_details = False
    settings.timestamped_export_folder = True
    settings.skipped_details_limit = STANDARD_SKIPPED_DETAILS_LIMIT
    settings.require_complete_source = False
    settings.include_git_state = False
    return settings


def apply_archive_preset(settings: ScanSettings) -> ScanSettings:
    settings.include_extensions = set(ARCHIVE_EXTENSIONS)
    settings.max_file_bytes = ARCHIVE_MAX_FILE_BYTES
    settings.max_total_bytes = ARCHIVE_MAX_TOTAL_BYTES
    settings.include_snapshot_zip = True
    settings.redact_sensitive_lines = True
    settings.include_hashes = True
    settings.include_line_counts = True
    settings.include_folder_tree = True
    settings.include_file_index = True
    settings.include_file_contents = True
    settings.include_skipped_details = True
    settings.timestamped_export_folder = True
    settings.skipped_details_limit = ARCHIVE_SKIPPED_DETAILS_LIMIT
    settings.require_complete_source = True
    settings.include_git_state = False
    return settings


def settings_for_profile(profile: str) -> ScanSettings:
    profile = profile.lower().strip()
    if profile not in VALID_PROFILES:
        raise ValueError(f"Invalid profile: {profile}")
    settings = ScanSettings(profile=profile)
    settings = apply_common_defaults(settings)
    if profile == PROFILE_STANDARD:
        return apply_standard_preset(settings)
    if profile == PROFILE_ARCHIVE:
        return apply_archive_preset(settings)
    raise ValueError(f"Invalid profile: {profile}")

