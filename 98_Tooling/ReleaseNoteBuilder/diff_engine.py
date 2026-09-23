"""
Folder comparison engine for ReleaseNoteBuilder.
"""

from __future__ import annotations

from pathlib import Path
from filesystem import collect_file_snapshot, build_tree


def compare_snapshots(old_snapshot: dict, new_snapshot: dict) -> dict:
    old_paths = set(old_snapshot.keys())
    new_paths = set(new_snapshot.keys())
    added_paths = sorted(new_paths - old_paths)
    removed_paths = sorted(old_paths - new_paths)
    shared_paths = sorted(old_paths.intersection(new_paths))
    modified_paths = []
    unchanged_paths = []

    for path in shared_paths:
        old_hash = old_snapshot[path].get("hash")
        new_hash = new_snapshot[path].get("hash")
        if old_hash != new_hash:
            modified_paths.append(path)
        else:
            unchanged_paths.append(path)

    return {
        "added": [new_snapshot[path] for path in added_paths],
        "removed": [old_snapshot[path] for path in removed_paths],
        "modified": [
            {"path": path, "old": old_snapshot[path], "new": new_snapshot[path]}
            for path in modified_paths
        ],
        "unchanged": [new_snapshot[path] for path in unchanged_paths],
    }


def build_project_comparison(old_root: Path, new_root: Path) -> dict:
    old_snapshot = collect_file_snapshot(old_root)
    new_snapshot = collect_file_snapshot(new_root)
    diff = compare_snapshots(old_snapshot, new_snapshot)
    return {
        "old_root": str(old_root),
        "new_root": str(new_root),
        "old_file_count": len(old_snapshot),
        "new_file_count": len(new_snapshot),
        "old_tree": build_tree(old_root),
        "new_tree": build_tree(new_root),
        "old_snapshot": old_snapshot,
        "new_snapshot": new_snapshot,
        "diff": diff,
    }
