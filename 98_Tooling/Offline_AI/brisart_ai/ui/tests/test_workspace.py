"""Purpose
-------
Exercise query drafts, diagnostic routing and the small-window composer.

Communication / relationships
-----------------------------
Uses ChatPanel directly without opening state or the external Native API stack.

Settings / parameters
---------------------
The layout check requires a Tk display.

Edge cases
----------
Busy and rejected submissions preserve the question.

Known limitations
-----------------
Does not validate Windows-specific rendering.

Examples
--------
python -m pytest brisart_ai/ui/tests/test_workspace.py -q
"""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

try:
    import tkinter as tk
except ImportError as exc:
    raise unittest.SkipTest(f"Tk unavailable: {exc}") from exc

from brisart_ai.ui.chat_panel import ChatPanel


class TestQueryComposer(unittest.TestCase):
    def test_submission_preserves_draft_until_accepted(self):
        draft = Mock()
        draft.get.return_value = "  local question  "
        panel = SimpleNamespace(input_var=draft, busy=True, on_submit=Mock(return_value=False), views=Mock())
        self.assertEqual(ChatPanel._submit(panel), "break")
        panel.on_submit.assert_not_called()
        panel.busy = False
        ChatPanel._submit(panel)
        panel.on_submit.assert_called_once_with("local question")
        draft.set.assert_not_called()
        panel.on_submit.return_value = True
        ChatPanel._submit(panel)
        draft.set.assert_called_once_with("")
        panel.views.select.assert_called_once_with(0)

    def test_diagnostics_do_not_appear_in_results(self):
        results, activity = Mock(), Mock()
        results.index.return_value = activity.index.return_value = "1.0"
        panel = SimpleNamespace(transcript=results, activity_log=activity)
        ChatPanel.append(panel, "diagnostic", "system")
        results.insert.assert_not_called()
        activity.insert.assert_called_once_with("end", "diagnostic", "system")
        activity.configure.assert_called_with(state="disabled")

    def test_composer_remains_visible_at_small_size(self):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(root.destroy)
        root.geometry("480x230")
        panel = ChatPanel(root, lambda _question: True)
        panel.pack(fill="both", expand=True)
        root.update()
        self.assertTrue(panel.entry.winfo_ismapped())
        self.assertTrue(panel.send.winfo_ismapped())
        self.assertLess(panel.entry.winfo_rooty(), panel.views.winfo_rooty())
