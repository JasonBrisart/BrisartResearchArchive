"""
File: tests/test_common.py

Purpose
-------
Verify entitle/common.py, the four things every Entitle module shares (the error base class,
  canonical JSON, the UTC clock and the required-text check), and that entitle/ really is a
  namespace package: every module imports in a fresh interpreter, from any working folder, with
  no entitle/__init__.py, and only one entitle folder is on the path.

Communication / relationships
-----------------------------
Imports entitle/common.py and tests/support.py (ENTITLE_ROOT). The import check starts one
  Python process that imports entitle/common.py, entitle/rights.py, entitle/encryption.py,
  entitle/entitlements.py, entitle/records.py, entitle/revoke.py, entitle/tracking.py,
  entitle/report.py, cli.py, version.py and run.py. Needs no encryption, files or record log.
  Run by pytest; nothing imports it.

Settings / parameters
---------------------
Canonical JSON is pinned to its exact bytes, because those bytes are what sealed files and
  record hashes are built from. The import check runs from tmp_path so nothing relies on the
  current folder.

Edge cases
----------
Covers canonical JSON with non-ASCII text and unordered keys, required text that is empty,
  whitespace, missing or not text, a clock that is aware and at second resolution, and an
  entitle package whose __file__ is None (a namespace package) with exactly one path entry.

Known limitations
-----------------
Does not import gui/ (it needs tkinter; tests/test_gui.py covers it with a stand-in).

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_common.py
"""

import datetime
import json
import subprocess
import sys
import warnings

import pytest

from entitle.common import EntitleError, canonical_json, require_text, utc_now, utc_now_iso
from support import ENTITLE_ROOT


class TestCanonicalJson:
    def test_output_is_deterministic_key_order(self):
        assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})

    def test_the_exact_bytes_are_pinned_because_hashes_and_seals_depend_on_them(self):
        assert canonical_json({"b": [1, {"y": None, "x": True}], "a": "é 实"}) == (
            '{"a":"é 实","b":[1,{"x":true,"y":null}]}'.encode("utf-8")
        )

    def test_round_trips_through_json_loads(self):
        payload = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
        assert json.loads(canonical_json(payload).decode("utf-8")) == payload


class TestRequireText:
    def test_blank_or_missing_text_names_the_field(self):
        for value in ("", "   ", None, 7):
            with pytest.raises(ValueError, match="^fork name is required.$"):
                require_text(product="P", fork_name=value)

    def test_present_text_passes_and_is_not_stripped(self):
        assert require_text(product="P", fork_name=" f ") is None


class TestClock:
    def test_utc_now_is_aware_utc(self):
        assert utc_now().utcoffset() == datetime.timedelta(0)

    def test_utc_now_iso_is_second_resolution_utc_and_parses_back(self):
        text = utc_now_iso()
        assert text.endswith("+00:00") and "." not in text
        assert datetime.datetime.fromisoformat(text).utcoffset() == datetime.timedelta(0)


class TestErrors:
    def test_entitle_error_is_an_ordinary_exception(self):
        assert issubclass(EntitleError, Exception) and not issubclass(EntitleError, ValueError)


class TestSourceFilesCompileCleanly:
    def test_no_source_file_raises_a_warning_when_compiled(self):
        # A header containing a backslash (for example a Windows path) in an ordinary docstring is a
        # SyntaxWarning today and an error in a future Python; this keeps that from creeping back in.
        for path in sorted(ENTITLE_ROOT.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                compile(path.read_text(encoding="utf-8"), str(path), "exec")


class TestNamespacePackage:
    def test_every_module_imports_with_no_init_file_and_one_entitle_folder(self, tmp_path):
        assert not list(ENTITLE_ROOT.rglob("__init__.py"))
        code = (
            f"import sys; sys.path.insert(0, {str(ENTITLE_ROOT)!r});"
            "import entitle.common, entitle.rights, entitle.encryption, entitle.entitlements,"
            " entitle.records, entitle.revoke, entitle.tracking, entitle.report, cli, version, run;"
            "import entitle;"
            "assert entitle.__file__ is None, entitle.__file__;"
            f"assert list(entitle.__path__) == [{str(ENTITLE_ROOT / 'entitle')!r}], list(entitle.__path__);"
            "assert 'tkinter' not in sys.modules and not any(m.startswith('brisart_security') for m in sys.modules)"
        )
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path)
        assert done.returncode == 0, done.stderr
