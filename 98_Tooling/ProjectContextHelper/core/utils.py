"""
File: core/utils.py

Purpose
-------
Provide local timestamps, root validation, extension normalization, text reading/redaction, CPU
  core detection with capture-thread resolution, and Markdown language hints.

Implemented responsibilities:
- timestamp_now: Return a local timezone-aware timestamp string including the numeric UTC offset
  for export records.
- timestamp_slug: Return a local second-resolution YYYYMMDD_HHMMSS string for export folder
  names.
- validate_root: Expand user-home notation, resolve the path, reject missing/non-directory
  roots, and return the resolved directory.
- normalize_extension: Trim/lowercase a string and prepend a dot if needed; an empty input
  remains empty.
- safe_read: Read UTF-8 text, retry decoding failures with replacement, return diagnostic text
  for read failures, and optionally replace whole assignment-like secret lines.
- detect_cpu_cores: Return the number of logical CPU cores available to this process (at least
  1), preferring affinity-aware counts over the machine-wide count.
- worker_limit: Return the highest selectable capture-thread count: detected cores, capped at
  MAX_WORKERS.
- resolve_workers: Turn a requested workers value into the thread count to run: AUTO_WORKERS
  becomes worker_limit(); an explicit number is clamped to 1..worker_limit().
- language_hint: Map a lowercased suffix to a Markdown fence language; treat
  .gitignore/.dockerignore and unknown types as text.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: AUTO_WORKERS, MAX_WORKERS.

Consumers in the supplied source:
- cli/cli.py imports normalize_extension.
- core/builder.py imports timestamp_now, timestamp_slug, validate_root.
- core/exporters.py imports language_hint, safe_read.
- core/scanner.py imports resolve_workers.
- gui/builders.py imports detect_cpu_cores, worker_limit.
- tests/test_export_safety_utilities.py imports normalize_extension, safe_read, validate_root.
- tests/test_v4_engine.py patches detect_cpu_cores and calls resolve_workers.

Settings / parameters
---------------------
safe_read defaults to redaction. The secret regex detects selected assignment-style keywords.
  resolve_workers and worker_limit accept an optional cores value so callers that already
  detected the core count (the GUI, tests) do not detect it again.

Function signatures (nested callbacks are scoped to their enclosing function):
- timestamp_now() -> str
- timestamp_slug() -> str
- validate_root(root: Path) -> Path
- normalize_extension(value: str) -> str
- safe_read(path: Path, redact_sensitive_lines: bool=True) -> str
- detect_cpu_cores() -> int
- worker_limit(cores: int | None=None) -> int
- resolve_workers(requested: int | str, cores: int | None=None) -> int
- language_hint(path: Path) -> str

Module constants and expressions:
- _SECRET_PATTERN = re.compile('(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-
  ]?key|private[_-]?key|client[_-]?secret)\\s*[:=]')

Edge cases
----------
Invalid roots raise FileNotFoundError or NotADirectoryError. UTF-8 decoding errors use
  replacement characters. Read errors return a diagnostic string instead of raising.

A platform that cannot report its core count yields 1, never 0 or None. An explicit workers
  value above the detected cores is clamped down (a profile saved on a 16-core machine runs with
  4 threads on a 4-core one); a value below 1 is raised to 1. resolve_workers does not validate
  types: core.builder.validate_settings rejects anything other than 'auto' or 1..MAX_WORKERS
  before a build starts.

Known limitations
-----------------
Redaction is heuristic and applies only to rendered text, not ZIP source files. It can miss
  secrets or redact benign lines. Redacted reads normalize line endings and may remove the final
  newline.

The secret regex is not anchored to the beginning of a line and matches selected keywords
  followed by : or =; it is neither a comprehensive secret detector nor a ZIP sanitizer.

Core counts are logical processors (hyper-threads count individually), not physical cores. On
  Windows and macOS before Python 3.13, the count is machine-wide and ignores CPU affinity.

v4.1.0 removed count_lines() and sha256_file(): since v4.0.0 the scanner computes line counts and
  hashes from its single captured read, and nothing in the application called them.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from tempfile import TemporaryDirectory
    from core.utils import normalize_extension, resolve_workers, safe_read

    assert normalize_extension(" PY ") == ".py"
    assert resolve_workers("auto", cores=8) == 8
    assert resolve_workers(16, cores=4) == 4
    with TemporaryDirectory() as directory:
        path = Path(directory) / "example.txt"
        path.write_text("mode = local\n", encoding="utf-8")
        assert safe_read(path) == "mode = local"
"""

from __future__ import annotations
import datetime
import os
import re
from pathlib import Path

from core.constants import AUTO_WORKERS, MAX_WORKERS

_SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret)\s*[:=]"
)


def timestamp_now() -> str:
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def timestamp_slug() -> str:
    return datetime.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def validate_root(root: Path) -> Path:
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Project folder does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Selected path is not a folder: {root}")
    return root


def normalize_extension(value: str) -> str:
    value = value.strip().lower()
    if not value:
        return value
    if value.startswith("."):
        return value
    return f".{value}"


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


def detect_cpu_cores() -> int:
    """
    Logical CPU cores this process may run on. Python 3.13+ provides
    os.process_cpu_count(), which honours CPU affinity; on older versions
    sched_getaffinity() gives the same answer on Linux, and os.cpu_count()
    (the whole machine) is the fallback elsewhere, including Windows.
    """
    counter = getattr(os, "process_cpu_count", None)
    if counter is not None:
        count = counter()
    elif hasattr(os, "sched_getaffinity"):
        try:
            count = len(os.sched_getaffinity(0))
        except OSError:
            count = os.cpu_count()
    else:
        count = os.cpu_count()
    return max(1, count or 1)


def worker_limit(cores: int | None = None) -> int:
    return min(cores if cores is not None else detect_cpu_cores(), MAX_WORKERS)


def resolve_workers(requested: int | str, cores: int | None = None) -> int:
    limit = worker_limit(cores)
    if requested == AUTO_WORKERS:
        return limit
    return max(1, min(int(requested), limit))


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

