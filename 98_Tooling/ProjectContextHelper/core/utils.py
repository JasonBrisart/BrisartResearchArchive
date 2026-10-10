"""
File: core/utils.py

Purpose
-------
Provide local timestamps, root validation, extension normalization, text reading/redaction, line
  counting, SHA256 hashing, and Markdown language hints.

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
- count_lines: Count splitlines in a UTF-8 replacement-decoded read; return None on any
  exception.
- sha256_file: Stream a binary file in 1 MiB chunks and return its SHA256 hex digest; return
  None on any exception.
- language_hint: Map a lowercased suffix to a Markdown fence language; treat
  .gitignore/.dockerignore and unknown types as text.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
This file imports no other application modules; its implementation uses the standard library.

Consumers in the supplied source:
- cli/cli.py imports normalize_extension.
- core/builder.py imports timestamp_now, timestamp_slug, validate_root.
- core/exporters.py imports language_hint, safe_read.
- core/scanner.py imports count_lines, sha256_file.
- tests/test_export_safety_utilities.py imports normalize_extension, safe_read, sha256_file,
  validate_root.

Settings / parameters
---------------------
safe_read defaults to redaction. The secret regex detects selected assignment-style keywords;
  hashing reads binary data in 1 MiB chunks.

Function signatures (nested callbacks are scoped to their enclosing function):
- timestamp_now() -> str
- timestamp_slug() -> str
- validate_root(root: Path) -> Path
- normalize_extension(value: str) -> str
- safe_read(path: Path, redact_sensitive_lines: bool=True) -> str
- count_lines(path: Path) -> int | None
- sha256_file(path: Path) -> str | None
- language_hint(path: Path) -> str

Module constants and expressions:
- _SECRET_PATTERN = re.compile('(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-
  ]?key|private[_-]?key|client[_-]?secret)\\s*[:=]')

Edge cases
----------
Invalid roots raise FileNotFoundError or NotADirectoryError. UTF-8 decoding errors use
  replacement characters. Read errors return a diagnostic string; hash/line failures return
  None.

safe_read returns a diagnostic string instead of raising for an unreadable file. Replacement
  decoding can alter invalid UTF-8 bytes. Empty files hash normally and have zero splitlines.

Known limitations
-----------------
Redaction is heuristic and applies only to rendered text, not ZIP source files. It can miss
  secrets or redact benign lines. Redacted reads normalize line endings and may remove the final
  newline.

The secret regex is not anchored to the beginning of a line and matches selected keywords
  followed by : or =; it is neither a comprehensive secret detector nor a ZIP sanitizer.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from tempfile import TemporaryDirectory
    from core.utils import normalize_extension, safe_read, sha256_file

    assert normalize_extension(" PY ") == ".py"
    with TemporaryDirectory() as directory:
        path = Path(directory) / "example.txt"
        path.write_text("mode = local\n", encoding="utf-8")
        assert safe_read(path) == "mode = local"
        assert len(sha256_file(path)) == 64
"""

from __future__ import annotations
import datetime
import hashlib
import re
from pathlib import Path

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


def count_lines(path: Path) -> int | None:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except Exception:
        return None


def sha256_file(path: Path) -> str | None:
    try:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None


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

