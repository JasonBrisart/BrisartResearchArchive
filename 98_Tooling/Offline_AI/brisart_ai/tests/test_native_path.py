"""
File: brisart_ai/tests/test_native_path.py

Purpose
-------
Exercise external API discovery and import origin.

Protected scenarios: TestNativePath verifies prefers official in named archive folder;
TestNativePath verifies supports flat archive folder when official incomplete;
TestNativePath verifies supports previous archive spelling; TestNativePath verifies
offline startup does not require web only helpers; TestNativePath verifies override
wins.

Protected scenarios: TestNativePath verifies invalid override does not fall back;
TestNativePath verifies local copy cannot satisfy dependency; TestNativePath verifies
modules import from selected external directory.

Communication / relationships
-----------------------------
Uses isolated layouts plus the loaded external helpers.

Direct project imports: brisart_ai.

The cases use self.assertEqual, self.assertRaisesRegex, self.assertFalse to check
returned values, persisted state or raised errors. The suite is run through
scripts/run_tests.py so Native API discovery happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Incomplete and in-project overrides and supported historical folder spellings.

Regression coverage includes TestNativePath.test_supports_previous_archive_spelling,
TestNativePath.test_offline_startup_does_not_require_web_only_helpers,
TestNativePath.test_override_wins,
TestNativePath.test_invalid_override_does_not_fall_back,
TestNativePath.test_local_copy_cannot_satisfy_dependency,
TestNativePath.test_modules_import_from_selected_external_directory.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_native_path.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/tests/test_native_path.py -k setUp.
"""

import importlib
import tempfile
import unittest
from pathlib import Path

from brisart_ai import native_path


def make_stack(directory, *, skip=None):
    directory.mkdir(parents=True, exist_ok=True)
    for name in native_path.REQUIRED_MODULES:
        if name != skip:
            (directory / name).touch()
    return directory


class TestNativePath(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.archive = Path(scratch.name).resolve() / 'Archive'
        self.project = self.archive / '98_Tooling' / 'Offline_AI'
        self.project.mkdir(parents=True)
        self.api = self.archive / "94_Native_API's"

    def test_prefers_official_in_named_archive_folder(self):
        make_stack(self.api)
        make_stack(self.archive / "94_native apis" / "Official")
        official = make_stack(self.api / 'Official')
        self.assertEqual(native_path.find_native_dir(self.project, {}), official)

    def test_supports_flat_archive_folder_when_official_incomplete(self):
        make_stack(self.api / 'Official', skip='brisart_url.py')
        flat = make_stack(self.api)
        self.assertEqual(native_path.find_native_dir(self.project, {}), flat)

    def test_supports_previous_archive_spelling(self):
        other = make_stack(self.archive / '94_Native_API' / 'Official')
        self.assertEqual(native_path.find_native_dir(self.project, {}), other)

    def test_offline_startup_does_not_require_web_only_helpers(self):
        helpers = {"brisart_hash.py", "brisart_inflate.py", "brisart_json.py",
                   "brisart_markup.py", "brisart_url.py"}
        official = self.api / "Official"
        official.mkdir(parents=True)
        for name in helpers:
            (official / name).touch()
        self.assertEqual(native_path.find_native_dir(self.project, {}), official)

    def test_override_wins(self):
        make_stack(self.api / 'Official')
        alternate = make_stack(self.archive / 'alternate')
        self.assertEqual(native_path.find_native_dir(self.project, {native_path.ENV_VAR: str(alternate)}), alternate)

    def test_invalid_override_does_not_fall_back(self):
        make_stack(self.api / 'Official')
        with self.assertRaisesRegex(ImportError, native_path.ENV_VAR):
            native_path.find_native_dir(self.project, {native_path.ENV_VAR: str(self.archive / 'missing')})

    def test_local_copy_cannot_satisfy_dependency(self):
        local = make_stack(self.project / 'brisart_ai' / 'native')
        with self.assertRaisesRegex(ImportError, "94_Native_API's"):
            native_path.find_native_dir(self.project, {})
        with self.assertRaisesRegex(ImportError, 'outside Offline_AI'):
            native_path.find_native_dir(self.project, {native_path.ENV_VAR: str(local)})

    def test_modules_import_from_selected_external_directory(self):
        selected = native_path.find_native_dir()
        for filename in native_path.REQUIRED_MODULES:
            with self.subTest(filename=filename):
                module = importlib.import_module(Path(filename).stem)
                self.assertEqual(Path(module.__file__).resolve(), (selected / filename).resolve())
                self.assertFalse(Path(module.__file__).resolve().is_relative_to(native_path.PROJECT_ROOT))
