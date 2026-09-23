"""
engine.retention
-----------------
Snapshot retention for ArchiveSnapshot.

The store grows without bound: every snapshot ever created stays on disk
forever. This module adds an optional, explicit pruning pass so a source
folder's ARCHIVE_SNAPSHOT store can be kept to a chosen size without
touching the live source files or the snapshot format itself.

Design goals, matching the rest of the engine:
- Pure engine logic: no Tkinter, no CLI, no third-party dependencies.
- Safe by default: callers must opt in to deletion (apply_retention).
  A dry-run plan is always produced first so nothing is removed silently.
- Only ever operates inside the ARCHIVE_SNAPSHOT store for the given
  source root. It never deletes the source folder or anything outside
  the store.
"""
from __future__ import annotations

import datetime
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .settings import StoredSnapshot
from .snapshot_index import discover_snapshots, write_store_index


@dataclass(slots=True)
class RetentionPolicy:
    """
    How many snapshots to keep.

    A snapshot is kept if it satisfies EITHER rule, so the two settings
    are protections that add together rather than fight each other:

    - keep_last: always keep this many of the most recent snapshots.
      0 disables the count rule.
    - keep_within_days: always keep snapshots created within this many
      days of now. 0 disables the age rule.

    If both rules are disabled, nothing is ever removed (fail-safe).
    """
    keep_last: int = 10
    keep_within_days: int = 0


@dataclass(slots=True)
class RetentionPlan:
    """
    The result of evaluating a policy against a source folder.

    `applied` is False for a dry run (nothing deleted) and True once the
    kept/removed split has actually been carried out on disk.
    """
    source_root: str
    keep_last: int
    keep_within_days: int
    total_snapshots: int
    kept: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    freed_bytes: int = 0
    applied: bool = False


def parse_created(snapshot: StoredSnapshot) -> datetime.datetime | None:
    """
    Best-effort parse of a snapshot's recorded creation time.

    Falls back to the date_key (local midnight) when the full timestamp
    cannot be parsed, so age-based retention still has something to work
    with. Returns None only when neither can be interpreted.
    """
    created = snapshot.created.strip()
    if created:
        try:
            return datetime.datetime.strptime(created, "%Y-%m-%d %H:%M:%S %z")
        except ValueError:
            pass
    try:
        return datetime.datetime.strptime(snapshot.date_key, "%Y-%m-%d").astimezone()
    except ValueError:
        return None


def within_age(
    snapshot: StoredSnapshot,
    keep_within_days: int,
    now: datetime.datetime,
) -> bool:
    """
    Return True if a snapshot is young enough to keep under the age rule.

    When a snapshot cannot be dated it is treated as protected, so an
    unreadable timestamp never causes a deletion.
    """
    if keep_within_days <= 0:
        return False
    created = parse_created(snapshot)
    if created is None:
        return True
    cutoff = now - datetime.timedelta(days=keep_within_days)
    return created >= cutoff


def directory_size(path: Path) -> int:
    """
    Total size in bytes of every file under a snapshot directory.
    """
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def plan_retention(source_root: str | Path, policy: RetentionPolicy) -> RetentionPlan:
    """
    Build a retention plan without deleting anything.

    discover_snapshots returns snapshots oldest-first, so the most recent
    `keep_last` entries are simply the tail of that list.
    """
    root = Path(source_root).expanduser().resolve()
    snapshots = discover_snapshots(root)
    now = datetime.datetime.now().astimezone()

    protected_by_count: set[Path] = set()
    if policy.keep_last > 0:
        for snapshot in snapshots[-policy.keep_last:]:
            protected_by_count.add(snapshot.snapshot_dir)

    both_rules_disabled = policy.keep_last <= 0 and policy.keep_within_days <= 0

    kept: list[str] = []
    removed: list[str] = []
    freed = 0
    for snapshot in snapshots:
        keep = (
            both_rules_disabled
            or snapshot.snapshot_dir in protected_by_count
            or within_age(snapshot, policy.keep_within_days, now)
        )
        if keep:
            kept.append(str(snapshot.snapshot_dir))
        else:
            removed.append(str(snapshot.snapshot_dir))
            freed += directory_size(snapshot.snapshot_dir)

    return RetentionPlan(
        source_root=str(root),
        keep_last=policy.keep_last,
        keep_within_days=policy.keep_within_days,
        total_snapshots=len(snapshots),
        kept=kept,
        removed=removed,
        freed_bytes=freed,
        applied=False,
    )


def apply_retention(source_root: str | Path, policy: RetentionPolicy) -> RetentionPlan:
    """
    Evaluate the policy and actually remove the snapshots it selects.

    Each removed snapshot directory is deleted with shutil.rmtree, then
    the store index is rewritten so it reflects only the surviving
    snapshots. The snapshot storage format is unchanged.
    """
    plan = plan_retention(source_root, policy)
    for snapshot_dir in plan.removed:
        try:
            shutil.rmtree(snapshot_dir)
        except OSError:
            continue
    if plan.removed:
        write_store_index(Path(plan.source_root))
    plan.applied = True
    return plan


def build_retention_report(plan: RetentionPlan) -> str:
    """
    Human-readable summary of a retention plan or an applied prune.
    """
    from .snapshot_writer import human_bytes

    heading = "Applied Prune" if plan.applied else "Retention Plan (dry run)"
    verb = "Removed" if plan.applied else "To Remove"
    space_label = "freed" if plan.applied else "to free"

    lines: list[str] = []
    lines.append(f"# Archive Snapshot {heading}")
    lines.append("")
    lines.append(f"Source folder: `{plan.source_root}`")
    lines.append(f"Keep last: `{plan.keep_last}`")
    lines.append(f"Keep within days: `{plan.keep_within_days}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total snapshots: `{plan.total_snapshots}`")
    lines.append(f"- Keeping: `{len(plan.kept)}`")
    lines.append(f"- Removing: `{len(plan.removed)}`")
    lines.append(f"- Space {space_label}: `{human_bytes(plan.freed_bytes)}`")
    lines.append("")
    lines.append(f"## Snapshots {verb}")
    lines.append("")
    if plan.removed:
        for path in plan.removed:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None. Every snapshot is protected by the current policy.")
    return "\n".join(lines)
