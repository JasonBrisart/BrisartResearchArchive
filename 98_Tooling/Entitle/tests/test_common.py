"""
File: tests/test_common.py

Purpose
-------
Verify entitle/common.py, what every Entitle module shares (the error base class, canonical JSON,
  the UTC clock, the required-text and identifier checks and the atomic file writer), and that
  entitle/ really is a namespace package: every module imports in a fresh interpreter, from any
  working folder, with no entitle/__init__.py, and only one entitle folder is on the path.

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
import os
import stat
import subprocess
import sys
import warnings

import pytest

from entitle.common import (
    EntitleError, canonical_json, require_identifier, require_text, utc_now, utc_now_iso, write_text_atomically,
)
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
            "import entitle.common, entitle.rights, entitle.encryption, entitle.signing, entitle.host,"
            " entitle.entitlements, entitle.records, entitle.revoke, entitle.revocation_list, entitle.tracking,"
            " entitle.checkpoints, entitle.report, cli, version, run;"
            "import entitle;"
            "assert entitle.__file__ is None, entitle.__file__;"
            f"assert list(entitle.__path__) == [{str(ENTITLE_ROOT / 'entitle')!r}], list(entitle.__path__);"
            "assert 'tkinter' not in sys.modules and not any(m.startswith('brisart_security') for m in sys.modules)"
        )
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path)
        assert done.returncode == 0, done.stderr


class TestRequireIdentifier:
    @pytest.mark.parametrize("value,message", [
        (" lab-1", "must not start or end with spaces"), ("lab-1 ", "must not start or end with spaces"),
        ("lab\t1", "must not contain control characters"), ("lab\x001", "must not contain control characters"),
        ("", "is required"), (None, "is required"),
    ])
    def test_identifiers_that_could_never_match_are_refused(self, value, message):
        with pytest.raises(ValueError, match=message):
            require_identifier(entitlement_id=value)

    def test_ordinary_identifiers_pass_including_non_latin_text(self):
        assert require_identifier(entitlement_id="lab-a 001", host="узел-1") is None


class TestWriteTextAtomically:
    def test_it_writes_utf8_with_a_final_newline_and_leaves_no_temporary_file(self, tmp_path):
        path = tmp_path / "a" / "b.txt"
        write_text_atomically(path, "实验室")
        assert path.read_bytes() == "实验室\n".encode("utf-8") and [p.name for p in path.parent.iterdir()] == ["b.txt"]

    def test_overwrite_false_refuses_an_existing_file(self, tmp_path):
        path = tmp_path / "b.txt"
        write_text_atomically(path, "first")
        with pytest.raises(FileExistsError, match="already exists"):
            write_text_atomically(path, "second", overwrite=False)
        assert path.read_text(encoding="utf-8") == "first\n"

    def test_a_failed_replacement_keeps_the_old_file_and_cleans_up(self, tmp_path, monkeypatch):
        from entitle import common

        path = tmp_path / "b.txt"
        write_text_atomically(path, "old")
        monkeypatch.setattr(common.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError, match="disk full"):
            write_text_atomically(path, "new")
        assert path.read_text(encoding="utf-8") == "old\n" and [p.name for p in tmp_path.iterdir()] == ["b.txt"]

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
    def test_private_files_are_owner_only(self, tmp_path):
        write_text_atomically(tmp_path / "secret", "x", private=True)
        assert stat.S_IMODE((tmp_path / "secret").stat().st_mode) == 0o600
