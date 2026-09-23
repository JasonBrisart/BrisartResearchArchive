# Project Context Helper

A no-dependency Python utility that packages a project folder into a
readable Markdown context file, a JSON manifest, a plaintext summary,
a settings record, and an optional ZIP snapshot.

Pure Python. No external dependencies. Works fully offline.

## Quick Start

Run the desktop GUI:

```
python run.py
```

Build an export from the command line:

```
python run.py /path/to/project --profile archive
```

Check for updates without building anything:

```
python run.py --check-updates
```

Run `python run.py --help` for the full list of CLI flags.

## Your settings are always remembered (GUI)

The GUI automatically remembers whatever settings you used for your
most recent build — profile, output folder, size limits, every
toggle — and reloads them the next time you open the app. There's no
checkbox for this; it just always happens.

To start over from a clean baseline, pick `standard` or `archive`
from the profile dropdown on the Build tab.

**Note:** this is GUI-only behavior. The command-line interface stays
deterministic by default — see `--remember-settings` /
`--use-last-settings` below.

## GUI Tabs

- **Build** — pick a project folder, choose a built-in profile
  (`standard` / `archive`), and build.
- **Options** — Export Settings (output folder, size limits) and
  Included Output Sections.
- **Extras** — opt-in add-ons (currently just Include Git State) plus
  the Custom Profiles Save/Load/Delete section.
- **About** — app info, Recent Exports history, and update settings.

Both Options and Extras scroll if their content grows past the
visible window.

## What gets generated

Every build produces, inside `PROJECT_CONTEXT_EXPORTS/`:

- `PROJECT_CONTEXT.md` — the human-readable export
- `PROJECT_MANIFEST.json` — the same data in machine-readable form
- `PROJECT_SUMMARY.txt` — a compact plaintext overview
- `PROJECT_CONTEXT_SETTINGS.json` — the exact settings used
- `PROJECT_SNAPSHOT.zip` — optional, bundles the four files above plus
  every included source file

## Profiles

- **standard** — fast everyday export.
- **archive** (default) — maximum preservation, with an enforced
  source-completeness check.

## Extras (Optional)

On the **Extras** tab:

- **Include Git State** — adds a "Git State" section by reading
  `.git` directly. Off by default. CLI: `--git-state` /
  `--no-git-state`.

## Remembering settings from the command line

Unlike the GUI, the CLI does **not** automatically remember or reload
settings between runs:

- `--remember-settings` — save the exact settings used to
  `last_export_settings.json`.
- `--use-last-settings` — load that file as the base before other
  flags override it.

## Custom Profiles

On the **Extras** tab. Save the exact combination of settings under a
name you choose:

- **Save Current As** / **Load Selected** / **Delete Selected**

Profile names are matched with leading/trailing whitespace ignored on
both save and lookup. CLI: `--save-profile NAME`, `--load-profile NAME`,
`--delete-profile NAME`, `--list-profiles`.

## Folder Layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full breakdown.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.
