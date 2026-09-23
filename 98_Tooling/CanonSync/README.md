# CanonSync

One source of truth for the boilerplate files every repo shares —
`.gitignore`, `.editorconfig`, `.gitattributes`, `LICENSE`, and whatever
else you standardize. Edit one canonical copy, run one tool, and every
repo gets the same content. Each repo's own additions are preserved.

Part of **BrisartDevTools**.

- Pure standard library (Tkinter GUI + a plain-Python engine).
- Local-first / offline. Never touches the network.
- Safe by default: previews a plan first; nothing is written until you
  press **Apply**. Optional timestamped backups before any overwrite.
- Per-repo **allow / block** so you can point at a whole folder and still
  exempt individual repos.
- Idempotent: re-running with no source change writes nothing.

CanonSync is the successor to the earlier gitignore-only sync tool,
generalized to sync any number of canonical files.

---

## The problem it solves

Keeping the same `.gitignore` (and license, editor config, ...) in sync by
hand across many repos is tedious and drifts fast. CanonSync makes the
files under `canon/` the single source of truth and pushes them into every
repo for you — without clobbering the rules a repo added for itself.

---

## Files

```
CanonSync/
├── canonsync_gui.py         # the GUI you run
├── canonsync_core.py        # engine (imported by the GUI; also a CLI)
├── canonsync.config.json    # declares WHAT syncs and HOW
├── CHANGELOG.md             # version history
└── canon/                   # the canonical sources you edit
    ├── gitignore.master
    ├── editorconfig.master
    ├── gitattributes.master
    └── LICENSE
```

You edit the files in `canon/`. Everything else is machinery.

---

## Two sync modes

Different canonical files behave differently, so each item in the config
declares a mode:

| Mode    | What it does                                                        | Used for |
|---------|--------------------------------------------------------------------|----------|
| `block` | Injects the canonical content into a delimited **managed block**, preserving whatever the repo added above or below it. | `.gitignore`, `.editorconfig`, `.gitattributes` |
| `whole` | Replaces the **entire** destination file. Nothing in the repo's copy is kept. | `LICENSE` |

### Block mode layout

In a repo's file, `block` mode writes:

```
# >>> CANONICAL (managed by CanonSync) - DO NOT EDIT >>>
...content from the master...
# <<< CANONICAL <<<

# --- repo-specific (not managed) ---
...anything this repo added itself, left untouched...
```

- Only the text between the markers is managed. Everything outside it is
  preserved.
- The block is found by the markers, not by any filename, so the tool can
  be renamed later without orphaning existing blocks.

### Whole mode

`whole` mode is a full-file replacement, so it makes **no per-repo
exceptions**. It exists for files like `LICENSE` that have no
repo-specific part. Because it is destructive, `whole` items are
**disabled by default** in the config.

---

## Allow / block repositories

After a scan, every discovered repo appears in a checkable list:

- **☑ checked = ALLOW** — the repo is included and gets written.
- **☐ unchecked = BLOCK** — the repo is skipped entirely; nothing is
  written to it. It still appears in the plan as **BLOCKED** so you can see
  what was skipped.

Click a repo's **Allow** cell (or press **Space** on the highlighted row)
to toggle it. **Allow all** / **Block all** flip everything at once. This
lets you aim CanonSync at your whole GitHub folder and still exempt a
legacy repo, a vendored fork, etc.

On the command line, block repos with `--block PATH` (repeatable).

---

## Quick start (GUI)

```bash
python canonsync_gui.py
```

1. **Canon config** — point at `canonsync.config.json` (auto-filled if it's
   beside the app). The canonical files it declares appear as checkboxes.
2. **Tick the files** you want to sync.
3. **Repositories folder** — Browse to the folder that contains your repos
   (e.g. your GitHub directory), then **Scan**. Every immediate subfolder
   containing a `.git` is found.
4. **Allow / block repos** — every repo starts allowed (☑). Untick any you
   want to skip, or use Allow all / Block all.
