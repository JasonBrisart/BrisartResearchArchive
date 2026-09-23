# Architecture

Project Context Helper is organized as one entry point plus four
purpose-built packages.

```
ProjectContextHelper/
├── run.py                  <- the only file you ever run directly
├── docs/                     README.md, ARCHITECTURE.md, CHANGELOG.md
├── core/                    the scan + export engine
│   ├── constants.py           app metadata, profiles, default rules
│   ├── models.py                ScanSettings (+ to/from_jsonable), etc.
│   ├── scanner.py                walks a project folder, decides what's included
│   ├── git_state.py               pure-Python .git reader (Extras-only feature)
│   ├── exporters.py                renders PROJECT_CONTEXT.md / manifest / summary
│   ├── builder.py                   orchestrates one full build (create_context)
│   └── utils.py                      hashing, redaction, timestamps, language hints
├── services/                 stateful support services
│   ├── storage.py               ALL settings/profile/history persistence (single file)
│   └── updater.py                self-update check / download / install
├── cli/                      command-line interface
│   └── cli.py                    argparse wiring, calls core.builder directly
└── gui/                      tkinter desktop interface
    ├── main_gui.py               4-tab notebook shell (Build/Options/Extras/About)
    ├── builders.py                shared GuiState + settings <-> ScanSettings glue
    ├── scroll_frame.py             reusable scrollable-container helper
    ├── build_tab.py                Build tab
    ├── options_tab.py               Options tab
    ├── extras_tab.py                 Extras tab (toggles + Custom Profiles)
    ├── profiles_section.py            Custom Profiles Save/Load/Delete controls
    ├── about_tab.py                    About tab (info, history, updates)
    └── dialogs.py                       shared message-box helpers
```

## Storage consolidation: one file for all persisted state

**`services/storage.py` is the single, exclusive place every kind of
persisted application state (other than a build's own output files)
is read and written.** Nothing else in this app performs direct file
I/O against `app_settings.json`, `last_export_settings.json`,
`custom_profiles.json`, or `build_history.json`.

Prior to this consolidation, this same functionality was spread
across four separate modules:

| Old module | Replaced section in storage.py | File |
|---|---|---|
| `services/app_settings.py` | App Preferences | `app_settings.json` |
| `services/settings_memory.py` | Last Used Settings | `last_export_settings.json` |
| `services/profile_manager.py` | Custom Profiles | `custom_profiles.json` |
| `services/history.py` | Build History | `build_history.json` |

Each of those four modules independently re-implemented the same
`application_dir()` resolution helper (frozen-executable vs.
source-mode folder resolution). That duplication is exactly the kind
of thing that lets small inconsistencies creep in silently over
time — one copy gets updated or fixed, another doesn't. `storage.py`
has exactly one `application_dir()` implementation, used by every
section in the file.

**Every other module that needs any of this state imports directly
from `services.storage`:**
- `core/builder.py` imports `HistoryEntry`, `append_history_entry`
- `cli/cli.py` imports the whole module as `storage` and calls
  `storage.load_last_settings()`, `storage.save_profile()`, etc.
- `gui/builders.py` imports `AppPreferences`, `load_preferences`,
  `save_preferences`, `load_last_settings`, `save_last_settings`
- `gui/profiles_section.py` imports the whole module as `storage`
- `gui/about_tab.py` imports `HistoryEntry`, `application_dir`,
  `clear_history`, `recent_entries`

`services/updater.py` (a separate concern — downloading and applying
application updates, not user settings) now also imports
`application_dir` directly from `services.storage` rather than
maintaining its own duplicate copy, so there is exactly one
implementation of "where does this app's data live" in the entire
codebase.

## Settings persistence: three distinct mechanisms, one storage layer

1. **Built-in profile defaults** (`core/constants.py`) — `standard`
   and `archive`.
2. **Last-used settings, always-on** (`services/storage.py`, section 3)
   — GUI-only, no toggle, no way to disable. The CLI's
   `--remember-settings` / `--use-last-settings` flags read/write the
   same file but remain explicit opt-in for scripting determinism.
3. **Custom Profiles** (`services/storage.py`, section 4) — named,
   multi-slot, always explicit Save/Load/Delete.

`load_profile()`, `delete_profile()`, and `profile_exists()` all
strip leading/trailing whitespace from the requested name before
looking it up, matching `save_profile()`'s existing behavior of
always storing a stripped name.

## Why this split

**`core/` never imports from `services/`, `cli/`, or `gui/`.**

**`services/` depends only on `core/`, never on `cli/` or `gui/`.**

**`cli/` and `gui/` are two interchangeable frontends** over the same
`core.builder.create_context()`, differing intentionally only in
whether "last used settings" persist automatically (GUI: yes, always)
or only on request (CLI: opt-in flags only).

## GUI: four tabs

1. **Build** 2. **Options** 3. **Extras** 4. **About**

Both Options and Extras wrap their content in a scrollable area
(`gui/scroll_frame.py`).

## Core vs. Extras vs. Custom Profiles

1. **Core output toggles** (Options tab).
2. **Extras (optional)** (Extras tab, top section) — currently just
   `include_git_state`.
3. **Custom Profiles** (Extras tab, bottom section) — named,
   multi-slot, explicit Save/Load/Delete.

## Shared settings serialization

`core/models.py`'s `ScanSettings.to_jsonable()` /
`ScanSettings.from_jsonable()` are the single shared conversion path
used by every section of `services/storage.py` that persists a
`ScanSettings` (Last Used Settings and Custom Profiles both use it).

## Import convention

`run.py` inserts the project root onto `sys.path` before importing
anything else.

## App-data file location

`services/storage.py`'s single `application_dir()` (also reused by
`services/updater.py`) resolves to the project root (the folder
containing `run.py`) in source mode, or the folder containing the
compiled `.exe` when frozen.
