r"""
File: brisart_ai/native_path.py

Purpose
-------
Resolve the shared native modules before startup without vendoring them in
Offline_AI.

Communication / relationships
-----------------------------
The launchers, test runner and replay scripts call install() before loading
application modules that use flat brisart_* imports. No API code lives here.

Settings / parameters
---------------------
BRISART_NATIVE_API, if set, names the external directory containing all
seven modules. Otherwise ancestors are checked for 94_Native_API's, preferring
its Official subfolder before the folder itself. Older folder spellings are
also recognized.

Edge cases
----------
An invalid override fails without searching elsewhere. Incomplete candidates
are skipped. Resolved paths inside Offline_AI cannot supply the modules.

Known limitations
-----------------
The loader checks location and file presence, not API version compatibility.

Examples
--------
In the Archive layout, run python cli.py counts with 94_Native_API's at the
repository root. For a detached checkout, set BRISART_NATIVE_API explicitly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Mapping, Optional

ENV_VAR = "BRISART_NATIVE_API"
ARCHIVE_DIRNAMES = ("94_Native_API's", "94_native apis", "94_Native_APIs", "94_Native_API")
ARCHIVE_SUBDIR = "Official"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = (
    "brisart_codec.py",
    "brisart_hash.py",
    "brisart_inflate.py",
    "brisart_json.py",
    "brisart_markup.py",
    "brisart_robots.py",
    "brisart_url.py",
)


def _is_external_stack(directory: Path, project_root: Path) -> bool:
    return (
        directory.is_dir()
        and not directory.is_relative_to(project_root)
        and all(
            (directory / name).is_file()
            and not (directory / name).resolve().is_relative_to(project_root)
            for name in REQUIRED_MODULES
        )
    )


def _archive_candidates(project_root: Path) -> List[Path]:
    return [
        directory
        for parent in project_root.parents
        for name in ARCHIVE_DIRNAMES
        for directory in (parent / name / ARCHIVE_SUBDIR, parent / name)
    ]


def find_native_dir(
    project_root: Path = PROJECT_ROOT,
    environ: Optional[Mapping[str, str]] = None,
) -> Path:
    """Return the folder that holds the Brisart native stack for this checkout."""
    project_root = Path(project_root).resolve()
    env = os.environ if environ is None else environ
    override = str(env.get(ENV_VAR, "")).strip()
    if override:
        chosen = Path(override).expanduser().resolve()
        if not _is_external_stack(chosen, project_root):
            raise ImportError(
                f"{ENV_VAR} points at {chosen}, which must be outside Offline_AI and contain "
                f"all of: {', '.join(REQUIRED_MODULES)}."
            )
        return chosen
    candidates = _archive_candidates(project_root)
    for candidate in candidates:
        resolved = candidate.resolve()
        if _is_external_stack(resolved, project_root):
            return resolved
    searched = "\n  ".join(str(candidate) for candidate in candidates)
    raise ImportError(
        "Could not find the Brisart native stack. Looked for a folder containing "
        f"{', '.join(REQUIRED_MODULES)} in:\n  {searched}\n"
        f"Set {ENV_VAR} to the folder, or run from the Archive layout."
    )


def install(
    project_root: Path = PROJECT_ROOT,
    environ: Optional[Mapping[str, str]] = None,
) -> Path:
    """Put the native stack folder on sys.path (once) and return it."""
    chosen = find_native_dir(project_root, environ)
    entry = str(chosen)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return chosen
