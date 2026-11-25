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
  network.

Examples
--------
python scripts/run_tests.py brisart_ai/core/tests/test_service_headless.py
"""

import json
import sqlite3
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
            answer = service.ask("who founded microsoft?")
            self.assertIn("Sources:", answer)
            service.close()

    def test_add_multiple_supported_files_and_folder_recursively(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            service = self._make(d)
            folder = root / "imports"
            nested = folder / "nested"
            nested.mkdir(parents=True)
            files = [root / "a.txt", root / "b.md", folder / "c.csv", nested / "d.json"]
            contents = ["local unique text", "markdown unique text", "name,value\nitem,unique", '{"description": "unique json"}']
            for path, content in zip(files, contents):
                path.write_text(content, encoding="utf-8")
            (folder / "ignore.bin").write_bytes(b"not supported")
            service.import_paths([str(files[0]), str(files[1])])
            self.assertEqual(service.index.source_count("file"), 2)
            service.import_paths([str(folder)])
            self.assertEqual(service.index.source_count("file"), 4)
            self.assertEqual({row[3] for row in service.list_sources() if row[1] == "file"},
                             {str(path.resolve()) for path in files})
            service.close()

    def test_source_note_keeps_provenance_and_excerpt_after_source_removal(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            path = Path(d) / "field notes.txt"
            path.write_text("First line.\nThe ravens nested by the bridge.\nLast line.", encoding="utf-8")
            service.import_paths([str(path)])
            source_id = service.list_sources()[0][0]
            self.assertIn("ravens", service.get_source_for_note(source_id)[2])
            with self.assertRaisesRegex(ValueError, "does not match"):
                service.add_source_note("Wrong", "", source_id, "The swans nested here.")
            self.assertIn("Note saved", service.add_source_note("Bird count", "Check next spring.", source_id,
                                                               "The ravens nested by the bridge."))
            self.assertTrue(service.remove_source(source_id))
            self.assertTrue(path.is_file())
            body = service.index.conn.execute("SELECT body FROM notes").fetchone()[0]
            self.assertIn(str(path.resolve()), body)
            self.assertIn("Excerpt:\nThe ravens nested by the bridge.", body)
            self.assertIn("Your observations:\nCheck next spring.", body)
            self.assertIn("ravens", service.ask("ravens"))
            with self.assertRaisesRegex(ValueError, "no longer indexed"):
                service.add_source_note("Old", "", source_id, "ravens")
            service.close()

    def test_batch_removal_rolls_back_and_ignores_duplicate_and_missing_ids(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            for name in ("a", "b"):
                service.add_note(name, f"Evidence for {name}.")
            first, second = [row[0] for row in service.list_sources()]
            service.index.conn.execute(
                f"CREATE TRIGGER block_delete BEFORE DELETE ON sources WHEN old.id = {second} "
                "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                service.remove_sources([first, second])
            self.assertEqual(service.index.source_count("note"), 2)
            self.assertEqual(service.index.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0], 2)
            service.index.conn.execute("DROP TRIGGER block_delete")
            self.assertEqual(service.remove_sources([first, first, second, -1]), 2)
            self.assertEqual(service.index.conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0], 0)
            service.close()

    def test_remove_imported_file_preserves_original_and_clears_search(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            path = Path(d) / "document.txt"
            path.write_text("unique aardvark evidence", encoding="utf-8")
            service.import_paths([str(path)])
            rows = [row for row in service.list_sources() if row[1] == "file"]
            self.assertEqual(len(rows), 1)
            self.assertTrue(service.remove_source(rows[0][0]))
            self.assertFalse(service.remove_source(rows[0][0]))
            self.assertTrue(path.exists())
            self.assertEqual(service.index.source_count("file"), 0)
            service.close()

    def test_remove_note_deletes_vault_record_and_does_not_reindex(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Aardvark", "unique aardvark evidence")
            rows = [row for row in service.list_sources() if row[1] == "note"]
            self.assertEqual(len(rows), 1)
            self.assertTrue(service.remove_source(rows[0][0]))
            self.assertEqual(service.index.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0], 0)
            self.assertEqual(service.index.source_count("note"), 0)
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
