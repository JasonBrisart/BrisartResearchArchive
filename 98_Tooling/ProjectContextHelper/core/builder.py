"""
File: core/builder.py

Purpose
-------
Orchestrate root validation, optional Git inspection, scanning, output rendering, ZIP creation,
  and best-effort export history recording.

Implemented responsibilities:
- create_context: Resolve/validate root; inspect Git when requested; create output paths; scan;
  write context, manifest, summary, and settings; optionally ZIP original sources; append best-
  effort history; return BuildResult.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: CONTEXT_FILENAME, MANIFEST_FILENAME, SETTINGS_FILENAME, SNAPSHOT_FILENAME,
  SUMMARY_FILENAME.
- core.exporters: build_manifest, build_context_markdown, build_summary_text,
  create_snapshot_zip.
- core.git_state: build_git_state.
- services.storage: HistoryEntry, append_history_entry.
- core.models: BuildResult, ScanSettings.
- core.scanner: collect_included_files.
- core.utils: timestamp_now, timestamp_slug, validate_root.

Consumers in the supplied source:
- cli/cli.py imports create_context.
- gui/builders.py imports create_context.

Settings / parameters
---------------------
Accepts a root Path and optional ScanSettings; returns BuildResult. Omitting settings constructs
  ScanSettings directly, not the archive preset.

Function signatures (nested callbacks are scoped to their enclosing function):
- create_context(root: Path, settings: ScanSettings | None=None) -> BuildResult

Edge cases
----------
Validates the root before building. History-write failures are suppressed after export creation.
  A completeness failure stops rendering, although the output directory may already exist.

A configured absolute output_dir_name or parent traversal is not rejected here. The output
  directory is created before scanning; custom output directory names are not automatically
  added to exclusions. Two builds in the same second can reuse a timestamped directory.

Known limitations
-----------------
Outputs are written sequentially, not transactionally. Files can change between scanning,
  rendering, and ZIP creation. Timestamp folder names have one-second resolution.

The default ScanSettings() has empty extension sets, so a direct create_context(root) call is
  not equivalent to an interface archive export. History is stored beside the application, not
  in the selected project root.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from core.builder import create_context
    from core.constants import settings_for_profile

    settings = settings_for_profile("archive")
    settings.include_snapshot_zip = False
    result = create_context(Path("/path/to/project"), settings)
    print(result.context_path, result.included_count)
"""

from pathlib import Path
import json

from core.constants import (
    CONTEXT_FILENAME,
    MANIFEST_FILENAME,
    SETTINGS_FILENAME,
    SNAPSHOT_FILENAME,
    SUMMARY_FILENAME,
)
from core.exporters import (
    build_manifest,
    build_context_markdown,
    build_summary_text,
    create_snapshot_zip,
)
from core.git_state import build_git_state
from services.storage import (
    HistoryEntry,
    append_history_entry,
)
from core.models import (
    BuildResult,
    ScanSettings,
)
from core.scanner import collect_included_files
from core.utils import (
    timestamp_now,
    timestamp_slug,
    validate_root,
)


def create_context(root: Path, settings: ScanSettings | None = None) -> BuildResult:
    root = validate_root(root)
    settings = settings or ScanSettings()
    created = timestamp_now()

    git_state = None
    if settings.include_git_state:
        git_state = build_git_state(
            root, exclude_dirs=settings.exclude_dirs,
            exclude_files=settings.exclude_files, commit_limit=settings.git_state_commit_limit,
        )

    base_export_dir = root / settings.output_dir_name
    if settings.timestamped_export_folder:
        export_dir = base_export_dir / f"project_context_{timestamp_slug()}"
    else:
        export_dir = base_export_dir
    export_dir.mkdir(parents=True, exist_ok=True)

    context_path = export_dir / CONTEXT_FILENAME
    manifest_path = export_dir / MANIFEST_FILENAME
    summary_path = export_dir / SUMMARY_FILENAME
    settings_path = export_dir / SETTINGS_FILENAME
    snapshot_path = export_dir / SNAPSHOT_FILENAME if settings.include_snapshot_zip else None

    scan = collect_included_files(root, settings)

    context_text = build_context_markdown(root=root, scan=scan, settings=settings, created=created, git_state=git_state)
    context_path.write_text(context_text, encoding="utf-8")

    manifest = build_manifest(root=root, scan=scan, settings=settings, created=created, git_state=git_state)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary_text = build_summary_text(root=root, scan=scan, settings=settings, created=created, git_state=git_state)
    summary_path.write_text(summary_text, encoding="utf-8")

    settings_path.write_text(json.dumps(settings.to_jsonable(), indent=2), encoding="utf-8")

    if snapshot_path is not None:
        create_snapshot_zip(
            zip_path=snapshot_path, context_path=context_path, manifest_path=manifest_path,
            summary_path=summary_path, settings_path=settings_path, scan=scan, root=root,
        )

    result = BuildResult(
        export_dir=export_dir, context_path=context_path, manifest_path=manifest_path,
        summary_path=summary_path, settings_path=settings_path, snapshot_path=snapshot_path,
        included_count=len(scan.included_records), skipped_count=len(scan.skipped_records),
        total_included_bytes=scan.total_included_bytes,
        git_branch=(git_state.branch if git_state else None),
        git_commit_short=(git_state.head_commit_short if git_state else None),
        git_is_dirty=(git_state.is_dirty if git_state else None),
    )

    try:
        append_history_entry(HistoryEntry(
            created=created, root=str(root), profile=settings.profile, export_dir=str(export_dir),
            included_count=result.included_count, skipped_count=result.skipped_count,
            total_included_bytes=result.total_included_bytes,
            git_branch=result.git_branch or "", git_commit_short=result.git_commit_short or "",
        ))
    except Exception:
        pass

    return result

