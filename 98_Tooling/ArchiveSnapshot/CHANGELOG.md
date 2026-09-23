# Changelog

All notable changes to **ArchiveSnapshot** are documented in this file.

## [2.1.2] - 2026-08-08

Change report honesty. The Compare feature now discloses when a diff was
produced without hashes, so a change report never overstates its own
confidence. Additive and fully backward compatible — the snapshot and
manifest formats are unchanged, and existing snapshots remain readable,
comparable, and verifiable with no migration step.

### Added
- `engine/change_report.py` now records whether both compared snapshots
  carried SHA256 hashes:
  - A new `manifest_has_hashes()` helper reads each manifest's
    `include_hashes` setting, falling back to checking whether the
    included files actually carry `sha256` values. An empty snapshot is
    treated as hashed, since nothing could be silently missed.
  - `compare_manifests()` adds a `hash_comparison` flag to its result
    (True only when both snapshots were hashed).
  - `build_diff_markdown()` prints a `Comparison method` line in every
    report (`sha256 + size` or `size only`), and a WARNING banner when a
    diff falls back to size-only detection — the case where an edit that
    leaves a file's size unchanged can go undetected.

### Notes
- No behavior change for hashed snapshots (the default): reports gain the
  new `Comparison method` line but the detected added/removed/modified
  sets are identical to before.
- All existing callers keep working — `compare_manifests()` only gains a
  new dictionary key; nothing was removed or renamed.

## [2.1.1] - 2026-08-08

Internal naming cleanup. No behavior, storage format, or public CLI/GUI
change — existing snapshots remain fully readable, comparable, and
verifiable with no migration step.

### Changed
- Renamed the module `engine/timeline_index.py` to `engine/snapshot_index.py`
  so the file name matches what it actually manages (the ArchiveSnapshot
  store, not a generic "timeline").
- Renamed the `TimelineSnapshot` dataclass to `StoredSnapshot`.
- Renamed the function `write_timeline_index()` to `write_store_index()`.
- Updated all importers to the new names: `engine/__init__.py`,
  `engine/retention.py`, `engine/snapshot_builder.py`, and the UI modules
  `ui/app.py`, `ui/calendar_tab.py`, `ui/comparison_tab.py`,
  `ui/verification_tab.py`.
- Corrected stale docstrings in `engine/retention.py` and
  `engine/__init__.py` that still referred to `ARCHIVE_TIMELINE`; they now
  reference the `ARCHIVE_SNAPSHOT` store.

### Removed
- Removed the unused `store_dir_name` field from `ArchiveSettings`. It was
  never read by `create_snapshot`, which resolves the store path from the
  `STORE_DIRNAME` constant instead, so the field was configurable in name
  only.

## [2.1.0] - 2026-08-08

### Added
- Snapshot retention. A new `engine/retention.py` module and a `prune`
  subcommand (`python main.py prune <folder>`) remove old snapshots
  according to a retention policy so the store no longer grows without
  bound.
  - Two additive rules: `--keep-last N` (keep the N most recent snapshots)
    and `--keep-within-days N` (keep any snapshot newer than N days). A
    snapshot survives if it satisfies either rule.
  - Safe by default: `prune` performs a dry run and prints a plan; nothing
    is deleted unless `--apply` is passed.
  - Fail-safe: with both rules disabled, nothing is ever removed.
  - Undateable snapshots are kept, never deleted.
  - After an applied prune, the store index is rewritten to reflect only
    the surviving snapshots.

### Changed
- Renamed the on-disk snapshot store from `ARCHIVE_TIMELINE/` to
  `ARCHIVE_SNAPSHOT/`, and its index/log files from `TIMELINE_INDEX.json`
  and `TIMELINE_LOG.md` to `ARCHIVE_SNAPSHOT_INDEX.json` and
  `ARCHIVE_SNAPSHOT_LOG.md`, so the store is named after the program
  itself. The README store-layout diagram was updated to match.

## [2.0.0] - 2026-08

### Changed
- Full architectural rebuild into a layered package:
  - `engine/` holds all core logic and never imports from `ui/` or
    `automation/`.
  - `ui/` is split into one module per tab (calendar, snapshot, compare,
    verify, settings, about) plus shared path actions.
  - `automation/` provides a headless daily snapshot runner on the same
    engine as the GUI and CLI.
- Unified entry points into a single `main.py` with `snapshot`, `daily`,
  and GUI modes.

### Removed
- Retired the legacy single-file `ArchiveSnapshot.py` (v1.0.0) and the
  standalone `DailyArchiveBackup.py` script; their functionality now lives
  in the engine and the daily runner.
