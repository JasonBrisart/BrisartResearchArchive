"""
File: gui/tests/test_tab_biometrics.py

Purpose
-------
Tests for gui.tabs.tab_biometrics.BiometricsTab -- the Biometrics-tab slice of
KI-002's remaining gap ("gui/tabs/*.py ... still has no direct coverage").

Verifies: gui/tabs/tab_biometrics.py, biometrics/identity/identity_store.py,
biometrics/identity/identity_record.py, biometrics/engine/attachments.py,
biometrics/engine/bulk_attachments.py, common/atomic_io.py.
Contains 13 test case(s) across 2 TestCase class(es).

Design notes:

Scope is limited to state-inspection and list-refresh logic: identity selection
helpers (_selected_identity_id / _target_identity_id), the identity list
refresh (_refresh_list), the attachment list refresh and its manifest/chunk
display-name logic (_refresh_attachment_list), and attachment selection
(_selected_attachment_name). Methods that pop a real modal dialog or run a
background KDF-touching operation (_ensure_keyring, _enroll, _verify,
_make_samples, _attach_selected_paths, _extract_selected_attachment,
_remove_selected_attachment -- the last of which opens a blocking
messagebox.askyesno before doing anything else) are intentionally NOT exercised
here, for the same reason test_tab_vault.py excludes its equivalents: no user
is present in an automated run to dismiss a modal, so calling one would hang
the suite.

self._store is overridden directly with a real, temp-directory-backed
IdentityStore after construction (BiometricsTab.__init__ already calls
_refresh_list() once against the real biometrics_settings.IDENTITY_DIR path as
a side effect of normal construction; overriding afterward, before any
test-specific refresh, keeps each test isolated from whatever that default
directory happens to contain). Attachment fixtures use an injected 32-byte
master key with the real attach_bytes / attach_large_bytes sealing calls (fast,
sponge-based -- no KDF), the same convention already used in
biometrics/tests/test_attachments.py and
biometrics/tests/test_bulk_attachments.py.

BiometricsTabTests requires a real Tk root and skips cleanly on a headless
runner with no display, matching the convention used throughout gui/tests/.

KeyringPersistenceTests covers _save_new_keyring(), the write used when the tab
creates a new keyring. It calls the helper directly with a stand-in keyring
object, so it needs tkinter to import the module but no display and no KDF.

Communication / relationships
-----------------------------
Depends on (project modules):
- gui.tabs.tab_biometrics (gui/tabs/tab_biometrics.py)
- biometrics.identity.identity_store (biometrics/identity/identity_store.py)
- biometrics.identity.identity_record (biometrics/identity/identity_record.py)
- biometrics.engine.attachments (biometrics/engine/attachments.py)
- biometrics.engine.bulk_attachments (biometrics/engine/bulk_attachments.py)
Standard library: json, os, pathlib, secrets, stat, tempfile, tkinter,
unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
- _HAS_DISPLAY = _tk_display_available()
- _HAS_TKINTER = _tkinter_importable()

Edge cases
----------
- Selected identity id returns none when nothing selected.
- Selected identity id returns correct value when selected.
- Target identity id prefers typed value over selection.
- Target identity id falls back to selection when field empty.
- Selected attachment name returns none when nothing selected.
- Refresh list populates identity rows.
- Refresh list is empty for a fresh store.
- Refresh attachment list shows plain attachment.
- Refresh attachment list strips manifest suffix and hides chunks.
- Refresh attachment list is empty with no target identity.
- Selected attachment name returns correct value when selected.
- A new keyring is saved as the keyring's JSON state.
- A new keyring is saved owner-only (0o600) on POSIX.
- Skips (rather than fails) when a prerequisite is missing: "requires a
  Tk-capable display", "tkinter not installed", "POSIX permission bits only"

Known limitations
-----------------
- Passing proves only the 13 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest gui.tests.test_tab_biometrics -v
    python tests/run_tests.py
"""

import json
import os
import secrets
import stat
import tempfile
import unittest
from pathlib import Path


def _tkinter_importable():
    try:
        import tkinter  # noqa: F401
    except ImportError:
        return False
    return True


_HAS_TKINTER = _tkinter_importable()


def _tk_display_available():
    try:
        import tkinter as tk
    except ImportError:
        return False
    try:
        root = tk.Tk()
    except Exception:
        return False
    root.destroy()
    return True


_HAS_DISPLAY = _tk_display_available()


