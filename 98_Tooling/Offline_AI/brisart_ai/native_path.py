"""
File: brisart_ai/native_path.py

Purpose
-------
Resolve the external Brisart helpers before launchers import their consumers.

Public operations: find_native_dir (project_root=PROJECT_ROOT, environ=None) - Return
the folder that holds the Brisart native stack for this checkout; install
(project_root=PROJECT_ROOT, environ=None) - Put the native stack folder on sys.path
(once) and return it.

Internal helpers include _is_external_stack, _archive_candidates.

Communication / relationships
-----------------------------
Used by run.py, cli.py and developer tools; helpers are not bundled.

No direct project import appears in this module’s top-level imports. The file is reached
as a launcher, test, or helper, or through a runtime import rather than through an
ordinary domain import.

Settings / parameters
---------------------
BRISART_NATIVE_API overrides ancestor discovery of the Official or flat API folder.

Module configuration and named constants: ENV_VAR='BRISART_NATIVE_API', ARCHIVE_DIRNAMES
(tuple, 4 entries), ARCHIVE_SUBDIR='Official', PROJECT_ROOT, REQUIRED_MODULES (tuple, 5
entries).

Call signatures: find_native_dir(project_root=PROJECT_ROOT, environ=None);
install(project_root=PROJECT_ROOT, environ=None).

Edge cases
----------
An incomplete override fails without falling back; a path inside the project is
rejected.

Explicit exception branches or raised errors in this file include ImportError.

Known limitations
-----------------
File discovery checks presence, not version or API compatibility. Codec and robots are
not used by this application.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
native_path.install()

Other callable entry points in this module include install.
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
    "brisart_hash.py",
    "brisart_inflate.py",
    "brisart_json.py",
    "brisart_markup.py",
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
