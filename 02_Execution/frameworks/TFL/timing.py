"""
File: frameworks/TFL/timing.py

Purpose
-------
Provide the timer contract for the TFL engine: TimerInterface,
MonotonicTimer (GUI scheduling), DeadlineOnlyTimer (console), and
NullSchedulerTimer (deterministic virtual clock for tests and automation).

Communication / relationships
-----------------------------
- frameworks/TFL/engine.py consumes any TimerInterface.
- frameworks/TFL/gui_session.py builds a MonotonicTimer bound to its
  window's after() and after_cancel().
- frameworks/TFL/cli_runner.py uses DeadlineOnlyTimer.
- frameworks/TFL/headless.py and the tests use NullSchedulerTimer.

Settings / parameters
---------------------
- MonotonicTimer(schedule_fn=None, cancel_fn=None); now() is
  time.monotonic().
- DeadlineOnlyTimer: real clock, never calls back; deadlines are checked
  when an answer is submitted.
- NullSchedulerTimer: starts at 0.0; advance(seconds) moves the clock;
  schedule() records callbacks in .callbacks without ever running them.

Edge cases
----------
- MonotonicTimer.schedule() without a schedule_fn raises RuntimeError.
- cancel(None) is a no-op everywhere.
- A cancelled handle is dropped from .callbacks.
- The engine measures reaction times as differences of now(), so any
  timer with a consistent now() works.

Known limitations
-----------------
- No repeating timers.
- NullSchedulerTimer never runs callbacks by itself, even when advance()
  passes a deadline; a test that wants a timeout calls the recorded
  callback (or submits an answer, which the engine rejects as late).
- Tk's after() is not exact; a GUI timeout can fire slightly after the
  deadline, and the engine then records it as a timeout either way.

Examples
--------
- timer = NullSchedulerTimer(); timer.advance(12); engine.submit_prediction("A")
"""
from __future__ import annotations

import time
from typing import Callable


class TimerInterface:
    def now(self) -> float:
        raise NotImplementedError

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> object:
        raise NotImplementedError

    def cancel(self, handle: object) -> None:
        raise NotImplementedError


class MonotonicTimer(TimerInterface):
    def __init__(self, schedule_fn=None, cancel_fn=None):
        self._schedule_fn = schedule_fn
        self._cancel_fn = cancel_fn

    def now(self) -> float:
        return time.monotonic()

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> object:
        if self._schedule_fn is None:
            raise RuntimeError("GUI scheduling is unavailable in this environment.")
        return self._schedule_fn(delay_ms, callback)

    def cancel(self, handle: object) -> None:
        if handle is not None and self._cancel_fn is not None:
            self._cancel_fn(handle)


class DeadlineOnlyTimer(TimerInterface):
    """Real clock without callbacks: blocking console input cannot be
    interrupted portably, so the engine checks deadlines on submission."""

    def now(self) -> float:
        return time.monotonic()

    def schedule(self, delay_ms: int, callback: Callable[[], None]) -> object:
        return None

    def cancel(self, handle: object) -> None:
        return None


class NullSchedulerTimer(MonotonicTimer):
    def __init__(self):
        self.current = 0.0
        self.callbacks: dict[int, Callable[[], None]] = {}
        self.next_handle = 1
        super().__init__(schedule_fn=self._schedule, cancel_fn=self._cancel)

    def now(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += float(seconds)

    def _schedule(self, delay_ms, callback):
        handle = self.next_handle
        self.next_handle += 1
        self.callbacks[handle] = callback
        return handle

    def _cancel(self, handle):
        self.callbacks.pop(handle, None)


__all__ = ["TimerInterface", "MonotonicTimer", "DeadlineOnlyTimer", "NullSchedulerTimer"]

