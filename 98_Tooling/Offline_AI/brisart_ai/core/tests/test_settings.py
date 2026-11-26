r"""
File: brisart_ai/core/tests/test_settings.py

Purpose
-------
Exercise settings defaults, persistence and save rollback.

Protected scenarios: TestResearchSettings verifies valid json non object does not break
startup; TestResearchSettings verifies failed atomic replace restores setting and cleans
temp; TestResearchSettings verifies defaults applied when no file exists;
TestResearchSettings verifies settings file created on first use; TestResearchSettings
verifies set persists across instances.

Protected scenarios: TestResearchSettings verifies toggle flips value;
TestResearchSettings verifies set unknown key raises; TestResearchSettings verifies
corrupt settings file falls back to defaults; TestResearchSettings verifies stale
unknown key in file is ignored; TestResearchSettings verifies resolve key aliases.

Protected scenarios: TestResearchSettings verifies resolve key unknown raises;
TestResearchSettings verifies render produces readable text; TestResearchSettings
verifies obsolete web setting is not exposed.

Communication / relationships
-----------------------------
Uses temporary settings files and a simulated replacement failure.

Direct project imports: brisart_ai.core.settings.

The cases use self.assertTrue, self.assertEqual, self.assertFalse, self.assertIn,
self.assertNotIn, self.assertRaises to check returned values, persisted state or raised
errors. The suite is run through scripts/run_tests.py so Native API discovery happens
before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Invalid JSON shapes and failed writes.

Regression coverage includes
TestResearchSettings.test_corrupt_settings_file_falls_back_to_defaults,
TestResearchSettings.test_stale_unknown_key_in_file_is_ignored,
TestResearchSettings.test_resolve_key_aliases,
TestResearchSettings.test_resolve_key_unknown_raises,
TestResearchSettings.test_render_produces_readable_text,
TestResearchSettings.test_obsolete_web_setting_is_not_exposed.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/core/tests/test_settings.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/core/tests/test_settings.py -k
test_valid_json_non_object_does_not_break_startup.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.core.settings import DEFAULT_SETTINGS, ResearchSettings


class TestResearchSettings(unittest.TestCase):
    def _make(self, tmpdir):
        return ResearchSettings(path=Path(tmpdir) / "settings.json")

    def test_valid_json_non_object_does_not_break_startup(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            for payload in ("null", "42", "[]"):
                path.write_text(payload)
                self.assertEqual(ResearchSettings(path).values, DEFAULT_SETTINGS)

    def test_failed_atomic_replace_restores_setting_and_cleans_temp(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            settings = self._make(d)
            original = settings.path.read_bytes()
            with patch.object(Path, "replace", side_effect=PermissionError("blocked")):
                with self.assertRaises(PermissionError):
                    settings.set("search_notes", False)
            self.assertTrue(settings.get("search_notes"))
            self.assertEqual(settings.path.read_bytes(), original)
            self.assertEqual(list(Path(d).iterdir()), [settings.path])

    def test_defaults_applied_when_no_file_exists(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            for key, value in DEFAULT_SETTINGS.items():
                self.assertEqual(s.get(key), value)

    def test_settings_file_created_on_first_use(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            ResearchSettings(path=path)
            self.assertTrue(path.exists())

    def test_set_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            s1 = ResearchSettings(path=path)
            s1.set("search_local_files", True)
            s2 = ResearchSettings(path=path)
            self.assertTrue(s2.get("search_local_files"))

    def test_toggle_flips_value(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            original = s.get("search_notes")
            new_value = s.toggle("search_notes")
            self.assertEqual(new_value, not original)
            self.assertEqual(s.get("search_notes"), not original)

    def test_set_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            with self.assertRaises(KeyError):
                s.set("nonexistent_setting", True)

    def test_corrupt_settings_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not valid json!!")
            s = ResearchSettings(path=path)
            self.assertEqual(s.get("search_local_files"), DEFAULT_SETTINGS["search_local_files"])

    def test_stale_unknown_key_in_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"search_collections": true, "search_notes": true}')
            s = ResearchSettings(path=path)
            self.assertFalse(hasattr(s, "search_collections"))
            self.assertTrue(s.get("search_notes"))

    def test_resolve_key_aliases(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            self.assertEqual(s.resolve_key("local"), "search_local_files")
            self.assertEqual(s.resolve_key("local"), "search_local_files")
            self.assertEqual(s.resolve_key("notes"), "search_notes")

    def test_resolve_key_unknown_raises(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            with self.assertRaises(KeyError):
                s.resolve_key("bogus")

    def test_render_produces_readable_text(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            text = s.render()
            self.assertIn("Research Sources", text)


    def test_obsolete_web_setting_is_not_exposed(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            self.assertNotIn("auto_web_research", s.values)
            with self.assertRaises(KeyError):
                s.set("auto_web_research", True)

if __name__ == "__main__":
    unittest.main()
