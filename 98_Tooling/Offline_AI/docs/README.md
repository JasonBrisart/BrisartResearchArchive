# Docs

This folder contains the user-facing BrisartAI guide, versioned engineering changelog, and test and benchmark record. The documents explain how to operate and validate the application; they are not runtime configuration.

`CHANGELOG.md` preserves release history and implementation rationale. `TESTING.md` distinguishes executed tests and measurements from historical benchmarks and integration checks still outstanding.

## Documentation in this folder

- [README.md](README.md): Installation, launch commands, source management and local state.
- [ARCHITECTURE.md](ARCHITECTURE.md): Runtime responsibilities, module ownership and data flow.
- [SECURITY.md](SECURITY.md): Local-data exposure, deletion boundaries and file-parser safeguards.
- [TESTING.md](TESTING.md): Reproduction commands, executed tests, benchmark results and limitations.
- [CHANGELOG.md](CHANGELOG.md): Versioned changes and engineering rationale, newest release first.

## Application overview

BrisartAI indexes local files and research notes, then answers questions using selected excerpts and citations. It does not search the internet. Results reflect the indexed copy and may differ from a source subsequently changed on disk.

## Start here

Keep `Offline_AI` under `98_Tooling` in the Archive, or point `BRISART_NATIVE_API` at an external folder holding `brisart_hash.py`, `brisart_inflate.py`, `brisart_json.py`, `brisart_markup.py` and `brisart_url.py`. In the Archive layout the loader prefers `94_Native_API's/Official`. It does not download or bundle the helpers. A full existing Official installation remains usable.

From `Offline_AI`, run `python run.py` for the desktop (requires Tk) or use the CLI:

```text
python cli.py import "notes.md" "Reference Library"
python cli.py ask "What is the permit fee?"
python cli.py note "Experiment 14" "Check the readings against the baseline."
python cli.py notes --limit 10
python cli.py counts

## Recovering existing encrypted archives

BrisartAI no longer offers manual backup creation. This build still stores indexed imports in the existing plaintext SQLite library; automatic library encryption and unlock are not implemented. Original files are unchanged by this update.

The recovery commands require the Archive's trusted `97_Encryption/Official` implementation and the original archive passphrase. Set `BRISART_ENCRYPTION` to that directory if it is not discovered automatically. To verify an existing archive, run `python cli.py backup-verify research.bsa` from `Offline_AI`.

Restore the archive into a **new private folder**, not the active profile:

```text
python cli.py backup-restore research.bsa recovery-copy
```

Restore authenticates the archive and validates its database before creating the destination. It refuses to overwrite an existing folder or restore to the active profile location.

Recovery writes plaintext. Inspect the recovered index with `python cli.py --db recovery-copy/brisart_ai_index.sqlite3 counts` before any manual profile replacement. Do not copy recovered files over a running instance or an existing profile without a separate backup. See [Security](SECURITY.md) for what this feature does not protect.

## Encrypted research library

When the desktop detects a plaintext library, it offers to encrypt the SQLite library that contains indexed copies, research notes and conversation history. **No** leaves the library unchanged and asks again next launch. **Yes** shows an estimated conversion time, closes database connections, verifies the encrypted container and then reopens a private working copy.

After migration, every import, note, question-history update and source removal checkpoints the current database into the encrypted container. On Windows, the generated archive passphrase is protected for the current user with DPAPI, allowing automatic unlock at launch. Original imported files are not encrypted or rewritten. During use, BrisartAI requires a private temporary plaintext SQLite working copy; a clean shutdown checkpoints it and removes the temporary directory.
