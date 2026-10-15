"""
File: gui/jobs.py

Purpose
-------
Run one export at a time on a background thread for the desktop GUI and hand its progress and
  outcome back through a queue, so the Tk thread stays responsive (new in v4.0.0).

Implemented responsibilities:
- JobRunner.__init__: Create the event queue, a cancellation Event, and an empty thread slot.
- JobRunner.busy: Report whether the current worker thread is still alive.
- JobRunner.start: Refuse to start while busy; otherwise create a fresh cancellation Event and
  run operation(cancel, emit) on a non-daemon thread named pch-job.
- JobRunner.drain: Yield up to 100 queued events without blocking; called from Tk after()
  callbacks.
- worker: Nested thread body: run the operation and queue ('progress', Progress),
  ('done', result), ('cancelled', message), or ('error', exception).

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.events: BuildCancelled.

Consumers in the supplied source:
- gui/builders.py imports JobRunner.

Settings / parameters
---------------------
operation is any callable taking (cancel: threading.Event, emit: Callable[[Progress], None])
  and returning a result. Events are plain Python objects; the worker never touches tkinter.

Function signatures (nested callbacks are scoped to their enclosing function):
- __init__(self) -> None
- busy(self) -> bool
- start(self, operation: Callable[[Event, Callable], object]) -> None
- drain(self) -> Iterator[tuple[str, object]]
- worker() -> None

Edge cases
----------
Exceptions are queued as exception objects, so the GUI can show ValueError as "Build Stopped"
  and anything else as "Build Failed", exactly as v3.1.4 did on the Tk thread. Starting while a
  job is running raises RuntimeError.

Known limitations
-----------------
Cancellation is cooperative (see core/events.py). The queue is unbounded; the GUI drains it in
  batches of 100 every 80 ms. The thread is non-daemon, so the process waits for a running
  export to finish or cancel before exiting.

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

from core.events import BuildCancelled


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
