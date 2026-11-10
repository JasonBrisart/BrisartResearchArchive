"""
File: gui/jobs.py

Purpose
-------
Run one export at a time on a background thread and pass its progress and outcome back to
  the Tk thread through a queue, so the window stays responsive during long builds.

Communication / relationships
-----------------------------
Imports export/events.py (BuildCancelled). Imported by gui/state.py, which stores a JobRunner
  in GuiState; gui/build_tab.py starts jobs and drains events; gui/window.py cancels on close.

Settings / parameters
---------------------
start(operation) calls operation(cancel_event, emit) on a non-daemon thread named pch-job.
  Events are ("progress", Progress), ("done", result), ("cancelled", message), or
  ("error", exception); drain() yields up to 100 per call without blocking.

Edge cases
----------
start raises RuntimeError while a job is still running. Exceptions are queued as objects so
  the Build tab can show ValueError as "Build Stopped" and anything else as "Build Failed".

Known limitations
-----------------
The queue is unbounded. The thread is non-daemon, so closing the program waits for a running
  export to finish or reach a cancellation checkpoint.

Examples
--------
Usage from the directory containing run.py:

    from gui.jobs import JobRunner

    runner = JobRunner()
    runner.start(lambda cancel, emit: 42)
    runner.thread.join()
    print(list(runner.drain()))     # [('done', 42)]
"""

from __future__ import annotations

from queue import Empty, Queue
from threading import Event, Thread
from typing import Callable, Iterator

from export.events import BuildCancelled


class JobRunner:
    def __init__(self) -> None:
        self.events: Queue = Queue()
        self.cancel = Event()
        self.thread: Thread | None = None

    @property
    def busy(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self, operation: Callable[[Event, Callable], object]) -> None:
        if self.busy:
            raise RuntimeError("A build is already running.")
        self.cancel = Event()
        cancel = self.cancel

        def worker() -> None:
            try:
                result = operation(cancel, lambda event: self.events.put(("progress", event)))
                self.events.put(("done", result))
            except BuildCancelled as exc:
                self.events.put(("cancelled", str(exc)))
            except Exception as exc:
                self.events.put(("error", exc))

        self.thread = Thread(target=worker, name="pch-job", daemon=False)
        self.thread.start()

    def drain(self) -> Iterator[tuple[str, object]]:
        for _ in range(100):
            try:
                yield self.events.get_nowait()
            except Empty:
                return