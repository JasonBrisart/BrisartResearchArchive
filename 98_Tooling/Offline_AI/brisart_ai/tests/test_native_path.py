r"""
File: brisart_ai/tests/test_native_path.py

Purpose
-------
Exercise external module discovery and verify the import origin of every
required module.

Communication / relationships
-----------------------------
Uses native_path and isolated directory layouts. The project test runner
installs the external stack before collection.

Settings / parameters
---------------------
Injects the environment mapping into find_native_dir for discovery tests.

Edge cases
----------
An incomplete Official folder, invalid override, or legacy in-project
copy must not silently change which dependency is loaded.

Known limitations
-----------------
Dummy module files test discovery only; the import test checks the actual
stack supplied to the current test run.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_native_path.py
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
