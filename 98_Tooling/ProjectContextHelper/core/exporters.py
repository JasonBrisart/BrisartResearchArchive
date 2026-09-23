from collections import Counter
from dataclasses import asdict
from pathlib import Path
import zipfile

from core.constants import (
    APP_NAME,
    APP_VERSION,
    AUTHOR,
    REPOSITORY_NAME,
    REPOSITORY_URL,
)
from core.git_state import GitState
from core.models import (
    ScanResult,
    ScanSettings,
)
from core.scanner import (
    SOURCE_COMPLETENESS_FAILURE_REASONS,
    build_tree,
)
from core.utils import (
    language_hint,
    safe_read,
)


def escape_table_cell(value: str) -> str:
    """
    Escape a value for safe placement inside a Markdown pipe-table
    cell, AND/OR inside a single-backtick inline code span (every
    call site in this module does one or both of these immediately
    after calling this function).
    Bugfix (v3.1.2): this function already escaped `|` (pipe) and
    collapsed embedded newlines, but did not escape backticks. Every
    call site wraps its result in a single pair of backticks
    (e.g. f"`{path_cell}`") to render it as inline code -- but if the
    original value itself contains a literal backtick (a valid
    filename character on Linux/macOS, e.g. "weird`file.py", and also
    a completely ordinary character to find inside a real git commit
    message, e.g. "Fix `foo()` bug"), that backtick prematurely closes
    the intended code span. Everything between the embedded backtick
    and the next backtick in the line renders as literal, unescaped
    Markdown instead of inert code text -- which, worse, undoes the
    protection this function was already providing against pipe
    characters, since a pipe that escapes the (now prematurely closed)
    code span is no longer inside a context where `\\|` reads as
    intended. Backticks are replaced with a single quote, consistent
    with this function's existing philosophy of prioritizing rendered
    output correctness over perfect character fidelity for values
    that were always going to be adversarial edge cases anyway.
    """
    return (
        value.replace("`", "'")
        .replace("|", "\\|")
        .replace("\n", " ")
        .replace("\r", "")
    )


def source_completeness_report(scan: ScanResult, settings: ScanSettings) -> dict:
    failures = [r for r in scan.skipped_records if r.reason in SOURCE_COMPLETENESS_FAILURE_REASONS]
    included_count = len(scan.included_records)
    failed_count = len(failures)
    status = "PASS" if failed_count == 0 else "FAIL"
    return {
        "required": settings.require_complete_source, "status": status,
        "included_source_files": included_count, "missing_or_blocked_source_files": failed_count,
        "failure_reasons": sorted(SOURCE_COMPLETENESS_FAILURE_REASONS),
        "failures": [asdict(r) for r in failures],
    }


def git_state_report(git_state: GitState | None) -> dict | None:
    if git_state is None:
        return None
    return asdict(git_state)


