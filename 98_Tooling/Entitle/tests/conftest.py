"""
File: tests/conftest.py

Purpose
-------
Prepare every pytest run: put the Entitle folder on sys.path so entitle/, gui/, cli.py and
  version.py import without installing anything, and provide the store_path fixture.

Communication / relationships
-----------------------------
Imports pytest. Loaded automatically by pytest before any test module. It does not import the
  application: entitle/encryption.py puts 97_Encryption/Official on the import path itself, so
  no preparation beyond the Entitle folder is needed. The tests do need 97_Encryption beside
  98_Tooling, because that is where Entitle's encryption lives.

Settings / parameters
---------------------
store_path is a fresh record-store path inside pytest's tmp_path; its parent folder does not
  exist yet, so tests can check that the first append creates it.

Edge cases
----------
Running pytest from the Entitle folder or from tests/ both work. A different test runner has
  to put the Entitle folder on its import path itself.

Known limitations
-----------------
Only pytest is supported; the tests use its fixtures, tmp_path and monkeypatch.

Examples
--------
From the directory containing run.py:

    python -m pytest tests
"""

import sys
from pathlib import Path

import pytest

ENTITLE_ROOT = Path(__file__).resolve().parent.parent
if str(ENTITLE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENTITLE_ROOT))


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "records" / "entitle_records.log"
