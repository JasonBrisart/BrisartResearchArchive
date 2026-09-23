"""
services/timestamps.py
The single generic timestamp helper for log/status messages. Kept
framework-agnostic and dependency-free: controllers/log_controller.py
prefixes every logged line with this, and it has no knowledge of TFL or
any other framework.

Split out of the old services/__init__.py so the services package needs
no __init__.py of its own -- it is now a PEP 420 namespace package,
consistent with every other package in this project.
"""
from __future__ import annotations
from datetime import datetime
def timestamp() -> str:
    """Return a standard local timestamp for log/status messages."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
__all__ = ["timestamp"]
