"""
Shared timing abstractions for framework session engines.

This is the OpenClaw-branch idea generalized: instead of one timer
class living inside frameworks/TFL, it lives here so every future
framework engine (SST, PFT, PCT, RIET, IRE) can reuse the same
schedule/cancel/now contract without copy-pasting it per framework.

TimerInterface is the contract. MonotonicTimer drives real GUI
scheduling (e.g. Tk's .after()). NullSchedulerTimer is a deterministic
virtual clock used by headless engine tests - no real time passes,
and a test manually advances the clock and fires scheduled callbacks.
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
