"""
engine.change_report
--------------------
Compares two snapshot manifests and builds a Markdown change report
describing added, removed, modified, and unchanged files.

The comparison also records whether both snapshots carried SHA256 hashes.
When either snapshot was created with hashing disabled, the diff falls
back to size-only detection, which can miss an edit that leaves a file's
size unchanged. The report discloses this explicitly so it never
overstates its own confidence.
"""
from __future__ import annotations

import json
from pathlib import Path

from .app_info import MANIFEST_FILENAME


def load_manifest(snapshot_dir: Path) -> dict:
    """
    Load a snapshot manifest.
    """
    path = snapshot_dir / MANIFEST_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def file_map(manifest: dict) -> dict[str, dict]:
    """
    Convert included files into a relative-path map.
    """
    return {
        item.get("relative_path", ""): item
        for item in manifest.get("included_files", [])
        if item.get("relative_path")
    }


def manifest_has_hashes(manifest: dict) -> bool:
    """
    Return True if this snapshot can be compared by hash.

    Prefers the recorded include_hashes setting, then falls back to
    checking whether the included files actually carry sha256 values. An
    empty snapshot is treated as hashed, since there is nothing whose
    change could be silently missed.
    """
    settings = manifest.get("settings")
    if isinstance(settings, dict) and "include_hashes" in settings:
        return bool(settings["include_hashes"])
    included = manifest.get("included_files", [])
    if not included:
        return True
    return all(item.get("sha256") for item in included)


def compare_manifests(old_manifest: dict, new_manifest: dict) -> dict:
    """
    Compare two archive manifests.
    """
    old_files = file_map(old_manifest)
    new_files = file_map(new_manifest)

    old_paths = set(old_files)
    new_paths = set(new_files)

    added = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)
    shared = sorted(old_paths.intersection(new_paths))

    modified = []
    unchanged = []

    for path in shared:
        old_item = old_files[path]
        new_item = new_files[path]

        old_hash = old_item.get("sha256")
        new_hash = new_item.get("sha256")
        old_size = old_item.get("size_bytes")
        new_size = new_item.get("size_bytes")

        if old_hash != new_hash or old_size != new_size:
            modified.append(path)
        else:
            unchanged.append(path)

    hash_comparison = (
        manifest_has_hashes(old_manifest) and manifest_has_hashes(new_manifest)
    )

    return {
        "old_created": old_manifest.get("created", ""),
        "new_created": new_manifest.get("created", ""),
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged_count": len(unchanged),
        "added_count": len(added),
        "removed_count": len(removed),
        "modified_count": len(modified),
        "hash_comparison": hash_comparison,
    }


def compare_snapshot_dirs(old_snapshot_dir: Path, new_snapshot_dir: Path) -> dict:
    """
    Compare two snapshot directories.
    """
    old_manifest = load_manifest(old_snapshot_dir)
    new_manifest = load_manifest(new_snapshot_dir)
    result = compare_manifests(old_manifest, new_manifest)
    result["old_snapshot_dir"] = str(old_snapshot_dir)
    result["new_snapshot_dir"] = str(new_snapshot_dir)
    return result


def build_diff_markdown(diff: dict) -> str:
    """
    Build Markdown diff report.
    """
    lines: list[str] = []
    lines.append("# Archive Snapshot Change Report")
    lines.append("")
    lines.append(f"Old snapshot: `{diff.get('old_snapshot_dir', '')}`")
    lines.append(f"New snapshot: `{diff.get('new_snapshot_dir', '')}`")
    lines.append("")

    if not diff.get("hash_comparison", True):
        lines.append(
            "> WARNING: Hash comparison unavailable for one or both "
            "snapshots. Changes were detected by file size only, so an edit "
            "that leaves a file's size unchanged may not appear as modified. "
            "Re-create the snapshots with SHA256 hashes enabled for a "
            "byte-level comparison."
        )
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Added files: `{diff.get('added_count', 0)}`")
    lines.append(f"- Removed files: `{diff.get('removed_count', 0)}`")
    lines.append(f"- Modified files: `{diff.get('modified_count', 0)}`")
    lines.append(f"- Unchanged files: `{diff.get('unchanged_count', 0)}`")
    lines.append(
        f"- Comparison method: "
        f"`{'sha256 + size' if diff.get('hash_comparison', True) else 'size only'}`"
    )
    lines.append("")

    lines.append("## Added Files")
    lines.append("")
    if diff.get("added"):
        for path in diff["added"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No added files.")
    lines.append("")

    lines.append("## Removed Files")
    lines.append("")
    if diff.get("removed"):
        for path in diff["removed"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No removed files.")
    lines.append("")

    lines.append("## Modified Files")
    lines.append("")
    if diff.get("modified"):
        for path in diff["modified"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No modified files.")

    return "\n".join(lines)