def append_git_state_markdown(chunks: list[str], git_state: GitState | None) -> None:
    """
    Bugfix (v3.1.2): the modified/untracked file paths and recent
    commit summaries rendered here were previously placed directly
    inside single backticks with NO escaping at all (unlike every
    table in this module, which at least escaped pipes/newlines even
    before this fix). A commit subject line containing a backtick --
    an extremely common, completely ordinary thing to find in a real
    commit message (e.g. "Fix `foo()` bug") -- would break the
    rendered bullet list. Both are now passed through
    escape_table_cell(), consistent with everywhere else in this
    module that wraps a value in backticks.
    """
    chunks.append("## Git State")
    chunks.append("")
    if git_state is None:
        chunks.append("_Git state detection was disabled for this build._")
        chunks.append("")
        return
    if not git_state.is_git_repo:
        chunks.append("_No `.git` directory was found under the project root; this project is not tracked by git, or the export was run against a subfolder that does not contain it._")
        chunks.append("")
        return
    chunks.append(f"- Branch: **{git_state.branch or '(detached HEAD)'}**")
    chunks.append(f"- HEAD commit: `{git_state.head_commit or 'unknown'}`")
    if git_state.is_dirty is None:
        dirty_display = f"**unknown** ({git_state.dirty_status})"
    elif git_state.is_dirty:
        dirty_display = f"**True** ({git_state.dirty_status})"
    else:
        dirty_display = f"**False** ({git_state.dirty_status})"
    chunks.append(f"- Working tree dirty: {dirty_display}")
    chunks.append(f"- Modified/deleted files vs HEAD: **{len(git_state.modified_files)}**")
    chunks.append(f"- Untracked files: **{len(git_state.untracked_files)}**")
    chunks.append("")
    if git_state.modified_files or git_state.untracked_files:
        if git_state.modified_files:
            chunks.append("**Modified or deleted since HEAD:**")
            chunks.append("")
            for path in git_state.modified_files:
                chunks.append(f"- `{escape_table_cell(path)}`")
            chunks.append("")
        if git_state.untracked_files:
            chunks.append("**Untracked:**")
            chunks.append("")
            for path in git_state.untracked_files:
                chunks.append(f"- `{escape_table_cell(path)}`")
            chunks.append("")
    if git_state.recent_commits:
        chunks.append("**Recent commits (HEAD first):**")
        chunks.append("")
        for commit_line in git_state.recent_commits:
            chunks.append(f"- `{escape_table_cell(commit_line)}`")
        chunks.append("")
    if git_state.warnings:
        chunks.append("> **Note:** git state detection was only partially possible for this repository:")
        for warning in git_state.warnings:
            chunks.append(f"> - {warning}")
        chunks.append("")


def build_manifest(root: Path, scan: ScanResult, settings: ScanSettings, created: str, git_state: GitState | None = None) -> dict:
    return {
        "created": created, "app_name": APP_NAME, "version": APP_VERSION, "author": AUTHOR,
        "repository_name": REPOSITORY_NAME, "repository_url": REPOSITORY_URL, "root": str(root),
        "settings": settings.to_jsonable(),
        "summary": {"included_count": len(scan.included_records), "skipped_count": len(scan.skipped_records), "included_bytes": scan.total_included_bytes},
        "source_completeness": source_completeness_report(scan, settings),
        "git_state": git_state_report(git_state),
        "included_files": [asdict(r) for r in scan.included_records],
        "skipped_files": [asdict(r) for r in scan.skipped_records],
    }


def append_source_completeness_markdown(chunks: list[str], scan: ScanResult, settings: ScanSettings) -> None:
    report = source_completeness_report(scan, settings)
    chunks.append("## Source Completeness Check")
    chunks.append("")
    chunks.append(f"- Requirement enabled: **{report['required']}**")
    chunks.append(f"- Status: **{report['status']}**")
    chunks.append(f"- Included source files: **{report['included_source_files']}**")
    chunks.append(f"- Missing or blocked source files: **{report['missing_or_blocked_source_files']}**")
    chunks.append("")
    if report["status"] == "PASS":
        chunks.append("Result: **PASS** — every eligible source/text file that matched the active profile was included.")
        chunks.append("")
        return
    chunks.append("Result: **FAIL** — one or more eligible source/text files could not be preserved.")
    chunks.append("")
    chunks.append("| File | Reason | Bytes |")
    chunks.append("|---|---|---:|")
    for failure in report["failures"]:
        size = failure.get("size_bytes")
        size_display = "" if size is None else str(size)
        path_cell = escape_table_cell(failure['relative_path'])
        reason_cell = escape_table_cell(failure['reason'])
        chunks.append(f"| `{path_cell}` | `{reason_cell}` | {size_display} |")
    chunks.append("")


