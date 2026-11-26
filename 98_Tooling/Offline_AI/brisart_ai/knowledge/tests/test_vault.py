"""
File: brisart_ai/knowledge/tests/test_vault.py

Purpose
-------
Exercise notes, collections and timeline behavior.

Protected scenarios: TestVault verifies note search uses shared variants and relevant
preview; TestVault verifies collection and timeline exclude substrings and old web rows;
TestVault verifies create collection; TestVault verifies list collections empty;
TestVault verifies add note saves and mirrors into index.

Protected scenarios: TestVault verifies add note empty body rejected; TestVault verifies
list notes shows saved note; TestVault verifies search notes finds matching note;
TestVault verifies search notes as documents returns document shape; TestVault verifies
reindex missing notes backfills old notes.

Protected scenarios: TestVault verifies reindex missing notes idempotent; TestVault
verifies extract entities from text; TestVault verifies extract entities short names
excluded; TestVault verifies vault report includes counts; TestVault verifies add
sources to collection matches by term.

Communication / relationships
-----------------------------
Uses temporary indexes with notes and sources.

Direct project imports: brisart_ai.knowledge.index, brisart_ai.knowledge.vault.

The cases use self.assertTrue, self.assertNotIn, self.assertEqual, self.assertIn to
check returned values, persisted state or raised errors. The suite is run through
scripts/run_tests.py so Native API discovery happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Source scoping, matching passage previews and metadata links.

Regression coverage includes TestVault.test_reindex_missing_notes_backfills_old_notes,
TestVault.test_reindex_missing_notes_idempotent,
TestVault.test_extract_entities_from_text,
TestVault.test_extract_entities_short_names_excluded,
TestVault.test_vault_report_includes_counts,
TestVault.test_add_sources_to_collection_matches_by_term.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_vault.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/knowledge/tests/test_vault.py -k
test_note_search_uses_shared_variants_and_relevant_preview.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.vault import (
    add_note, add_sources_to_collection, create_collection, extract_entities_from_text,
    list_collections, list_notes, reindex_missing_notes, search_notes, search_notes_as_documents,
    timeline, vault_report,
)


class TestVault(unittest.TestCase):
    def _make(self, tmpdir):
        return Index(str(Path(tmpdir) / "test.sqlite"))

    def test_note_search_uses_shared_variants_and_relevant_preview(self):
        with Index(":memory:") as idx:
            add_note(idx, "Permit", "Background. " * 40 + "Permit expiry: June 30.")
            add_note(idx, "Travel", "An expirationist is not an indexed term match.")
            idx.add_source("file", "/permit.txt", "Other", "Permit expires tomorrow.")
            docs = search_notes_as_documents(idx, "When does the permit expire?")
            self.assertEqual([d["title"] for d in docs], ["Permit"])
            self.assertIn("Preview: Permit expiry: June 30.", search_notes(idx, "permit expire"))
            self.assertEqual(search_notes_as_documents(idx, "expiry", limit=0), [])

    def test_collection_and_timeline_exclude_substrings_and_old_web_rows(self):
        with Index(":memory:") as idx:
            idx.add_source("file", "/answer.txt", "Handbook", "Permit renewal begins in October.")
            idx.add_source("file", "/decoy.txt", "Decoy", "A superrenewalism entry.")
            idx.add_source("web", "https://example.invalid", "Old page", "The permit renews in June.")
            self.assertIn("Matched sources added: 1", add_sources_to_collection(idx, "Permits", "renew"))
            selected = idx.conn.execute("SELECT s.location FROM source_collections c "
                                        "JOIN sources s ON c.source_id=s.id").fetchall()
            self.assertEqual(selected, [("/answer.txt",)])
            result = timeline(idx, "renew")
            self.assertIn("/answer.txt", result)
            self.assertNotIn("/decoy.txt", result)
            self.assertNotIn("Old page", result)

    def test_create_collection(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = create_collection(idx, "research")
            self.assertIn("research", result)
            idx.close()

    def test_list_collections_empty(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = list_collections(idx)
            self.assertIn("No collections", result)
            idx.close()

    def test_add_note_saves_and_mirrors_into_index(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = add_note(idx, "My Note", "Some searchable content about narwhals")
            self.assertIn("My Note", result)
            self.assertEqual(idx.source_count("note"), 1)
            idx.close()

    def test_add_note_empty_body_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = add_note(idx, "Title", "   ")
            self.assertIn("cannot be empty", result)
            idx.close()

    def test_list_notes_shows_saved_note(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Test Note", "Note body text here")
            result = list_notes(idx)
            self.assertIn("Test Note", result)
            idx.close()

    def test_search_notes_finds_matching_note(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Zebra Facts", "Zebras have distinctive stripes")
            result = search_notes(idx, "zebra")
            self.assertIn("Zebra Facts", result)
            idx.close()

    def test_search_notes_as_documents_returns_document_shape(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Note Title", "unique searchable content xyzzy")
            docs = search_notes_as_documents(idx, "xyzzy")
            self.assertEqual(len(docs), 1)
            self.assertIn("score", docs[0])
            self.assertIn("text", docs[0])
            idx.close()

    def test_reindex_missing_notes_backfills_old_notes(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            # Simulate a note saved before mirroring existed: insert directly
            # into the notes table, bypassing add_note()'s mirroring step.
            from brisart_ai.knowledge.vault import init_vault_schema
            init_vault_schema(idx)
            with idx.conn:
                idx.conn.execute(
                    "INSERT INTO notes(title, body, collection_id, created_at, updated_at) VALUES(?,?,?,?,?)",
                    ("Old Note", "old note body content", None, 0, 0),
                )
            self.assertEqual(idx.source_count("note"), 0)
            reindexed = reindex_missing_notes(idx)
            self.assertEqual(reindexed, 1)
            self.assertEqual(idx.source_count("note"), 1)
            idx.close()

    def test_reindex_missing_notes_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Already Indexed", "content here")
            first = reindex_missing_notes(idx)
            self.assertEqual(first, 0)  # already indexed via add_note()
            idx.close()

    def test_extract_entities_from_text(self):
        entities = extract_entities_from_text("Bill Gates founded Microsoft in Albuquerque.")
        self.assertTrue(any("Bill Gates" in e or "Gates" in e for e in entities))

    def test_extract_entities_short_names_excluded(self):
        entities = extract_entities_from_text("A B is not a real entity but Full Name is.")
        self.assertNotIn("A", entities)

    def test_vault_report_includes_counts(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            report = vault_report(idx)
            self.assertIn("Indexed sources", report)
            self.assertIn("1", report)
            idx.close()

    def test_add_sources_to_collection_matches_by_term(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="unique term aardvark here")
            result = add_sources_to_collection(idx, "my_collection", "aardvark")
            self.assertIn("1", result)
            idx.close()


if __name__ == "__main__":
    unittest.main()
