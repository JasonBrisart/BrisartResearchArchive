# Known Issues

Standing record of currently unresolved bugs in Brisart Research Archive.
Every entry uses the standard bug report template. Resolved issues move to
docs/CHANGELOG.md under the release that fixed them.

To fill in the **Environment** field, run `python tools/envinfo.py` and paste
its output.

---

## KI-001: Touchpad scrolling does not scroll the general page area

- **Title:** Touchpad two-finger scrolling does not scroll page content outside the scrollbar
- **Reported date:** 2026-08-27 (0.8.0 ALPHA)
- **Severity:** Medium (usability; a physical mouse wheel and the scrollbar both work)
- **Environment:** Not recorded in this file. Run `python tools/envinfo.py` on the affected machine and paste the output here.
- **Component:** `gui/main_window.py` (`_on_global_mousewheel`), `gui/components/page_helpers.py`

### Steps to Reproduce
1. Launch the Archive with `python main.py`.
2. Open a page taller than the window, such as Settings.
3. Place the pointer over page content (a card or label, not a text box or the scrollbar).
4. Perform a two-finger scroll gesture on the touchpad.

### Expected behavior
The page scrolls, the same way it does with a physical mouse wheel.

### Actual behavior
Nothing scrolls. Dragging the scrollbar and using a physical mouse wheel both work.

### Tried / Ruled out
Listed in chronological order:
1. **Fix 1:** Hover-gated `<Enter>`/`<Leave>` binding on the canvas. Ruled out; the canvas is fully covered by its own child widgets, so it never receives the events.
2. **Fix 2:** Small deltas truncated to zero. Fixed with `mousewheel_units()`, which guarantees at least one unit for any nonzero delta. This did not resolve touchpad scrolling.
3. **Fix 3 and Fix 4:** Routing the wheel by keyboard focus. Insufficient.
4. **Fix 5:** Per-widget instance binding (`bind_scrolling_recursively()`). Fixed the physical mouse wheel; the touchpad is still unaffected.
5. **Fix 6:** Global root-level handler that resolves the widget under the pointer with `winfo_containing()`. This is the current primary mechanism; the touchpad is still unaffected.
6. **Fix 7:** Text widgets swallowed the wheel when their content fit. Fixed with `bind_text_widget_scroll_passthrough()`. This fix was unrelated to the touchpad.

### Next step
Proposed: temporarily log every event that reaches `_on_global_mousewheel` (`event.delta`, `event.num`, `event.widget`, and the `winfo_containing()` result) while performing the touchpad gesture. This shows whether Tk receives any `<MouseWheel>` event from the touchpad driver at all. If none arrives, the fix is outside the handler, for example in the driver's scrolling mode or in Tk's event delivery.
