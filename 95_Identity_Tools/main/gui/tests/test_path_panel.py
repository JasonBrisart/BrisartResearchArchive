"""
File: gui/tests/test_path_panel.py

Purpose
-------
Tests for gui.widgets.path_panel.PathSelectionPanel: the shared
file/folder/drive picker used by both the Vault "Files / Folders / Drives"
sub-tab and the Biometrics "File Attachments" sub-tab.

Verifies: gui/widgets/path_panel.py.
Contains 10 test case(s) across 1 TestCase class(es).

Design notes:

Only the panel's own state management (paths list, dedup, on_change callback,
listbox sync) is under test here -- the actual file/folder picker dialogs
(tkinter.filedialog.askopenfilenames / askdirectory) are real OS dialogs and
are deliberately NOT exercised; _add_paths() is called directly instead,
exactly as the dialog callbacks themselves do internally.

Communication / relationships
-----------------------------
Depends on (project modules):
- gui.widgets.path_panel (gui/widgets/path_panel.py)
Standard library: tkinter, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
- _HAS_DISPLAY = _tk_display_available()

Edge cases
----------
- Starts with no paths.
- Add paths appends and syncs listbox.
- Add paths deduplicates.
- Add paths preserves first seen order.
- Clear all empties paths and listbox.
- Remove selected removes only the selected indices.
- Remove selected with multiple selection removes all of them.
- Remove selected with nothing selected is a no op.
- On change callback fires with current paths.
- Panel without on change does not raise.
- Skips (rather than fails) when a prerequisite is missing: "requires a
  Tk-capable display"

Known limitations
-----------------
- Requires a real Tk root (a Listbox cannot be constructed without one) and
  skips cleanly on a headless runner with no display, matching the convention
  used in test_busy.py.
- Passing proves only the 10 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest gui.tests.test_path_panel -v
    python tests/run_tests.py
"""

import unittest


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
class PathSelectionPanelTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        from gui.widgets.path_panel import PathSelectionPanel

        self.root = tk.Tk()
        self.root.withdraw()
        self.PathSelectionPanel = PathSelectionPanel

    def tearDown(self):
        self.root.destroy()

    def test_starts_with_no_paths(self):
        panel = self.PathSelectionPanel(self.root)
        self.assertEqual(panel.paths, [])
        self.assertEqual(panel.listbox.size(), 0)

    def test_add_paths_appends_and_syncs_listbox(self):
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/a.txt", "/tmp/b.txt"])
        self.assertEqual(panel.paths, ["/tmp/a.txt", "/tmp/b.txt"])
        self.assertEqual(panel.listbox.size(), 2)
        self.assertEqual(panel.listbox.get(0), "/tmp/a.txt")
        self.assertEqual(panel.listbox.get(1), "/tmp/b.txt")

    def test_add_paths_deduplicates(self):
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/a.txt"])
        panel._add_paths(["/tmp/a.txt", "/tmp/b.txt"])
        # "/tmp/a.txt" was already present, so it must not appear twice.
        self.assertEqual(panel.paths, ["/tmp/a.txt", "/tmp/b.txt"])
        self.assertEqual(panel.listbox.size(), 2)

    def test_add_paths_preserves_first_seen_order(self):
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/z.txt", "/tmp/a.txt"])
        panel._add_paths(["/tmp/m.txt"])
        self.assertEqual(panel.paths, ["/tmp/z.txt", "/tmp/a.txt", "/tmp/m.txt"])

    def test_clear_all_empties_paths_and_listbox(self):
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/a.txt", "/tmp/b.txt"])
        panel._clear_all()
        self.assertEqual(panel.paths, [])
        self.assertEqual(panel.listbox.size(), 0)

    def test_remove_selected_removes_only_the_selected_indices(self):
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/a.txt", "/tmp/b.txt", "/tmp/c.txt"])
        panel.listbox.selection_set(1)  # select "/tmp/b.txt" only
        panel._remove_selected()
        self.assertEqual(panel.paths, ["/tmp/a.txt", "/tmp/c.txt"])
        self.assertEqual(panel.listbox.size(), 2)

    def test_remove_selected_with_multiple_selection_removes_all_of_them(self):
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/a.txt", "/tmp/b.txt", "/tmp/c.txt"])
        panel.listbox.selection_set(0, 1)  # select "a" and "b"
        panel._remove_selected()
        self.assertEqual(panel.paths, ["/tmp/c.txt"])

    def test_remove_selected_with_nothing_selected_is_a_no_op(self):
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/a.txt"])
        panel._remove_selected()
        self.assertEqual(panel.paths, ["/tmp/a.txt"])

    def test_on_change_callback_fires_with_current_paths(self):
        seen = []
        panel = self.PathSelectionPanel(self.root, on_change=seen.append)
        panel._add_paths(["/tmp/a.txt"])
        self.assertEqual(seen[-1], ["/tmp/a.txt"])
        panel._clear_all()
        self.assertEqual(seen[-1], [])

    def test_panel_without_on_change_does_not_raise(self):
        # on_change is optional; _refresh_listbox() must guard against None
        # rather than assuming a callback was supplied.
        panel = self.PathSelectionPanel(self.root)
        panel._add_paths(["/tmp/a.txt"])  # must not raise


if __name__ == "__main__":
    unittest.main()




