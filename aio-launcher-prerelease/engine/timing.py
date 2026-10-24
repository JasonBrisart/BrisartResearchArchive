"""
File: engine/timing.py

Purpose
-------
Provide the shared timer contract for framework session engines:
TimerInterface, MonotonicTimer (GUI scheduling), DeadlineOnlyTimer
(console runs), and NullSchedulerTimer (deterministic virtual clock).

Communication / relationships
-----------------------------
- frameworks/TFL/engine.py consumes any TimerInterface.
- frameworks/TFL/session_gui.py builds a MonotonicTimer bound to its
  Toplevel's after() and after_cancel().
- frameworks/TFL/cli_runner.py uses DeadlineOnlyTimer.
- app/headless.py and the tests use NullSchedulerTimer.

Settings / parameters
---------------------
- MonotonicTimer(schedule_fn=None, cancel_fn=None); now() uses
  time.monotonic().
- DeadlineOnlyTimer: now() is monotonic; schedule() returns None and
  never calls back, so deadlines are enforced at submission time.
- NullSchedulerTimer: clock starts at 0.0; advance(seconds); fire(handle).

Edge cases
----------
- MonotonicTimer.schedule() without a schedule_fn raises RuntimeError.
- cancel(None) is a no-op everywhere.
- fire() on a cancelled or unknown handle does nothing.

Known limitations
-----------------
- No repeating timers.
- NullSchedulerTimer does not fire callbacks automatically when
  advance() passes a deadline; tests call fire().

Examples
--------
- timer = NullSchedulerTimer(); handle = timer.schedule(12000, cb); timer.fire(handle)
- MonotonicTimer(schedule_fn=window.after, cancel_fn=window.after_cancel)
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

    def fire(self, handle):
        callback = self.callbacks.pop(handle, None)
        if callback is not None:
            callback()


__all__ = ["TimerInterface", "MonotonicTimer", "DeadlineOnlyTimer", "NullSchedulerTimer"]
