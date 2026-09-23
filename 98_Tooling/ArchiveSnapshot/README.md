# ArchiveSnapshot

ArchiveSnapshot is a local-first, calendar-based archival snapshot tool for
BrisartPreservationTools. It creates dated preservation snapshots of
important digital folders so future users can understand:

- what existed
- when it existed
- how it was organized
- what changed over time
- whether preserved files can be verified

ArchiveSnapshot is not generic backup software. It is designed for
archival context preservation.

## Core Idea

A backup answers:

> Can I restore the files?

ArchiveSnapshot answers:

> What existed here on this date?

---

## Architecture

```text
ArchiveSnapshot/
├── main.py                          # single entry point (GUI / CLI / daily)
├── README.md
├── engine/                          # core logic — no GUI, no CLI dependency
│   ├── __init__.py                    # public API re-exports
│   ├── app_info.py                    # app metadata + shared filenames
│   ├── settings.py                    # ArchiveSettings, AppSettings, records
│   ├── folder_scanner.py              # scanning, exclusion rules, folder tree
│   ├── snapshot_writer.py             # writes summary/manifest/hashes/zip
│   ├── change_report.py               # compares two snapshots
│   ├── integrity_check.py             # verifies a snapshot against source
│   ├── timeline_index.py              # discovers/indexes snapshots by date
│   ├── snapshot_builder.py            # orchestrates one full snapshot
│   └── project_context_import.py      # imports a Project Context Helper bundle
├── automation/                      # headless daily automation, no GUI required
│   ├── __init__.py
│   └── daily_snapshot_runner.py       # config-driven daily snapshot jobs
└── ui/                               # presentation layer — one module per tab
    ├── __init__.py                    # public API re-exports (run_gui)
    ├── app.py                         # main window + tab coordination
    ├── app_settings.py                # GUI settings load/save
    ├── path_actions.py                # shared folder picker + file/folder opening
    ├── calendar_tab.py                # Calendar tab
    ├── snapshot_tab.py                # Create Snapshot tab
    ├── comparison_tab.py              # Compare tab
    ├── verification_tab.py            # Verify tab
    ├── settings_tab.py                # Settings tab
    └── about_tab.py                   # About tab
```

**Design rule:** `engine/` never imports from `ui/` or `automation/`.
Both `ui/` and `automation/` call into `engine/` — they never duplicate
its logic. This is what guarantees a snapshot created from the calendar,
from the command line, or from an unattended daily job all look
identical on disk.

### File Reference

| File | Responsibility |
| --- | --- |
| [main.py](main.py) | Single CLI/GUI/daily entry point |
| [engine/app_info.py](engine/app_info.py) | App metadata, shared filenames |
| [engine/settings.py](engine/settings.py) | Settings + result dataclasses |
| [engine/folder_scanner.py](engine/folder_scanner.py) | Folder walk, exclusions, hashing |
| [engine/snapshot_writer.py](engine/snapshot_writer.py) | Summary/manifest/hashes/ZIP output |
| [engine/change_report.py](engine/change_report.py) | Snapshot-to-snapshot diff |
| [engine/integrity_check.py](engine/integrity_check.py) | Snapshot-vs-source verification |
| [engine/timeline_index.py](engine/timeline_index.py) | Snapshot discovery + indexing |
| [engine/snapshot_builder.py](engine/snapshot_builder.py) | Orchestrates one snapshot |
| [engine/project_context_import.py](engine/project_context_import.py) | Project Context Helper import |
| [automation/daily_snapshot_runner.py](automation/daily_snapshot_runner.py) | Headless daily snapshot jobs |
| [ui/app.py](ui/app.py) | Main window + tab coordination |
| [ui/app_settings.py](ui/app_settings.py) | GUI settings load/save |
| [ui/path_actions.py](ui/path_actions.py) | Shared folder picker + file/folder opening |
| [ui/calendar_tab.py](ui/calendar_tab.py) | Calendar tab |
| [ui/snapshot_tab.py](ui/snapshot_tab.py) | Create Snapshot tab |
| [ui/comparison_tab.py](ui/comparison_tab.py) | Compare tab |
| [ui/verification_tab.py](ui/verification_tab.py) | Verify tab |
| [ui/settings_tab.py](ui/settings_tab.py) | Settings tab |
| [ui/about_tab.py](ui/about_tab.py) | About tab |

