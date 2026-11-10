"""
File: export/events.py

Purpose
-------
Define how a running export reports progress and how it is cancelled: the Progress event, the
  BuildCancelled exception, and the checkpoint() call the pipeline makes between units of work.
  It is its own module because the scanner and the pipeline both raise and report through it,
  and the pipeline imports the scanner.

Communication / relationships
-----------------------------
Imports nothing from the application. Imported by export/scan.py and export/pipeline.py
  (Progress, checkpoint), cli.py (Progress, for --progress), and gui/jobs.py (BuildCancelled).

Settings / parameters
---------------------
Progress phases, in order: discovering, capturing (with completed/total file counts),
  rendering, zipping, publishing. total is 0 when a phase has no countable units.

Edge cases
----------
checkpoint(None) never cancels, so callers that cannot cancel pass None. BuildCancelled is
  deliberately not a ValueError, so interfaces can tell "cancelled" apart from "stopped by
  validation".

Known limitations
-----------------
Cancellation is cooperative: it is noticed only at checkpoints, so one slow file read or ZIP
  write finishes first. The pipeline stops checking once publication starts.

Examples
--------
Usage from the directory containing run.py:

    from threading import Event
    from export.events import BuildCancelled, checkpoint

    cancel = Event()
    checkpoint(cancel)
    cancel.set()
    try:
        checkpoint(cancel)
    except BuildCancelled:
        print("cancelled")
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event


class BuildCancelled(Exception):
    """Raised at a pipeline checkpoint after cancellation was requested."""


@dataclass(frozen=True, slots=True)
class Progress:
    phase: str
    completed: int = 0
    total: int = 0
    message: str = ""


def checkpoint(cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise BuildCancelled("Build cancelled before the export was published.")