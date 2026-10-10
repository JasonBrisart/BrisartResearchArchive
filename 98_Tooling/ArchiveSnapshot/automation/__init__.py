"""
File: automation/__init__.py

Purpose
-------
automation

Communication / relationships
-----------------------------
Direct module imports: .daily_snapshot_runner.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.

Additional module documentation
-------------------------------
automation

Headless daily snapshot automation for ArchiveSnapshot.

Daily jobs use the same snapshot engine as the GUI and direct command-line
interface, keeping manually created and scheduled snapshots consistent.
"""

from .daily_snapshot_runner import (
    DailySnapshotConfig,
    DailySnapshotJob,
    add_daily_arguments,
    run_daily_command,
)


__all__ = [
    "DailySnapshotConfig",
    "DailySnapshotJob",
    "add_daily_arguments",
    "run_daily_command",
]
