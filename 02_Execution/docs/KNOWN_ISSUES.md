# docs/KNOWN_ISSUES.md
Brisart Research Archive -- known, currently unresolved issues.
Purpose: a permanent, honest record of bugs that were investigated and
NOT successfully fixed, so future engineers (including a future Jason)
don't have to re-discover the same dead ends from scratch. Each entry
documents the symptom, every fix that was attempted, why each attempt
was believed to fail, and what evidence would actually help resolve it
next time. This file should be updated whenever an issue in here is
either genuinely fixed (move it to CHANGELOG.md and delete the entry
here) or a new attempt is made and also fails (add the attempt to that
issue's history instead of starting a new entry).

---

## OPEN: Touchpad (Precision Touchpad / trackpad) scrolling does not
## work over the general page area -- only over the Scrollbar itself

**Status:** Unresolved. Multiple fix attempts made across several
sessions; none confirmed working by the reporting user (Jason, on a
Windows laptop touchpad). Physical mouse wheel scrolling DOES work
correctly everywhere on the page as of the FIX 5/6 attempts below --
this issue is touchpad-specific.

**Symptom (as reported):** Dragging the Scrollbar thumb directly always
works. Placing the cursor anywhere else on a page (over a Label, Card,
Frame, Button, Checkbutton -- any non-Scrollbar widget) and performing
a two-finger touchpad scroll gesture does nothing at all: the page does
not move.

**A related, DIFFERENT, and CONFIRMED-FIXED issue** (do not re-open or
conflate with the one above): mouse-wheel scrolling specifically while
hovering a `tk.Text` widget whose content already fits fully on screen
(e.g. the Settings page's near-empty "Update output" box, or a short
Activity Log) did nothing, because Tk's own built-in Text-widget scroll
binding swallows the event even when it has nothing to scroll
internally. That is fixed by
`gui.components.page_helpers.bind_text_widget_scroll_passthrough()`
(FIX 7) and is unrelated to the touchpad problem below -- it affects
mouse and touchpad equally, and was confirmed against the actual
reported screenshot.

### Attempts made, in order, and why each was believed insufficient

1. **Hover-gated bind/unbind (`<Enter>`/`<Leave>`) on the canvas.**
   Never worked at all, for mouse OR touchpad. The scrollable canvas is
   completely covered edge-to-edge by its own child Frame/Cards, so
   `<Leave>` fires on the canvas almost immediately after `<Enter>`
   (the pointer is always "over some child" the instant it's inside
   the page), unbinding the scroll handler before a scroll could ever
   register. Abandoned in favor of unconditional binding.

2. **`canvas.bind_all("<MouseWheel>", ...)`, bound unconditionally at
   page-build time**, with a delta-to-units conversion that guarantees
   at least 1 scroll unit for any nonzero `event.delta` (needed because
   trackpad-style deltas are often far below the 120-per-notch value a
   physical mouse wheel sends, and a naive `int(delta/120)` truncates
   anything smaller straight to 0). This fixed physical mouse wheel
   scrolling completely. It did NOT fix touchpad scrolling away from
   the Scrollbar -- reported as still broken.

3. **Focus-following (`bind_focus_follows_mouse`)**: hypothesis was
   that Windows routes `<MouseWheel>` to whichever widget currently
   holds keyboard focus, not strictly whichever widget is under the
   cursor -- and that the Scrollbar (the one naturally focusable widget
   on the page) was the only widget ever receiving focus, so it was the
   only widget the event ever reached. Implemented by walking the full
   widget tree and binding `<Enter>` on every widget to pull focus onto
   the canvas. Also extended to `<ButtonRelease-1>` (re-grab focus after
   any click) to cover the case where a touchpad scroll gesture
   involves literally zero cursor motion (no `<Enter>` fires), so focus
   might still be sitting on whatever was last clicked. **Reported by
   Jason as still not working.** This entire focus-based theory was
   never verified against a real Windows display -- it was only ever
   tested against a hand-built mock of Tkinter in a sandbox with no
   real Tk/display available -- so its core premise may simply be
   wrong for the environment in question.

4. **Direct per-widget instance binding
   (`bind_scrolling_recursively`)**: abandoned the focus theory
   entirely and instead walked the full widget tree, binding
   `<MouseWheel>`/`<Button-4>`/`<Button-5>` as an INSTANCE-level binding
   directly on every single widget (Canvas, Frame, Card, Label, Button,
   Checkbutton), reasoning that an instance binding on the literal
   widget under the cursor should fire regardless of focus or bindtag
   routing. Confirmed (via mocked test harness only) that every widget
   in a sample tree received the binding and that firing any of them
   invoked the shared scroll callback. **Reported by Jason as still not
   working for touchpad**, despite this being the most "should always
   work" mechanism attempted so far. This is the strongest signal that
   the problem is NOT about which widget receives the event at the
   Tkinter binding level at all, but something upstream of that --
   e.g. the touchpad driver, OS-level gesture handling, or the
   underlying Tcl/Tk build's WM_MOUSEWHEEL translation never generating
   a `<MouseWheel>` event for certain widgets/coordinates in the first
   place, before Tkinter's own binding system ever gets a chance to
   route it anywhere.

5. **Global root-level handler using live coordinate resolution
   (`_on_global_mousewheel` + `winfo_containing(event.x_root,
   event.y_root)`)**: hypothesized that Tk caches "which widget is
   under the pointer" for dispatch purposes based on the last
   `<Motion>` event, that a touchpad's zero-cursor-movement two-finger
   scroll gesture never updates that cache, and that resolving the
   REAL widget via a live OS coordinate query (independent of Tk's
   internal cache) would bypass the problem. Bound once at the Tk root
   rather than per-widget/per-page. **Reported by Jason as still not
   working.** Like attempt 3, this was only validated against mocked
   coordinate objects in a sandbox with no real Tk/display -- the
   `winfo_containing` mechanism itself, and whether `event.x_root` /
   `event.y_root` are even populated the same way for a touchpad-
   generated `<MouseWheel>` event as for a mouse-generated one, was
   never confirmed against Jason's actual machine.

### What would actually move this forward

Every attempt above was designed, implemented, and unit-tested entirely
against a **mocked/simulated Tkinter** (this development environment has
no real display or `_tkinter` module available at all), never against
a real Windows session with a real touchpad. That is very likely why
five structurally different theories have all "passed their own tests"
and all failed in Jason's hands: the tests were only ever checking
"does my own model of Tk behave the way I assumed," never "does real Tk
on real Windows with a real Precision Touchpad actually do this."

To make real progress, the next attempt needs PRINTLN/DEBUG evidence
gathered live, on the actual machine, such as:
  - Does ANY Python-level event at all fire when a touchpad scroll
    gesture happens over a non-Scrollbar widget? (Bind a temporary
    `print(event)` handler for `<MouseWheel>`, `<Button-4>`,
    `<Button-5>`, and even generic `<Motion>` at the Tk root via
    `bind_all`, and check the terminal while performing the exact
    gesture that fails.)
  - If NOTHING prints at all: the touchpad's two-finger scroll is
    likely being translated by Windows/the touchpad driver into
    something other than a standard `WM_MOUSEWHEEL` message that Tk's
    event loop recognizes as `<MouseWheel>` -- in which case the fix
    belongs at a different layer entirely (e.g. Windows touchpad/
    precision-touchpad driver settings, or an alternate low-level
    input hook), not in this application's Tkinter code at all.
  - If something DOES print, but with unexpected values (e.g.
    `event.num`, `event.delta`, `event.x_root`/`event.y_root` all
    zero/None, or the event firing on an unrelated/invisible widget),
    that would finally tell us which specific assumption among attempts
    2-5 above was wrong, instead of guessing a sixth mechanism blind.

Until that live diagnostic evidence exists, further blind attempts at a
6th/7th/8th fix mechanism are not likely to be more productive than the
five already tried and abandoned above.
