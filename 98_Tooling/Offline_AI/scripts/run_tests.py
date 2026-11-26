#!/usr/bin/env python3
r"""
File: scripts/run_tests.py

Purpose
-------
Run the co-located application suite with proper dependency bootstrap.

Public operations: main (argv).

Communication / relationships
-----------------------------
Resolves Native APIs, puts the project on sys.path and calls pytest.

Direct project imports: brisart_ai.

Concrete calls within this file include native_path.install.

Settings / parameters
---------------------
Pass pytest flags or paths after the script; default collection is brisart_ai/.

Module configuration and named constants: PROJECT_ROOT.

Call signatures: main(argv).

Edge cases
----------
Importlib collection supports namespace folders; pytest cache writes are disabled.

Explicit exception branches or raised errors in this file include SystemExit.

Known limitations
-----------------
Headless runs do not validate live Tk or Windows Explorer interactions.

Developer tooling is not part of the normal desktop request path. Benchmark-only
dependencies do not become runtime requirements of the offline research assistant.

Examples
--------
python scripts/run_tests.py -q

For a concrete entry point, inspect `main`; invoke it through the existing application entry
point or its documented caller. The example above is illustrative of this file's present
interface; do not treat it as an instruction to create additional state or call private
functions directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from brisart_ai import native_path  # noqa: E402

native_path.install()

import pytest  # noqa: E402


def main(argv):
    arguments = list(argv)
    if not any(Path(argument.split("::", 1)[0]).exists() for argument in arguments):
        arguments.append(str(PROJECT_ROOT / "brisart_ai"))
    return pytest.main(["--import-mode=importlib", "-p", "no:cacheprovider", *arguments])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