def build_context_markdown(root: Path, scan: ScanResult, settings: ScanSettings, created: str, git_state: GitState | None = None) -> str:
    chunks: list[str] = []
    skip_counts = Counter(r.reason for r in scan.skipped_records)
    chunks.append("# Project Context")
    chunks.append("")
    chunks.append(f"Generated by **{APP_NAME} v{APP_VERSION}**")
    chunks.append(f"Created: `{created}`")
    chunks.append(f"Author: **{AUTHOR}**")
    chunks.append(f"Repository: {REPOSITORY_URL}")
    chunks.append(f"Root: `{root}`")
    chunks.append(f"Profile: `{settings.profile}`")
    chunks.append(f"Redaction enabled: `{settings.redact_sensitive_lines}`")
    chunks.append("")
    chunks.append("## Export Summary")
    chunks.append("")
    chunks.append(f"- Included files: **{len(scan.included_records)}**")
    chunks.append(f"- Skipped files: **{len(scan.skipped_records)}**")
    chunks.append(f"- Included bytes: **{scan.total_included_bytes}**")
    chunks.append(f"- Max file bytes: **{settings.max_file_bytes}**")
    chunks.append(f"- Max total bytes: **{settings.max_total_bytes}**")
    chunks.append(f"- Snapshot ZIP enabled: **{settings.include_snapshot_zip}**")
    chunks.append(f"- Hashes enabled: **{settings.include_hashes}**")
    chunks.append(f"- Line counts enabled: **{settings.include_line_counts}**")
    chunks.append(f"- Complete source required: **{settings.require_complete_source}**")
    chunks.append("")
    if settings.include_git_state:
        append_git_state_markdown(chunks, git_state)
    append_source_completeness_markdown(chunks, scan, settings)
    if skip_counts:
        chunks.append("## Skip Reason Summary")
        chunks.append("")
        for reason, count in sorted(skip_counts.items()):
            chunks.append(f"- `{escape_table_cell(reason)}`: {count}")
        chunks.append("")
    if settings.include_skipped_details and scan.skipped_records:
        chunks.append("## Skipped File Details")
        chunks.append("")
        limit = max(0, settings.skipped_details_limit)
        visible_records = scan.skipped_records[:limit]
        chunks.append("| File | Reason | Bytes |")
        chunks.append("|---|---|---:|")
        for record in visible_records:
            size_display = "" if record.size_bytes is None else str(record.size_bytes)
            path_cell = escape_table_cell(record.relative_path)
            reason_cell = escape_table_cell(record.reason)
            chunks.append(f"| `{path_cell}` | `{reason_cell}` | {size_display} |")
        remaining = len(scan.skipped_records) - len(visible_records)
        if remaining > 0:
            chunks.append("")
            chunks.append(f"_Skipped details truncated. {remaining} additional skipped files are listed in PROJECT_MANIFEST.json._")
        chunks.append("")
    if settings.include_folder_tree:
        chunks.append("## Folder Tree")
        chunks.append("")
        chunks.append("```text")
        chunks.append(build_tree(root, settings))
        chunks.append("```")
        chunks.append("")
    if settings.include_file_index:
        chunks.append("## File Index")
        chunks.append("")
        if scan.included_records:
            headers = ["File", "Bytes"]
            if settings.include_line_counts:
                headers.append("Lines")
            if settings.include_hashes:
                headers.append("SHA256")
            chunks.append("| " + " | ".join(headers) + " |")
            alignment = ["---:" if h in {"Bytes", "Lines"} else "---" for h in headers]
            chunks.append("| " + " | ".join(alignment) + " |")
            for record in scan.included_records:
                path_cell = escape_table_cell(record.relative_path)
                cells = [f"`{path_cell}`", str(record.size_bytes)]
                if settings.include_line_counts:
                    cells.append("" if record.line_count is None else str(record.line_count))
                if settings.include_hashes:
                    cells.append(f"`{record.sha256}`" if record.sha256 else "")
                chunks.append("| " + " | ".join(cells) + " |")
            chunks.append("")
        else:
            chunks.append("_No files were included._")
            chunks.append("")
    if settings.include_file_contents:
        chunks.append("## Included File Contents")
        chunks.append("")
        for path in scan.included_paths:
            rel = path.relative_to(root)
            chunks.append(f"### `{rel}`")
            chunks.append("")
            chunks.append(f"```{language_hint(path)}")
            chunks.append(safe_read(path, redact_sensitive_lines=settings.redact_sensitive_lines))
            chunks.append("```")
            chunks.append("")
    return "\n".join(chunks)


