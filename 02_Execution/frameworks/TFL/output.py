"""
File: frameworks/TFL/output.py

Purpose
-------
Save TFL sessions so nothing is ever overwritten and nothing answered is
ever lost: every run gets its own CSV whose name ends with the date and
time it started, and the whole session is re-saved after every single
answer.

Communication / relationships
-----------------------------
- frameworks/TFL/gui_session.py and frameworks/TFL/cli_runner.py create a
  SessionWriter and pass writer.save as the engine's on_progress hook.
- frameworks/TFL/analysis.py uses latest_session_file(); cli.py and
  gui/pages/results_page.py use list_session_files().
- default_output_dir() resolves the folder through config/runtime.py:
  %APPDATA%/Brisart Research Archive/outputs/TFL unless the user picked
  another Output Directory in Settings.
- Columns come from frameworks/TFL/schema.TRIAL_FIELDNAMES.

Settings / parameters
---------------------
- File name: tfl_output_[<label>_]YYYY-MM-DD_HH-MM-SS.csv. If two runs
  start in the same second, a counter is added: ..._HH-MM-SS_2.csv.
- SessionWriter(output_dir=None, label="", started_at=None); path is the
  run's file and rows_saved is the row count of the last snapshot,
  including an in-progress row.
- save(rows): writes the full snapshot to a hidden temporary file in the
  same folder, flushes and fsyncs it, then os.replace()s it over this run's
  own file. close() marks the run finished; the file already holds
  everything.
- list_session_files() returns every tfl_output*.csv in the folder, oldest
  first by last-saved time (then name); latest_session_file() returns the
  last. The pattern also matches the legacy tfl_output.csv of 0.9.3.

Edge cases
----------
- The file is created with exclusive mode ("x") and its header written at
  once, so a writer never opens, truncates, or overwrites any existing
  file, including another run's, and an empty run still leaves a
  header-only file.
- A crash or power loss during a save leaves either the previous snapshot
  or the new one, never a half-written CSV.
- If a save fails (for example the CSV is open in Excel on Windows and
  locked), the temporary file is removed and the error propagates to the
  engine, which records it and continues; the next successful save writes
  the complete session again.
- A row with a key outside the schema raises at save time; a missing key is
  written blank.
- save() after close() raises RuntimeError.

Known limitations
-----------------
- Each save rewrites the whole file. Measured with the built-in stimuli, a
  120-trial session with perturbations is about 31 KB and is rewritten 422
  times, roughly 6.5 MB written over a session. That is not noticeable on a
  local disk but may be on a slow network or synced folder.
- Nothing is ever deleted; old session files accumulate until removed by
  hand.
- Durability against power loss is not claimed; the temp-and-replace
  sequence protects against a killed process.

Examples
--------
- writer = SessionWriter(output_dir, label="pilot01")
- writer.save(engine.snapshot())
- latest_session_file(output_dir)
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

from . import settings
from .schema import TRIAL_FIELDNAMES


def default_output_dir() -> Path:
    from config.runtime import get_tfl_output_dir
    return get_tfl_output_dir()


def list_session_files(output_dir: Path | str | None = None) -> list[Path]:
    """All TFL CSVs in the folder, oldest first by last save time."""
    folder = Path(output_dir) if output_dir is not None else default_output_dir()
    if not folder.is_dir():
        return []
    files = [path for path in folder.glob(f"{settings.OUTPUT_FILE_PREFIX}*.csv") if path.is_file()]
    return sorted(files, key=lambda path: (path.stat().st_mtime, path.name))


def latest_session_file(output_dir: Path | str | None = None) -> Path | None:
    files = list_session_files(output_dir)
    return files[-1] if files else None


class SessionWriter:
    def __init__(self, output_dir: Path | str | None = None, label: str = "", started_at: datetime | None = None):
        self.output_dir = Path(output_dir) if output_dir is not None else default_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = (started_at or datetime.now()).strftime(settings.OUTPUT_TIMESTAMP_FORMAT)
        stem = f"{settings.OUTPUT_FILE_PREFIX}_{label + '_' if label else ''}{stamp}"
        self.path = self._create_exclusive(stem)
        self.rows_saved = 0
        self.closed = False

    def _create_exclusive(self, stem: str) -> Path:
        counter = 1
        while True:
            path = self.output_dir / (f"{stem}.csv" if counter == 1 else f"{stem}_{counter}.csv")
            try:
                with open(path, "x", newline="", encoding="utf-8") as handle:
                    csv.DictWriter(handle, fieldnames=TRIAL_FIELDNAMES).writeheader()
                    handle.flush()
                    os.fsync(handle.fileno())
                return path
            except FileExistsError:
                counter += 1

    def save(self, rows: list[dict]) -> None:
        if self.closed:
            raise RuntimeError("This session file is closed.")
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        try:
            with open(temporary, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=TRIAL_FIELDNAMES, extrasaction="raise")
                writer.writeheader()
                writer.writerows(rows)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()
        self.rows_saved = len(rows)

    def close(self) -> Path:
        self.closed = True
        return self.path


__all__ = ["SessionWriter", "default_output_dir", "list_session_files", "latest_session_file"]

