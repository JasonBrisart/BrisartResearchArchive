"""
engine.integrity_check
-----------------------
Verifies a previously created snapshot's manifest against the current
state of the source folder, to confirm preserved files still match what
was recorded (by hash and size) and to flag anything missing or changed
since the snapshot was taken.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .app_info import MANIFEST_FILENAME
from .folder_scanner import sha256_file


def load_manifest(snapshot_dir: Path) -> dict[str, Any]:
    """
    Load a snapshot manifest.
    """

    path = snapshot_dir / MANIFEST_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def verify_snapshot_against_source(snapshot_dir: Path, source_root: Path) -> dict[str, Any]:
    """
    Verify a snapshot's recorded files against the current source folder.

    Returns a dictionary describing:
    - files that still match (hash and size unchanged)
    - files that have changed since the snapshot
    - files that are missing from the source folder
    """

    manifest = load_manifest(snapshot_dir)
    included_files = manifest.get("included_files", [])

    matched: list[str] = []
    changed: list[dict[str, Any]] = []
    missing: list[str] = []

    for record in included_files:
        relative_path = record.get("relative_path", "")
        if not relative_path:
            continue

        source_path = source_root / relative_path

        if not source_path.exists() or not source_path.is_file():
            missing.append(relative_path)
            continue

        recorded_hash = record.get("sha256")
        recorded_size = record.get("size_bytes")

        try:
            current_size = source_path.stat().st_size
        except OSError:
            missing.append(relative_path)
            continue

        current_hash = sha256_file(source_path) if recorded_hash else None

        if recorded_hash and current_hash != recorded_hash:
            changed.append(
                {
                    "relative_path": relative_path,
                    "recorded_sha256": recorded_hash,
                    "current_sha256": current_hash,
                    "recorded_size_bytes": recorded_size,
                    "current_size_bytes": current_size,
                }
            )
        elif not recorded_hash and current_size != recorded_size:
            changed.append(
                {
                    "relative_path": relative_path,
                    "recorded_sha256": recorded_hash,
                    "current_sha256": current_hash,
                    "recorded_size_bytes": recorded_size,
                    "current_size_bytes": current_size,
                }
            )
        else:
            matched.append(relative_path)

    return {
        "snapshot_dir": str(snapshot_dir),
        "source_root": str(source_root),
        "created": manifest.get("created", ""),
        "archive_name": manifest.get("archive_name", ""),
        "total_recorded": len(included_files),
        "matched_count": len(matched),
        "changed_count": len(changed),
        "missing_count": len(missing),
        "matched": matched,
        "changed": changed,
        "missing": missing,
    }


def build_verify_report(result: dict[str, Any]) -> str:
    """
    Build a human-readable verification report.
    """

    lines: list[str] = []

    lines.append("# Archive Snapshot Verification Report")
    lines.append("")
    lines.append(f"Snapshot: `{result.get('snapshot_dir', '')}`")
    lines.append(f"Source folder: `{result.get('source_root', '')}`")
    lines.append(f"Snapshot created: `{result.get('created', '')}`")
    lines.append(f"Archive name: `{result.get('archive_name', '')}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Recorded files: `{result.get('total_recorded', 0)}`")
    lines.append(f"- Matched (unchanged): `{result.get('matched_count', 0)}`")
    lines.append(f"- Changed since snapshot: `{result.get('changed_count', 0)}`")
    lines.append(f"- Missing from source: `{result.get('missing_count', 0)}`")
    lines.append("")

    lines.append("## Changed Files")
    lines.append("")
    changed = result.get("changed", [])
    if changed:
        for item in changed:
            lines.append(f"- `{item.get('relative_path', '')}`")
    else:
        lines.append("- No changed files detected.")
    lines.append("")

    lines.append("## Missing Files")
    lines.append("")
    missing = result.get("missing", [])
    if missing:
        for path in missing:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No missing files detected.")
    lines.append("")

    lines.append("## Verification Notes")
    lines.append("")
    if result.get("changed_count", 0) == 0 and result.get("missing_count", 0) == 0:
        lines.append(
            "All recorded files were found in the source folder and match "
            "the hashes and sizes captured at snapshot time."
        )
    else:
        lines.append(
            "Some recorded files differ from or are missing in the current "
            "source folder. Review the lists above before relying on this "
            "snapshot as an exact historical match."
        )

    return "\n".join(lines)