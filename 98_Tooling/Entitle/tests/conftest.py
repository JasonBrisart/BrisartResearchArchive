"""
File: tests/conftest.py

Purpose
-------
Regression checks in 98_Tooling/Entitle/tests/conftest.py.

Communication / relationships
-----------------------------
Direct module imports: sys, pathlib, entitle.bootstrap, pytest.

Settings / parameters
---------------------
Module-level named settings: REPO_ROOT. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Run this test file with the project-scoped test runner.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from entitle.bootstrap import ensure_bsr_on_path  # noqa: E402
ensure_bsr_on_path()

import pytest  # noqa: E402


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "records" / "entitle_records.log"

