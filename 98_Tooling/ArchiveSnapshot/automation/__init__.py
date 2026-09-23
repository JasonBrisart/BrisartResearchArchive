"""
automation
----------

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