5. **Preview (dry run)** — the table shows, per repo and per file, what
   would change: 🟢 CREATE, 🟠 UPDATE, ⚪ unchanged, 🔴 missing, 🟡 BLOCKED.
   Nothing is written.
6. *(Optional)* tick **Back up files before overwriting** to drop a
   timestamped `.bak` beside each file it updates.
7. **Apply** — enabled only when there are changes. It asks for
   confirmation (warning about whole-mode files and blocked repos), then
   writes.

### Command line

The engine runs standalone for scripting or automation:

```bash
# Preview across every repo in a folder (writes nothing)
python canonsync_core.py --discover /path/to/GitHub

# Apply to every discovered repo
python canonsync_core.py --discover /path/to/GitHub --apply

# Apply, but block a couple of repos, keeping backups
python canonsync_core.py --discover /path/to/GitHub \
    --block /path/to/GitHub/Legacy --block /path/to/GitHub/VendoredFork \
    --apply --backup

# Target specific repos instead of discovering
python canonsync_core.py --repo ../ArchiveSnapshot --repo ../Entitle --apply

# Sync only certain items by name
python canonsync_core.py --discover /path/to/GitHub --only gitignore,editorconfig --apply
```

Options:

- `--config PATH`  — the config file (default: `canonsync.config.json`)
- `--repo PATH`    — a target repo root (repeatable)
- `--discover DIR` — auto-find git repos in the immediate subfolders of DIR
- `--only a,b`     — restrict to these item names (default: all enabled)
- `--block PATH`   — block/skip a repo (repeatable)
- `--backup`       — write a timestamped `.bak` before overwriting a file
- `--apply`        — actually write; without it, a safe dry run
- `--version`      — print the version and exit

---

## Configuring what syncs

`canonsync.config.json` is a list of items:

```json
{
  "name": "gitignore",
  "source": "canon/gitignore.master",
  "dest": ".gitignore",
  "mode": "block",
  "enabled": true
}
```

- `name`    — label shown in the GUI and used by `--only`.
- `source`  — path to the canonical file, relative to the config.
- `dest`    — filename written inside each repo.
- `mode`    — `block` or `whole`.
- `enabled` — whether it syncs by default.

**To add a new canonical file** (e.g. a `CODE_OF_CONDUCT.md`): drop the
source into `canon/`, add one item to the list, and it appears in the GUI
automatically. `block` mode requires a `#`-comment-friendly destination so
the markers are valid comments.

### Enabling the LICENSE sync (read first)

The shipped `canon/LICENSE` is a **placeholder**, and its config item is
`"enabled": false`. Because whole mode replaces the entire LICENSE in
every target repo, turn it on only after:

1. Replacing `canon/LICENSE` with your actual license text.
2. Confirming the same terms are correct for **every** repo you sync to —
   whole mode makes no exceptions.
3. Setting `"enabled": true` for the license item in the config.

Authoritative licensing terms and governance are maintained separately in
the BrisartLicensing repository; treat that as the definitive source
before publishing the file here.

---

## Notes and limitations

- **Already-committed junk isn't untracked automatically.** Adding a rule
  to `.gitignore` does not remove a file Git is already tracking. If an
  artifact was committed before the rule existed, untrack it once with
  `git rm --cached <path>` and commit.
- **The marker string defines a block's identity.** If you change
  `BEGIN_MARKER` / `END_MARKER` in `canonsync_core.py` after rolling out,
  the next run won't recognize old blocks and will add a second one. Pick
  the markers before wide use. (They are unchanged since 1.0.0.)
- **Discovery is one level deep.** `--discover` looks at the immediate
  subfolders of the folder you point at (plus that folder itself). Nested
  repos aren't found recursively — pass them with `--repo`.
- **Backups are local `.bak` files.** The canonical `.gitignore` ignores
  `*.bak` so they won't be committed. Clean them up when you're satisfied.
- **No network, ever.** CanonSync only reads and writes local files.

See [CHANGELOG.md](CHANGELOG.md) for version history.

Created by Jason Brisart · Part of BrisartDevTools.
