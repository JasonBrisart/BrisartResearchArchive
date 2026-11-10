"""
File: export/render.py

Purpose
-------
Turn a finished scan into the export's files: PROJECT_CONTEXT.md, the PROJECT_MANIFEST.json
  dictionary, PROJECT_SUMMARY.txt, the source-completeness report, and the optional
  PROJECT_SNAPSHOT.zip. Also owns the text handling only rendering needs: reading captured
  text with optional secret-line redaction, Markdown escaping and fences, and fence language
  hints.

Communication / relationships
-----------------------------
Imports app (attribution and manifest name), export/git_state.py (GitState), export/scan.py
  (ScanResult, build_tree, SOURCE_COMPLETENESS_FAILURE_REASONS), and export/settings.py
  (ScanSettings, AUTO_WORKERS). Imported only by export/pipeline.py, which writes the
  returned text to disk.

Settings / parameters
---------------------
Sections follow the ScanSettings toggles. File contents and ZIP members come from
  ScanResult.captured_paths when present (always, under the pipeline), otherwise from the
  original files. The manifest keeps settings.workers as requested and adds
  summary.capture_workers, the count actually used; the Markdown and summary show both, for
  example "8 (auto)" or "4 (requested 16, limited to available CPU cores)". Redaction replaces
  any line where password, token, secret, api_key, and similar keys are followed by : or =.

Edge cases
----------
An empty scan renders "No files were included." instead of an index table. The Markdown
  skipped-details table is capped at skipped_details_limit (negative values count as zero);
  the manifest always lists every skip. Unreadable text renders a diagnostic line instead of
  raising, and invalid UTF-8 is replaced. Git sections distinguish disabled, not a
  repository, and partially readable.

Known limitations
-----------------
Redaction is heuristic, can miss secrets or hide harmless lines, and applies only to rendered
  text: ZIP members and hashes are the original bytes. Escaping protects Markdown structure; it
  is not a general sanitizer.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from export.settings import settings_for_profile
    from export.scan import collect_included_files
    from export.render import build_manifest

    root = Path("/path/to/project").resolve()
    settings = settings_for_profile("archive")
    scan = collect_included_files(root, settings)
    manifest = build_manifest(root, scan, settings, "example build")
    print(manifest["source_completeness"]["status"], manifest["summary"]["capture_workers"])
"""

from collections import Counter
from dataclasses import asdict
from pathlib import Path
import zipfile

import re

from app import AFFILIATION, APP_NAME, APP_VERSION, AUTHOR, MANIFEST_FILENAME
from export.git_state import GitState
from export.scan import SOURCE_COMPLETENESS_FAILURE_REASONS, ScanResult, build_tree
from export.settings import AUTO_WORKERS, ScanSettings

_SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret)\s*[:=]"
)


def safe_read(path: Path, redact_sensitive_lines: bool = True) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return f"[[Could not read file: {exc}]]"
    except Exception as exc:
        return f"[[Could not read file: {exc}]]"
    if not redact_sensitive_lines:
        return text
    redacted_lines: list[str] = []
    for line in text.splitlines():
        if _SECRET_PATTERN.search(line):
            redacted_lines.append("[[REDACTED POSSIBLE SECRET LINE]]")
        else:
            redacted_lines.append(line)
    return "\n".join(redacted_lines)


def language_hint(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".py": "python", ".json": "json", ".csv": "csv", ".txt": "text",
        ".md": "markdown", ".rst": "rst", ".toml": "toml", ".ini": "ini",
        ".cfg": "ini", ".yaml": "yaml", ".yml": "yaml", ".html": "html",
        ".css": "css", ".js": "javascript", ".jsx": "jsx", ".ts": "typescript",
        ".tsx": "tsx", ".sql": "sql", ".xml": "xml", ".bat": "bat",
        ".ps1": "powershell", ".sh": "bash", ".java": "java", ".c": "c",
        ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".cs": "csharp", ".go": "go",
        ".rs": "rust", ".rb": "ruby", ".php": "php", ".swift": "swift",
        ".kt": "kotlin", ".kts": "kotlin", ".r": "r", ".pl": "perl", ".lua": "lua",
    }
    if path.name.lower() in {".gitignore", ".dockerignore"}:
        return "text"
    return mapping.get(suffix, "text")


def escape_table_cell(value: str) -> str:
    """
    Make a value safe inside a Markdown table cell or `code span`: backticks
    become apostrophes (a backtick would close the span early), pipes are
    escaped, and newlines are flattened.
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


def describe_workers(scan: ScanResult, settings: ScanSettings) -> str:
    used = scan.workers_used
    if settings.workers == AUTO_WORKERS:
        return f"{used} (auto)"
    if settings.workers != used:
        return f"{used} (requested {settings.workers}, limited to available CPU cores)"
    return f"{used} (requested {used})"


def git_state_report(git_state: GitState | None) -> dict | None:
    if git_state is None:
        return None
    return asdict(git_state)


def append_git_state_markdown(chunks: list[str], git_state: GitState | None) -> None:
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
        "affiliation": AFFILIATION, "root": str(root),
        "settings": settings.to_jsonable(),
        "summary": {
            "included_count": len(scan.included_records), "skipped_count": len(scan.skipped_records),
            "included_bytes": scan.total_included_bytes, "capture_workers": scan.workers_used,
        },
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


def source_fence(text: str) -> str:
    """
    Return a backtick fence longer than any backtick run in the text (minimum
    three), so an embedded file containing ``` cannot close its block early.
    """
    longest = 0
    run = 0
    for char in text:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def build_context_markdown(root: Path, scan: ScanResult, settings: ScanSettings, created: str, git_state: GitState | None = None, output_dir: Path | None = None) -> str:
    chunks: list[str] = []
    skip_counts = Counter(r.reason for r in scan.skipped_records)
    chunks.append("# Project Context")
    chunks.append("")
    chunks.append(f"Generated by **{APP_NAME} v{APP_VERSION}**")
    chunks.append(f"Created: `{created}`")
    chunks.append(f"Author: **{AUTHOR}**")
    chunks.append(f"Affiliation: **{AFFILIATION}**")
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
    chunks.append(f"- Capture workers: **{describe_workers(scan, settings)}**")
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
            chunks.append(f"_Skipped details truncated. {remaining} additional skipped files are listed in {MANIFEST_FILENAME}._")
        chunks.append("")
    if settings.include_folder_tree:
        chunks.append("## Folder Tree")
        chunks.append("")
        chunks.append("```text")
        chunks.append(build_tree(root, settings, output_dir))
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
        sources = scan.captured_paths or scan.included_paths
        for path, source in zip(scan.included_paths, sources):
            rel = path.relative_to(root)
            text = safe_read(source, redact_sensitive_lines=settings.redact_sensitive_lines)
            fence = source_fence(text)
            chunks.append(f"### `{escape_table_cell(str(rel))}`")
            chunks.append("")
            chunks.append(f"{fence}{language_hint(path)}")
            chunks.append(text)
            chunks.append(fence)
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
    lines.append(f"Affiliation: {AFFILIATION}")
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
    lines.append(f"Capture workers: {describe_workers(scan, settings)}")
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
        sources = scan.captured_paths or scan.included_paths
        for path, source in zip(scan.included_paths, sources):
            rel = path.relative_to(root)
            archive.write(source, f"project_files/{rel.as_posix()}")