def build_summary_text(root: Path, scan: ScanResult, settings: ScanSettings, created: str, git_state: GitState | None = None) -> str:
    extension_counts = Counter(r.extension for r in scan.included_records)
    skip_counts = Counter(r.reason for r in scan.skipped_records)
    report = source_completeness_report(scan, settings)
    lines: list[str] = []
    lines.append(f"{APP_NAME} v{APP_VERSION}")
    lines.append(f"Created: {created}")
    lines.append(f"Author: {AUTHOR}")
    lines.append(f"Repository: {REPOSITORY_URL}")
    lines.append(f"Root: {root}")
    lines.append(f"Profile: {settings.profile}")
    lines.append("")
    lines.append("Settings")
    lines.append("--------")
    lines.append(f"Snapshot ZIP: {settings.include_snapshot_zip}")
    lines.append(f"Redaction: {settings.redact_sensitive_lines}")
    lines.append(f"Hashes: {settings.include_hashes}")
    lines.append(f"Line counts: {settings.include_line_counts}")
    lines.append(f"Folder tree: {settings.include_folder_tree}")
    lines.append(f"File index: {settings.include_file_index}")
    lines.append(f"File contents: {settings.include_file_contents}")
    lines.append(f"Complete source required: {settings.require_complete_source}")
    lines.append("")
    if settings.include_git_state:
        lines.append("Git State")
        lines.append("---------")
        if git_state is None or not git_state.is_git_repo:
            lines.append("Repository: not detected")
        else:
            lines.append(f"Branch: {git_state.branch or '(detached HEAD)'}")
            lines.append(f"HEAD commit: {git_state.head_commit or 'unknown'}")
            lines.append(f"Dirty: {git_state.is_dirty} ({git_state.dirty_status})")
            lines.append(f"Modified/deleted files: {len(git_state.modified_files)}")
            lines.append(f"Untracked files: {len(git_state.untracked_files)}")
        lines.append("")
    lines.append("Summary")
    lines.append("-------")
    lines.append(f"Included files: {len(scan.included_records)}")
    lines.append(f"Skipped files: {len(scan.skipped_records)}")
    lines.append(f"Included bytes: {scan.total_included_bytes}")
    lines.append("")
    lines.append("Source Completeness")
    lines.append("-------------------")
    lines.append(f"Status: {report['status']}")
    lines.append(f"Included source files: {report['included_source_files']}")
    lines.append(f"Missing or blocked source files: {report['missing_or_blocked_source_files']}")
    lines.append("")
    lines.append("Extensions")
    lines.append("----------")
    for ext, count in sorted(extension_counts.items()):
        lines.append(f"{ext}: {count}")
    lines.append("")
    lines.append("Skip Reasons")
    lines.append("------------")
    for reason, count in sorted(skip_counts.items()):
        lines.append(f"{reason}: {count}")
    return "\n".join(lines)


def create_snapshot_zip(zip_path: Path, context_path: Path, manifest_path: Path, summary_path: Path, settings_path: Path, scan: ScanResult, root: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(context_path, context_path.name)
        archive.write(manifest_path, manifest_path.name)
        archive.write(summary_path, summary_path.name)
        archive.write(settings_path, settings_path.name)
        for path in scan.included_paths:
            rel = path.relative_to(root)
            archive.write(path, f"project_files/{rel.as_posix()}")
