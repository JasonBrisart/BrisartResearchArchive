#!/usr/bin/env python3
r"""
File: scripts/run_tests.py

Purpose
-------
Configure the shared native dependency and run co-located application tests
under pytest.

Communication / relationships
-----------------------------
- Imports brisart_ai.native_path before pytest imports any test module.
- Calls pytest.main(); pytest must be installed (it is the only runner
  dependency, and nothing under brisart_ai/ needs it at run time).
- Covers every tests/ folder under brisart_ai/ by default.

Settings / parameters
---------------------
- Every command-line argument is passed to pytest unchanged.
- With no argument that names an existing path, brisart_ai/ is added, so
  ``-k robots`` and ``-v`` still run the whole suite.
- Always added: ``--import-mode=importlib`` and ``-p no:cacheprovider``
  (pytest's cache folder would otherwise appear inside the project).

Edge cases
----------
- The exit status is pytest's.
- BRISART_NATIVE_API is honoured, so the suite can be run against another
  native stack folder.

Known limitations
-----------------
- Plain ``pytest`` or ``python -m unittest`` from the project root cannot
  import the flat brisart_* modules; use this script.
- GUI modules that need a Tk display are not covered; see docs/TESTING.md.

Examples
--------
::

    python scripts/run_tests.py
    python scripts/run_tests.py brisart_ai/web/tests -v
    python scripts/run_tests.py -k robots
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
