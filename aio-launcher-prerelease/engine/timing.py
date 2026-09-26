"""
File: engine/timing.py

Purpose:
Provide the shared timer contract for framework session engines:
TimerInterface (the contract), MonotonicTimer (real GUI scheduling),
and NullSchedulerTimer (a deterministic virtual clock for tests).

Communication / relationships:
- frameworks/TFL/engine.py consumes any TimerInterface.
- frameworks/TFL/session_gui.py builds a MonotonicTimer bound to its
  Toplevel's after() and after_cancel().
- app/headless.py and tests/test_merged.py use NullSchedulerTimer.
- Intended for reuse by future framework engines.

Settings / parameters:
- MonotonicTimer(schedule_fn=None, cancel_fn=None); now() uses
  time.monotonic().
- NullSchedulerTimer: the clock starts at 0.0; advance(seconds) moves
  it; fire(handle) runs one scheduled callback.

Edge cases:
- schedule() without a schedule_fn raises RuntimeError.
- cancel(None) is a no-op.
- fire() on a cancelled or unknown handle does nothing.
- NullSchedulerTimer ignores delay_ms; callbacks run only through fire().

Known limitations:
- No repeating timers.
- NullSchedulerTimer does not fire callbacks automatically when
  advance() passes their deadline.

Examples:
- timer = NullSchedulerTimer(); handle = timer.schedule(12000, callback); timer.fire(handle)
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
    """
    Real-time timer driven by a host scheduler.
    schedule_fn/cancel_fn are normally bound to a Tk Toplevel's
    .after()/.after_cancel(), but any compatible scheduler works.
    """

    def __init__(
        self,
        schedule_fn: Callable[[int, Callable[[], None]], object] | None = None,
        cancel_fn: Callable[[object], None] | None = None,
    ):
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


class NullSchedulerTimer(MonotonicTimer):
    """
    Deterministic virtual-clock timer for headless engine tests.
    """

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


__all__ = ["TimerInterface", "MonotonicTimer", "NullSchedulerTimer"]
