# docs/KNOWN_ISSUES.md
Brisart Research Archive -- known, currently unresolved issues.
Standard bug report format going forward -- every entry uses this
template, filled in completely, kept as short as the facts allow. To
gather the **Environment:** field for a new entry, run `tools/envinfo.py`
from the repository root (on any OS -- it is not Windows-specific) and
paste its output directly into that field.

## [OPEN/FIXED]: <short title>

**Reported:** <date>
**Severity:** Critical / High / Medium / Low
**Environment:** OS, version, architecture, hardware, relevant software versions
**Component:** <file/module/feature affected>

**Steps to Reproduce:**
1. ...
2. ...
3. ...

**Expected behavior:** what should happen
**Actual behavior:** what actually happens

**Tried / Ruled out:** what's been attempted so far, and why each didn't work
**Next step:** the single concrete action that would move this forward

---

## [OPEN]: Touchpad (Precision Touchpad) scrolling doesn't work over
## the general page area -- only the Scrollbar itself responds

**Reported:** 2026-08-27
**Severity:** Medium
**Environment:**
```
OS: Windows 11 (build 10.0.26200)
Machine / Processor: ARM64 / ARMv8 (64-bit) Family 8 Model 1 Revision 201, Qualcomm Technologies Inc
Python: 3.14.7 (64bit, CPython)
Tkinter: Tcl 9.0.4 / Tk 9.0
```
Python is confirmed running natively for this machine's architecture
(not under emulation) -- `platform.machine()` matches the OS's native
architecture directly, ruling out an emulation-layer explanation.
**Component:** `gui/components/page_helpers.py`, `gui/main_window.py`
(mouse wheel scroll handling)

**Steps to Reproduce:**
1. Open any page with more content than fits in the window.
2. Rest the cursor over any widget that is NOT the Scrollbar (a Label, Card, Button, etc.).
3. Perform a two-finger scroll gesture on the touchpad.

**Expected behavior:** The page scrolls, same as it does with a physical mouse wheel.
**Actual behavior:** Nothing happens. Scrolling only works while the cursor is directly over the Scrollbar itself.

**Tried / Ruled out:** hover-gated bind/unbind, `bind_all` with a
delta-to-units fix, focus-following, direct per-widget instance
binding, and a global root-level handler using `winfo_containing()`
for live cursor resolution -- all confirmed still not working on the
actual machine. This rules out the issue being about which widget
receives the event at the Tkinter level. Also now confirmed Python
itself is running natively on this machine's architecture, not under
emulation -- ruling out the emulation-layer branch of the original
hypothesis. Remaining candidates: the touchpad driver or the OS's
input-translation layer behaving differently on this
architecture/device regardless of emulation, or this specific Tcl/Tk
version (a newer major version than the more commonly used 8.6) having
different touchpad-event handling.

**Next step:** Bind a temporary `print(event)` on
`<MouseWheel>`/`<Motion>` at the Tk root and launch from a terminal to
see if the event ever arrives at all during a touchpad gesture over a
non-Scrollbar widget. If nothing prints, the fix belongs outside this
codebase entirely (OS/driver level). If something does print, but with
an unusual widget target or zeroed fields, that narrows it to a Tcl/Tk
dispatch quirk specific to this Tcl/Tk version.
