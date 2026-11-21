"""
File: application/identity.py

Purpose
-------
Hold Project Context Helper's identity (name, version, author, affiliation within Brisart
  Research Archive) and the name of every file and folder the application itself writes:
  export outputs, persisted state files, and the internal .pch- prefix. These names live in
  one leaf module because three owners need the same list: the export pipeline writes the
  outputs, application/storage.py writes the state files, and the scanner must recognise all
  of them so the tool never exports its own files.

Communication / relationships
-----------------------------
Imports nothing, from the application or the standard library. Imported by cli.py (version
  banner), export/settings.py (default exclusions), export/render.py (attribution and
  output names), export/pipeline.py (output names), export/scan.py (internal prefix),
  application/storage.py (state file names), gui/state.py (default output folder), and
  gui/window.py and gui/about_tab.py (attribution). It is a leaf so the engine can import
  it without loading application/storage.py.

Settings / parameters
---------------------
APP_VERSION is 4.2.0. STATE_VENDOR_DIRNAME and STATE_APP_DIRNAME name the per-user folder
  where the state files live (for example %APPDATA%\\Brisart Research Archive\\Project Context Helper); the vendor
  folder is shared with other Brisart Research Archive tools. AUTHOR and AFFILIATION are written into every export and shown in the
  GUI. EXPORTS_DIRNAME is the default output folder inside the selected project. Any file or
  folder whose name starts with INTERNAL_NAME_PREFIX is skipped by the scanner.

Edge cases
----------
Renaming an output or state file, or either state folder name, here changes where existing
  users' data is looked for; state written under an old name would be silently ignored. The
  current file names are unchanged since v3.x for that reason. The state file names stay in
  the scanner's default exclusions even though the files no longer sit beside run.py,
  because copies left there by an older release must still never be exported.

Known limitations
-----------------
INTERNAL_NAME_PREFIX is a naming convention, not a security boundary: a project file that
  happens to start with .pch- is never exported.

Examples
--------
Usage from the directory containing run.py:

    from application.identity import APP_NAME, APP_VERSION, CONTEXT_FILENAME
    print(f"{APP_NAME} v{APP_VERSION} writes {CONTEXT_FILENAME}")
"""

APP_NAME = "Project Context Helper"
APP_VERSION = "4.2.0"
AUTHOR = "Jason Brisart"
AFFILIATION = "Brisart Research Archive"

# Export outputs, written into <project>/<EXPORTS_DIRNAME>/project_context_<timestamp>/.
EXPORTS_DIRNAME = "PROJECT_CONTEXT_EXPORTS"
CONTEXT_FILENAME = "PROJECT_CONTEXT.md"
MANIFEST_FILENAME = "PROJECT_MANIFEST.json"
SUMMARY_FILENAME = "PROJECT_SUMMARY.txt"
SETTINGS_FILENAME = "PROJECT_CONTEXT_SETTINGS.json"
SNAPSHOT_FILENAME = "PROJECT_SNAPSHOT.zip"
OUTPUT_FILENAMES = (CONTEXT_FILENAME, MANIFEST_FILENAME, SUMMARY_FILENAME, SETTINGS_FILENAME, SNAPSHOT_FILENAME)

# Persisted state, written beside run.py (or the executable, or PCH_STATE_DIR).
# Per-user folder for the state files: <config root>/<vendor>/<app>. The vendor folder is
# shared with other Brisart Research Archive tools, so it must not change.
STATE_VENDOR_DIRNAME = "Brisart Research Archive"
STATE_APP_DIRNAME = "Project Context Helper"
APP_SETTINGS_FILENAME = "app_settings.json"
LAST_SETTINGS_FILENAME = "last_export_settings.json"
CUSTOM_PROFILES_FILENAME = "custom_profiles.json"
BUILD_HISTORY_FILENAME = "build_history.json"
STATE_FILENAMES = (APP_SETTINGS_FILENAME, LAST_SETTINGS_FILENAME, CUSTOM_PROFILES_FILENAME, BUILD_HISTORY_FILENAME)

# Prefix for this tool's staging folders, temp files, and lock file.
INTERNAL_NAME_PREFIX = ".pch-"