### Generated Outputs

Each dated snapshot may contain:

- `ARCHIVE_SUMMARY.md` — human-readable overview
- `ARCHIVE_MANIFEST.json` — machine-readable file index, hashes, and settings
- `HASHES.sha256` — SHA256 checksums for every included file
- `FOLDER_TREE.txt` — a readable tree of what was captured
- `ARCHIVE_SETTINGS.json` — the exact settings used for this snapshot
- `ARCHIVE_FILES.zip` — a ZIP of the generated records plus every included file
- `CHANGES_SINCE_PREVIOUS.md` — diff against the previous snapshot, if one exists
- `PROJECT_CONTEXT_HELPER/` — an attached Project Context Helper bundle, if one was provided

### Store Layout

Snapshots are stored in a date-based structure inside the archived folder,
under a store folder named after the program itself:

```text
<Archived Folder>/
└── ARCHIVE_SNAPSHOT/
    ├── 2026/
    │   └── 07/
    │       ├── 2026-07-12_064500/
    │       └── 2026-07-13_020000/
    ├── ARCHIVE_SNAPSHOT_INDEX.json
    └── ARCHIVE_SNAPSHOT_LOG.md
```

### Project Context Helper Import

ArchiveSnapshot does not generate Project Context Helper exports — it
only imports an already-created bundle. To attach one to a snapshot:

1. Run Project Context Helper on the project you want documented.
2. Copy `PROJECT_CONTEXT.md`, `PROJECT_SUMMARY.txt`,
   `PROJECT_CONTEXT_SETTINGS.json`, and `PROJECT_MANIFEST.json` into:
   `<Archive Folder>/SNAPSHOT_ACTIVE/PROJECT_CONTEXT_HELPER/`
3. Create a snapshot as usual (GUI, CLI, or daily job). The bundle is
   copied into the dated snapshot folder and indexed in
   `PROJECT_CONTEXT_INDEX.json`.

## Usage

### GUI

```bash
python main.py
```

Opens the calendar app: browse months, see which days have snapshots,
create a snapshot, compare the two latest snapshots, verify the latest
snapshot against the live folder, and manage settings — including
enabling daily mode while the GUI stays open.

### Command line — single snapshot

```bash
python main.py snapshot "C:\path\to\folder" --name "My Archive"
```

Common flags: `--description`, `--no-zip`, `--no-hashes`, `--no-diff`,
`--no-project-context`, `--max-file-mb`, `--max-total-mb`.

### Headless daily automation

No GUI needs to be open for this — it is meant to run under a scheduled
task, cron job, or process manager you configure yourself.

```bash
# 1. Create an example config
python main.py daily --init-config --config DAILY_SNAPSHOT_CONFIG.json

# 2. Edit the config: set source_folder, enabled: true, and any options
#    per job (see automation/daily_snapshot_runner.py for all fields)

# 3a. Run any due jobs once and exit (good for a scheduled task/cron entry)
python main.py daily --once --config DAILY_SNAPSHOT_CONFIG.json

# 3b. Or run a long-lived watcher that checks once per day at the
#     configured run_hour/run_minute
python main.py daily --watch --config DAILY_SNAPSHOT_CONFIG.json
```

Add `--force` to `--once` to re-run jobs that already ran today.

## Verification & Comparison

- **Compare** — `engine.change_report.compare_snapshot_dirs` diffs two
  snapshots' manifests and reports added/removed/modified/unchanged
  files. Available from the GUI's Compare tab.
- **Verify** — `engine.integrity_check.verify_snapshot_against_source`
  re-hashes the live source folder and checks it against a snapshot's
  recorded hashes and sizes, flagging anything changed or missing since
  the snapshot was taken. Available from the GUI's Verify tab.

Created by Jason Brisart
Part of BrisartPreservationTools
