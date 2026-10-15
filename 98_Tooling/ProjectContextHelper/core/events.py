"""
File: core/events.py

Purpose
-------
Define the progress record and cooperative cancellation checkpoint shared by the export
  pipeline, the GUI worker, and the CLI (new in v4.0.0).

Implemented responsibilities:
- BuildCancelled: Exception raised at a checkpoint once cancellation has been requested. It
  is deliberately not a ValueError, so interfaces can tell "cancelled" apart from "stopped".
- Progress: Immutable progress event (phase, completed, total, message) passed to an optional
  progress callback; carries plain values only, never tkinter objects.
- checkpoint: Raise BuildCancelled when the supplied threading.Event is set; a None event
  never cancels.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
This file imports no other application modules; its implementation uses the standard library.

Consumers in the supplied source:
- core/scanner.py imports BuildCancelled, Progress, checkpoint.
- core/builder.py imports Progress, checkpoint.
- gui/jobs.py imports BuildCancelled.
- cli/cli.py imports Progress.

Settings / parameters
---------------------
Progress phases emitted by the pipeline: discovering, capturing, rendering, zipping,
  publishing. total is 0 when a phase has no countable units.

Function signatures (nested callbacks are scoped to their enclosing function):
- checkpoint(cancel: threading.Event | None) -> None

Edge cases
----------
checkpoint(None) is a no-op, so callers that never cancel can pass None. Setting the event
  after publication has started has no effect on that export.

Known limitations
-----------------
Cancellation is cooperative: it is observed only at checkpoints, so a single slow file read
  or ZIP write finishes before cancellation takes effect.

Examples
--------
Usage from the directory containing run.py:

    from threading import Event
    from core.events import BuildCancelled, checkpoint

    cancel = Event()
    checkpoint(cancel)          # no-op
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
