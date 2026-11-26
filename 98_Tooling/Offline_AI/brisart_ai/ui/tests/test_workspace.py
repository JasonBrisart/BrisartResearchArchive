"""Purpose
-------
Exercise query drafts, diagnostic routing and the small-window composer.

This regression test module defines `TestQueryComposer`. Its scope is deliberately limited to
the responsibilities visible in this file rather than duplicating the application-wide
workflow. Its fixtures and assertions describe observable behavior without changing the
installed application.

Communication / relationships
-----------------------------
Uses ChatPanel directly without opening state or the external Native API stack.

The direct in-project imports visible in this module are `brisart_ai.ui.chat_panel`. Test
methods `test_submission_preserves_draft_until_accepted`,
`test_diagnostics_do_not_appear_in_results`, `test_composer_remains_visible_at_small_size`;
this identifies where behavior is invoked without implying a separate hidden dependency. The
test runner supplies the test lifecycle and any temporary fixtures.

Settings / parameters
---------------------
The layout check requires a Tk display.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
Busy and rejected submissions preserve the question.

The behaviors documented above must be read together with the actual branches in
test_workspace.py; assertions should reject regressions rather than merely checking file
layout. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Does not validate Windows-specific rendering.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python -m pytest brisart_ai/ui/tests/test_workspace.py -q

For a concrete entry point, inspect `TestQueryComposer`; run this module through the existing
project test runner with its actual test path. The example above is illustrative of this
file's present interface; do not treat it as an instruction to create additional state or call
private functions directly.
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
