"""
File: frameworks/TFL/output.py

Purpose
-------
Persist TFL rows the way the reference does (header first, one flushed
row per completed trial) while keeping every session: each run writes
its own timestamped file, and a completed run is then published as
tfl_output.csv.

Communication / relationships
-----------------------------
- session_gui.py and cli_runner.py create a SessionWriter and pass
  writer.write_row as the engine's on_trial_recorded hook.
- analysis.py reads tfl_output.csv by default, or any explicit path.
- Uses config/runtime.get_framework_output_dir() only when no directory
  is supplied.

Settings / parameters
---------------------
- SessionWriter(output_dir): opens tfl_output_<YYYYmmdd_HHMMSS_ffffff>.csv.
- write_row(row, rows): writes, flushes, and fsyncs one row.
- finalize(): closes the session file and atomically replaces
  tfl_output.csv with a copy of it.
- abandon(): closes the session file and leaves tfl_output.csv alone.

Edge cases
----------
- Every completed trial is on disk before the next trial begins, so an
  interrupted run keeps all completed trials in its session file.
- finalize() and abandon() are idempotent; the second call is a no-op.
- The latest-file copy goes through a .tmp file and os.replace().

Known limitations
-----------------
- Two simultaneous runs into the same folder each keep their own session
  file, but the last to finish owns tfl_output.csv.

Examples
--------
- writer = SessionWriter(output_dir); engine.on_trial_recorded = writer.write_row
- writer.finalize()
"""
from __future__ import annotations

import csv
import os
import shutil
from datetime import datetime
from pathlib import Path

from . import settings
from .schema import TRIAL_FIELDNAMES


def default_output_dir() -> Path:
    from config.runtime import get_framework_output_dir
    return get_framework_output_dir(settings.FRAMEWORK_ID)


def latest_output_file(output_dir: Path | None = None) -> Path:
    return Path(output_dir or default_output_dir()) / settings.OUTPUT_FILENAME


class SessionWriter:
    def __init__(self, output_dir: Path | str | None = None):
        self.output_dir = Path(output_dir) if output_dir is not None else default_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.session_file = self.output_dir / f"{settings.SESSION_FILE_PREFIX}{stamp}.csv"
        self.latest_file = self.output_dir / settings.OUTPUT_FILENAME
        self.rows_written = 0
        self.closed = False
        self.finalized = False
        self._handle = open(self.session_file, "w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._handle, fieldnames=TRIAL_FIELDNAMES, extrasaction="raise")
        self._writer.writeheader()
        self._sync()

    def _sync(self) -> None:
        self._handle.flush()
        try:
            os.fsync(self._handle.fileno())
        except OSError:
            pass

    def write_row(self, row: dict, _rows: list[dict] | None = None) -> None:
        if self.closed:
            raise RuntimeError("Session file is already closed.")
        self._writer.writerow(row)
        self._sync()
        self.rows_written += 1

    def _close(self) -> None:
        if not self.closed:
            self._handle.close()
            self.closed = True

    def abandon(self) -> Path:
        self._close()
        return self.session_file

    def finalize(self) -> Path:
        self._close()
        if not self.finalized:
            temporary = self.latest_file.with_name(self.latest_file.name + ".tmp")
            try:
                shutil.copyfile(self.session_file, temporary)
                os.replace(temporary, self.latest_file)
            finally:
                if temporary.exists():
                    temporary.unlink()
            self.finalized = True
        return self.latest_file


__all__ = ["SessionWriter", "default_output_dir", "latest_output_file"]
