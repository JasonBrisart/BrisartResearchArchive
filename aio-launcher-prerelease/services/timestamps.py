"""
File: services/timestamps.py

Purpose:
Provide the single framework-agnostic timestamp helper for log and
status lines.

Communication / relationships:
- Used by controllers/log_controller.py.

Settings / parameters:
- Format: %Y-%m-%d %H:%M:%S in local time.

Edge cases:
- None; no I/O and no state.

Known limitations:
- Local time without a timezone offset. frameworks/TFL/engine.py
  records UTC ISO timestamps separately for trial data.

Examples:
- timestamp() returns a string such as "2026-09-26 10:15:00"
"""
from __future__ import annotations
from datetime import datetime
def timestamp() -> str:
    """Return a standard local timestamp for log/status messages."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
__all__ = ["timestamp"]
