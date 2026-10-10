"""
File: tests/test_build_profile_paths.py

Purpose
-------
Check build-profile paths without building executables.

Communication / relationships
-----------------------------
Imports existing project modules; runs under the project-scoped CI workflow.

Settings / parameters
---------------------
Uses unittest and temporary fixtures; no application settings are changed.

Edge cases
----------
Covers normal behavior and selected invalid or missing inputs.

Known limitations
-----------------
Targeted regression coverage only; not a complete application or GUI audit.

Examples
--------
Run python -m pytest -v from the containing project directory.
"""

import tempfile
import unittest
from pathlib import Path
from build_profiles import BuildProfile, resolve_entrypoint, resolve_icon_path

class BuildProfilePathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = BuildProfile(str(self.root), 'main.py', str(self.root / 'out'), 'sample')

    def test_relative_python_entrypoint_is_resolved(self):
        path = self.root / 'main.py'
        path.write_text('pass\n', encoding='utf-8')
        self.assertEqual(resolve_entrypoint(self.profile), path.resolve())

    def test_absolute_python_entrypoint_is_resolved(self):
        path = self.root / 'main.py'
        path.write_text('pass\n', encoding='utf-8')
        self.profile.entrypoint = str(path)
        self.assertEqual(resolve_entrypoint(self.profile), path.resolve())

    def test_missing_entrypoint_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            resolve_entrypoint(self.profile)

    def test_directory_entrypoint_is_rejected(self):
        (self.root / 'main.py').mkdir()
        with self.assertRaises(FileNotFoundError):
            resolve_entrypoint(self.profile)

    def test_non_python_entrypoint_is_rejected(self):
        (self.root / 'main.txt').write_text('text', encoding='utf-8')
        self.profile.entrypoint = 'main.txt'
        with self.assertRaises(ValueError):
            resolve_entrypoint(self.profile)

    def test_blank_icon_is_optional(self):
        self.profile.icon_path = '   '
        self.assertIsNone(resolve_icon_path(self.profile))

    def test_missing_icon_is_rejected(self):
        self.profile.icon_path = 'missing.ico'
        with self.assertRaises(FileNotFoundError):
            resolve_icon_path(self.profile)

    def test_profile_serialization_preserves_settings(self):
        self.profile.onefile = False
        result = self.profile.to_dict()
        self.assertEqual(result['entrypoint'], 'main.py')
        self.assertFalse(result['onefile'])
        self.assertFalse(result['confirm_overwrite'])