@unittest.skipUnless(_HAS_DISPLAY, "requires a Tk-capable display")
class BiometricsTabTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from gui.tabs.tab_biometrics import BiometricsTab
        from biometrics.identity.identity_store import IdentityStore

        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)
        self.store = IdentityStore(self.tmp_path / "identities")
        self.master_key = secrets.token_bytes(32)

        self.root = tk.Tk()
        self.root.withdraw()
        self.tab = BiometricsTab(self.root)
        # Override the store the constructor set up against the real
        # biometrics_settings.IDENTITY_DIR path, before any test triggers
        # another refresh.
        self.tab._store = self.store

    def tearDown(self):
        self.root.destroy()
        self._tmp_dir.cleanup()

    def _save_identity(self, identity_id="alice", label="Alice Example"):
        from biometrics.identity.identity_record import new_record

        record = new_record(identity_id, label, "device-binding-placeholder")
        self.store.save(record)
        return record

    # -- selection helpers ----------------------------------------------------
    def test_selected_identity_id_returns_none_when_nothing_selected(self):
        self.assertIsNone(self.tab._selected_identity_id())

    def test_selected_identity_id_returns_correct_value_when_selected(self):
        self._save_identity("alice", "Alice Example")
        self.tab._refresh_list()
        children = self.tab.tree.get_children()
        self.assertEqual(len(children), 1)
        self.tab.tree.selection_set(children[0])
        self.assertEqual(self.tab._selected_identity_id(), "alice")

    def test_target_identity_id_prefers_typed_value_over_selection(self):
        self._save_identity("alice", "Alice Example")
        self.tab._refresh_list()
        self.tab.tree.selection_set(self.tab.tree.get_children()[0])
        self.tab._attach_identity_var.set("bob")
        self.assertEqual(self.tab._target_identity_id(), "bob")

    def test_target_identity_id_falls_back_to_selection_when_field_empty(self):
        self._save_identity("alice", "Alice Example")
        self.tab._refresh_list()
        self.tab.tree.selection_set(self.tab.tree.get_children()[0])
        self.tab._attach_identity_var.set("")
        self.assertEqual(self.tab._target_identity_id(), "alice")

    def test_selected_attachment_name_returns_none_when_nothing_selected(self):
        self.assertIsNone(self.tab._selected_attachment_name())

    # -- identity list ----------------------------------------------------------
    def test_refresh_list_populates_identity_rows(self):
        self._save_identity("alice", "Alice Example")
        self._save_identity("bob", "Bob Example")
        self.tab._refresh_list()
        identity_ids = {self.tab.tree.item(i, "values")[0] for i in self.tab.tree.get_children()}
        self.assertEqual(identity_ids, {"alice", "bob"})

    def test_refresh_list_is_empty_for_a_fresh_store(self):
        self.tab._refresh_list()
        self.assertEqual(len(self.tab.tree.get_children()), 0)

    # -- attachment list: manifest/chunk display logic --------------------------
    def test_refresh_attachment_list_shows_plain_attachment(self):
        from biometrics.engine.attachments import attach_bytes

        record = self._save_identity()
        record = attach_bytes(record, "notes.txt", b"hello world", self.master_key)
        self.store.save(record)

        self.tab._attach_identity_var.set("alice")
        self.tab._refresh_attachment_list()
        rows = [self.tab.attachment_tree.item(i, "values") for i in self.tab.attachment_tree.get_children()]
        self.assertEqual(rows, [("notes.txt", 11)])

    def test_refresh_attachment_list_strips_manifest_suffix_and_hides_chunks(self):
        from biometrics.engine import bulk_attachments

        record = self._save_identity()
        payload = secrets.token_bytes(200)
        record = bulk_attachments.attach_large_bytes(
            record, "mybundle", payload, self.master_key, chunk_bytes=64
        )
        self.store.save(record)

        self.tab._attach_identity_var.set("alice")
        self.tab._refresh_attachment_list()
        names = [self.tab.attachment_tree.item(i, "values")[0] for i in self.tab.attachment_tree.get_children()]
        # Exactly one row for the whole bundle, named without ".manifest",
        # and no ".chunkN" rows leaking through as if they were their own
        # independent attachments.
        self.assertEqual(names, ["mybundle"])

    def test_refresh_attachment_list_is_empty_with_no_target_identity(self):
        self.tab._attach_identity_var.set("")
        self.tab._refresh_attachment_list()
        self.assertEqual(len(self.tab.attachment_tree.get_children()), 0)

    def test_selected_attachment_name_returns_correct_value_when_selected(self):
        from biometrics.engine.attachments import attach_bytes

        record = self._save_identity()
        record = attach_bytes(record, "report.pdf", b"%PDF fake", self.master_key)
        self.store.save(record)

        self.tab._attach_identity_var.set("alice")
        self.tab._refresh_attachment_list()
        children = self.tab.attachment_tree.get_children()
        self.tab.attachment_tree.selection_set(children[0])
        self.assertEqual(self.tab._selected_attachment_name(), "report.pdf")


class _StubKeyring:
    """Stands in for crypto.keyring.Keyring: only to_state() is used."""

    def __init__(self, state):
        self._state = state

    def to_state(self):
        return dict(self._state)


@unittest.skipUnless(_HAS_TKINTER, "tkinter not installed")
class KeyringPersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp_dir.name) / "keyring.json"
        self.state = {"format": "test-keyring", "iterations": 10000}

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_new_keyring_is_saved_as_its_json_state(self):
        from gui.tabs.tab_biometrics import _save_new_keyring

        _save_new_keyring(self.path, _StubKeyring(self.state))
        with open(self.path, "r", encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), self.state)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits only")
    def test_new_keyring_is_saved_owner_only_on_posix(self):
        from gui.tabs.tab_biometrics import _save_new_keyring

        previous_umask = os.umask(0o022)  # would leave 0o644 without file_mode
        try:
            _save_new_keyring(self.path, _StubKeyring(self.state))
        finally:
            os.umask(previous_umask)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()




