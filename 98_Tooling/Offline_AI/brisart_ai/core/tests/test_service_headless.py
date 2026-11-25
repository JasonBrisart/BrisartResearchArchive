r"""
File: brisart_ai/core/tests/test_service_headless.py

Purpose
-------
Exercise research service operations directly, without creating Tk widgets.

Communication / relationships
-----------------------------
Direct module imports: json, tempfile, unittest, pathlib,
brisart_ai.core.service. Every service is built with a database and a
settings file inside its own temporary directory.

Settings / parameters
---------------------
_make(tmpdir) builds a BrisartService with db_path and settings_path in
tmpdir. Nothing here reads or writes the user's saved settings.

Edge cases
----------
- test_default_settings_path_is_in_the_state_folder only compares paths; it
  never constructs a service on the user's own settings file.

Known limitations
-----------------
- app.py, chat_panel.py, dialogs.py and sidebar.py need a live Tk display
  and are checked by hand, not here.
- ask() is exercised only with force_web=False, so no test reaches the
  network.

Examples
--------
python scripts/run_tests.py brisart_ai/core/tests/test_service_headless.py
"""

import json
import tempfile
import unittest
from pathlib import Path
from brisart_ai import native_path
from brisart_ai.core.service import BrisartService
from brisart_ai.core.settings import DEFAULT_SETTINGS, DEFAULT_SETTINGS_PATH


class TestBrisartServiceHeadless(unittest.TestCase):
    def _make(self, tmpdir):
        return BrisartService(
            str(Path(tmpdir) / "test.sqlite"),
            settings_path=str(Path(tmpdir) / "settings.json"),
        )

    def test_construction_succeeds(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            self.assertIsNotNone(service.index)
            self.assertIsNotNone(service.memory)
            self.assertIsNotNone(service.settings)
            service.close()

    def test_counts_start_at_zero(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            total, files, web = service.counts()
            self.assertEqual((total, files, web), (0, 0, 0))
            service.close()

    def test_add_note_increases_counts(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Test Note", "Some content about narwhals")
            total, _files, _web = service.counts()
            self.assertEqual(total, 1)
            service.close()

    def test_ask_answers_from_indexed_note(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Microsoft History", "Microsoft was founded by Bill Gates and Paul Allen in 1975.")
            answer = service.ask("who founded microsoft?", force_web=False)
            self.assertIn("Sources:", answer)
            service.close()

    def test_toggle_setting_flips_value(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            original = service.settings.get("search_notes")
            _label, new_value = service.toggle_setting("notes")
            self.assertEqual(new_value, not original)
            service.close()

    def test_settings_panel_text_contains_research_sources(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            text = service.settings_panel_text()
            self.assertIn("Research Sources", text)
            service.close()

    def test_import_paths_ingests_files(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            f = Path(d) / "doc.txt"
            f.write_text("unique searchable content about wombats")
            result = service.import_paths([str(f)])
            self.assertIn("Ingested 1", result)
            service.close()

    def test_list_notes_reflects_added_note(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("My Title", "body content")
            result = service.list_notes()
            self.assertIn("My Title", result)
            service.close()

    def test_settings_live_in_the_given_file_not_the_state_folder(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.toggle_setting("notes")
            saved = json.loads((Path(d) / "settings.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["search_notes"], not DEFAULT_SETTINGS["search_notes"])
            service.close()

    def test_default_settings_path_is_in_the_state_folder(self):
        self.assertEqual(DEFAULT_SETTINGS_PATH.name, "research_settings.json")
        self.assertEqual(DEFAULT_SETTINGS_PATH.parent.name, "BrisartAI")
        self.assertNotIn(native_path.PROJECT_ROOT, DEFAULT_SETTINGS_PATH.parents)


if __name__ == "__main__":
    unittest.main()
