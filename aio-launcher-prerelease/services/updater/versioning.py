"""
File: services/updater/versioning.py

Purpose
-------
Parse and compare MAJOR.MINOR.PATCH versions and read the installed
version from version.py.

Communication / relationships
-----------------------------
- Used by services/updater/orchestration.py, download.py, install.py,
  and exe_swap.py.
- Reads LOCAL_VERSION_FILE and VERSION_PATTERN from
  services/updater/constants.py.

Settings / parameters
---------------------
- VERSION_PATTERN accepts an optional "v" prefix and any suffix after a
  space or hyphen, for example "0.9.4 ALPHA".
- read_local_version() parses version.py with ast and reads its VERSION
  string literal; the module is never imported, so the value on disk is
  read even after an in-place update in the same process.

Edge cases
----------
- A missing, unparsable, or non-literal VERSION reads as "0.0.0", so any
  remote version appears newer.
- Suffixes are ignored when comparing: "0.9.4 ALPHA" equals "0.9.4".

Known limitations
-----------------
- Pre-release ordering (ALPHA, BETA) is not compared.

Examples
--------
- is_remote_newer("0.9.5", "0.9.4 ALPHA") returns True
- canonical_version("v0.9.4 ALPHA") returns "0.9.4"
"""
from __future__ import annotations

import ast

from collections.abc import Callable
from typing import Any

from services.updater.constants import LOCAL_VERSION_FILE, VERSION_PATTERN


def normalize_version(version_text: Any) -> tuple[int, int, int]:
    value = str(version_text).strip()
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Version must use MAJOR.MINOR.PATCH format: {value!r}")
    return tuple(int(component) for component in match.groups())


def canonical_version(version_text: Any) -> str:
    major, minor, patch = normalize_version(version_text)
    return f"{major}.{minor}.{patch}"


def version_slug(value: str) -> str:
    slug = "".join(c for c in str(value) if c.isalnum() or c in {".", "-", "_"})
    return slug or "latest"


def is_remote_newer(remote_version: Any, local_version: Any) -> bool:
    return normalize_version(remote_version) > normalize_version(local_version)


def default_emit(line: str) -> None:
    print(line)


def version_from_source(source: str) -> str:
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "VERSION" for t in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise ValueError("version.py does not define VERSION as a string literal.")


def read_local_version(emit: Callable[[str], None] = default_emit) -> str:
    if not LOCAL_VERSION_FILE.is_file():
        emit("version.py was not found. Using 0.0.0.")
        return "0.0.0"
    try:
        source = LOCAL_VERSION_FILE.read_text(encoding="utf-8-sig")
        return canonical_version(version_from_source(source))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
        emit(f"version.py is invalid. Using 0.0.0: {exc}")
        return "0.0.0"

